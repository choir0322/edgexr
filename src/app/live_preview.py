"""Loopback-only camera motion preview, accessed remotely using an SSH tunnel."""

from __future__ import annotations
from typing import Any, BinaryIO, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from _contracts import Frame, MotionShift, Record


import argparse
import base64
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import threading
import time
from urllib.parse import urlsplit
import numpy as np
from recording.visual_motion import WIDTH, HEIGHT, image_shift
from imu.live_reader import LiveImu, poll_imu
from vision.live_detector import (
    DetectionState,
    CpuDetector,
    detect_latest,
    SOURCE_WIDTH,
    SOURCE_HEIGHT,
)


def read_frame(stream: BinaryIO, size: int = WIDTH * HEIGHT) -> bytes | None:
    """Read exactly one raw grayscale frame from a possibly chunked pipe.

    Args:
        stream (BinaryIO): Readable binary pipe; reads may return fewer bytes than
            requested.
        size (int): Expected raw-frame byte count; gray uses one byte per pixel.

    Returns:
        bytes | None: Immutable pixels, or None on clean EOF; partial-frame EOF raises
            ValueError.
    """
    # Assemble exactly one raw frame across possibly short pipe reads.
    # An empty pipe is normal EOF only before any bytes of the next frame arrive.
    chunks = bytearray()
    while len(chunks) < size:
        part = stream.read(size - len(chunks))
        if not part:
            if chunks:
                raise ValueError("Camera pipe ended partway through a frame")
            return None
        chunks.extend(part)
    return bytes(chunks)


def rate(times: Sequence[float]) -> float | None:
    """Estimate event frequency from observed monotonic timestamps.

    Args:
        times (Sequence[float]): Ordered observation timestamps in seconds; arrays are
            one-dimensional.

    Returns:
        float | None: Events per second, or None when fewer than two usable times exist.
    """
    if len(times) < 2 or times[-1] <= times[0]:
        return None
    return (len(times) - 1) / (times[-1] - times[0])


class State:
    def __init__(
        self, imu_enabled: bool = False, detection_enabled: bool = False
    ) -> None:
        """Create bounded latest-value storage and synchronization for the live workers.

        Args:
            imu_enabled (bool): Whether the optional IMU path is selected.
            detection_enabled (bool): Whether full-frame detection storage is required.

        Returns:
            None: initializes shared state without starting workers.
        """
        # Coordinate workers with a condition and stop event; retain only the newest
        # frame/result and bounded timing histories rather than growing a frame queue.
        self.condition = threading.Condition()
        self.stop = threading.Event()
        self.latest = None
        self.received = 0
        self.analyzed = 0
        self.skipped = 0
        self.capture_times = deque(maxlen=60)
        self.analysis_times = deque(maxlen=60)
        self.result = None
        self.error = None
        self.started = time.monotonic()

        # Give IMU and detection their own status stores; either may fail independently.
        self.imu = LiveImu(imu_enabled)
        self.detector = DetectionState(detection_enabled)
        self.detection_frame = None

    def publish_frame(
        self, pixels: bytes, timestamp: float, detection_pixels: bytes | None = None
    ) -> None:
        """Replace waiting image slots and notify workers without queuing old frames.

        Args:
            pixels (bytes): Immutable row-major grayscale bytes; dimensions are specified by
                this stage.
            timestamp (float): Host monotonic observation time in seconds, not sensor
                exposure time.
            detection_pixels (bytes | None): Optional full 1280x720 gray bytes, separate
                from small motion pixels.

        Returns:
            None: advances the receipt sequence and recent capture-rate history.
        """
        # Publish both image sizes with the same receipt time and sequence under one
        # lock, then wake consumers. Replacing the slots deliberately drops older work.
        with self.condition:
            self.received += 1
            self.latest = (self.received, timestamp, pixels)
            if detection_pixels is not None and self.detector.enabled:
                self.detection_frame = (self.received, timestamp, detection_pixels)
            self.capture_times.append(timestamp)
            self.condition.notify_all()

    def fail(self, message: str) -> None:
        """Publish a camera/analysis failure and wake workers so they can stop.

        Args:
            message (str): Human-readable error retained for the terminal or browser.

        Returns:
            None: leaves the error visible in future snapshots.
        """
        with self.condition:
            self.error = message
            self.condition.notify_all()

    def publish_result(
        self,
        frame: Frame,
        previous_seq: int,
        shift: MotionShift | None,
        elapsed_ms: float,
        finished: float,
    ) -> None:
        """Store the latest analyzed image, displacement and motion-worker counters.

        Args:
            frame (Frame): Sequence integer, monotonic receipt seconds, and immutable gray
                bytes.
            previous_seq (int): Sequence of the previously analyzed frame; zero during
                startup.
            shift (MotionShift | None): dx/dy pixels, agreeing-patch count and peak quality,
                or no reliable estimate.
            elapsed_ms (float): Elapsed motion-estimator computation in milliseconds.
            finished (float): Host monotonic completion time in seconds for rate
                measurement.

        Returns:
            None: updates analyzed/skipped counts and latest browser result.
        """
        # Prepare browser-ready pixels and motion fields before taking the shared lock.
        # No previous frame means warm-up; a rejected estimate is not zero motion.
        seq, captured, pixels = frame
        result = dict(
            sequence=seq,
            captured=captured,
            analysis_ms=elapsed_ms,
            pixels_b64=base64.b64encode(pixels).decode("ascii"),
            dx=None,
            dy=None,
            patches=0,
            quality=None,
            motion="warming up" if previous_seq == 0 else "unreliable",
        )
        if shift is not None:
            result.update(
                dx=shift[0],
                dy=shift[1],
                patches=shift[2],
                quality=shift[3],
                motion="reliable",
            )

        # Atomically publish the result and count sequences bypassed by motion analysis.
        # This skip counter does not measure deliberate detector sampling.
        with self.condition:
            self.skipped += max(0, seq - previous_seq - 1)
            self.analyzed += 1
            self.analysis_times.append(finished)
            self.result = result

    def snapshot(self, now: float | None = None) -> Record:
        """Build a JSON-ready view of independently aged camera, detector and IMU results.

        Args:
            now (float | None): Host monotonic seconds used to calculate age; None selects
                the clock now.

        Returns:
            Record: Snapshot dictionary; stale camera displacement is hidden. This is not
                synchronized fusion.
        """
        # Copy a consistent result and determine freshness from its source receipt,
        # not completion time. Startup has a separate ten-second timeout.
        now = time.monotonic() if now is None else now
        with self.condition:
            result = dict(self.result) if self.result else {}
            age = now - result["captured"] if result else None
            status = (
                "error"
                if self.error
                else ("starting" if age is None else "stale" if age > 2 else "live")
            )
            startup_timeout = age is None and now - self.started > 10
            if startup_timeout:
                status = "error"

            # Add measured rates from the recent two-second histories and current counters.
            result.update(
                status=status,
                error=self.error,
                width=WIDTH,
                height=HEIGHT,
                received=self.received,
                analyzed=self.analyzed,
                skipped=self.skipped,
                result_age_ms=age * 1000 if age is not None else None,
                capture_fps=rate([t for t in self.capture_times if now - t < 2]),
                analysis_fps=rate([t for t in self.analysis_times if now - t < 2]),
            )
            if startup_timeout and not self.error:
                result[
                    "error"
                ] = "No analyzed frame within 10 seconds. Check the camera path, permissions and other camera readers."

            # Suppress invalid motion and attach independently aged IMU/detector snapshots;
            # sharing a response does not make the underlying measurements synchronized.
            if status != "live":
                result.update(motion="unavailable", dx=None, dy=None)
            result.pop("captured", None)
            result["imu"] = self.imu.snapshot(now)
            result["detector"] = self.detector.snapshot(now, status == "live")
            return result


def analyze_latest(state: State) -> None:
    """Compare the previous processed image with the newest available image until stopped.

    Args:
        state (State): Shared live application state, protected by its locks and stop
            event.

    Returns:
        None: publishes motion results or a camera-analysis error.
    """
    # Wait for a new sequence or shutdown/error, then release the condition lock
    # before image processing so capture can continue replacing the latest slot.
    previous = None
    while not state.stop.is_set():
        with state.condition:

            def motion_frame_ready() -> bool | str:
                """Wake on shutdown, a nonempty error, or a new eligible source sequence.

                Args:
                    None; values are captured from the enclosing function.

                Returns:
                    bool | str: The callback result described above.
                """
                return (
                    state.stop.is_set()
                    or state.error
                    or (
                        state.latest is not None
                        and (previous is None or state.latest[0] != previous[0])
                    )
                )

            state.condition.wait_for(
                motion_frame_ready,
                timeout=0.5,
            )
            if state.stop.is_set() or state.error:
                break
            frame = state.latest
        if frame is None or (previous is not None and frame[0] == previous[0]):
            continue

        # Compare only sufficiently close frames; a gap over half a second resets
        # the comparison. Time the estimator path separately from capture and display.
        try:
            begin = time.perf_counter()
            shift = None
            if previous is not None and frame[1] - previous[1] <= 0.5:
                first = np.frombuffer(previous[2], dtype=np.uint8).reshape(
                    HEIGHT, WIDTH
                )
                second = np.frombuffer(frame[2], dtype=np.uint8).reshape(HEIGHT, WIDTH)
                shift = image_shift(first, second)
            elapsed = (time.perf_counter() - begin) * 1000

            # Publish the source frame and result together, then advance the reference frame.
            state.publish_result(
                frame, previous[0] if previous else 0, shift, elapsed, time.monotonic()
            )
            previous = frame
        except Exception as error:
            state.fail(f"Analysis failed: {error}")
            break


def camera_command(
    device: str | None = None, demo: bool = False, detection: bool = False
) -> list[str]:
    """Build FFmpeg arguments for real/demo capture and the selected grayscale pipe size.

    Args:
        device (str | None): Verified V4L2 path such as /dev/video0; demo mode does not
            read it.
        demo (bool): Use synthetic FFmpeg imagery instead of a physical camera.
        detection (bool): Keep full source pixels for detection instead of downsizing in
            FFmpeg.

    Returns:
        list[str]: Argument list; real capture requires a device path unless demo is
            selected.
    """
    # Select a paced synthetic source or the verified MJPEG camera request.
    # Both feed the same raw-grayscale output path.
    command = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "warning"]
    if demo:
        size = f"{SOURCE_WIDTH}x{SOURCE_HEIGHT}" if detection else f"{WIDTH}x{HEIGHT}"
        command += ["-re", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30"]
    else:
        command += [
            "-f",
            "v4l2",
            "-input_format",
            "mjpeg",
            "-video_size",
            "1280x720",
            "-framerate",
            "30",
            "-i",
            device,
        ]

    # Detection needs the 720p source; motion-only mode reduces inside FFmpeg.
    # Python must read exactly width × height bytes for each gray frame.
    width, height = (SOURCE_WIDTH, SOURCE_HEIGHT) if detection else (WIDTH, HEIGHT)
    return command + [
        "-an",
        "-vf",
        f"scale={width}:{height}",
        "-pix_fmt",
        "gray",
        "-fps_mode",
        "passthrough",
        "-f",
        "rawvideo",
        "-",
    ]


def start_workers(
    state: State, command: list[str], cv: Any | None = None
) -> tuple[subprocess.Popen[bytes], list[threading.Thread]]:
    """Start FFmpeg and the diagnostic, capture and motion-analysis threads.

    Args:
        state (State): Shared live application state, protected by its locks and stop
            event.
        command (list[str]): FFmpeg argument list passed directly to Popen, not through
            a shell.
        cv (Any | None): OpenCV module or test double; Any is intentional for this
            optional native API.

    Returns:
        tuple[subprocess.Popen[bytes], list[threading.Thread]]: Child process and worker
            handles needed for orderly shutdown.
    """
    # Start FFmpeg with separate pixel/diagnostic pipes and bound its error history.
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    diagnostics = deque(maxlen=8)

    def log_errors() -> None:
        """Drain FFmpeg stderr independently so diagnostics cannot fill its pipe.

        Args:
            None.

        Returns:
            None: retains the last eight diagnostic lines in the enclosing deque.
        """
        for line in iter(process.stderr.readline, b""):
            diagnostics.append(line.decode(errors="replace").strip())

    def capture() -> None:
        """Receive complete decoded images and publish small/full images for the workers.

        Args:
            None.

        Returns:
            None: updates enclosing state and reports unexpected EOF or read failures.
        """
        # Read complete frames until stopped; unexpected EOF or decoding failure
        # becomes camera status rather than leaving the last result looking live.
        try:
            while not state.stop.is_set():
                full_size = (
                    SOURCE_WIDTH * SOURCE_HEIGHT
                    if state.detector.enabled
                    else WIDTH * HEIGHT
                )
                pixels = read_frame(process.stdout, full_size)
                if pixels is None:
                    if not state.stop.is_set():
                        state.fail("FFmpeg stopped. " + " | ".join(diagnostics))
                    return

                # Timestamp host receipt before resizing. With detection enabled, publish
                # a small motion image and the original 720p bytes from this same frame.
                received = time.monotonic()
                if state.detector.enabled:
                    gray = np.frombuffer(pixels, dtype=np.uint8).reshape(
                        SOURCE_HEIGHT, SOURCE_WIDTH
                    )
                    small = cv.resize(
                        gray, (WIDTH, HEIGHT), interpolation=cv.INTER_AREA
                    ).tobytes()
                    state.publish_frame(small, received, pixels)
                else:
                    state.publish_frame(pixels, received)
        except Exception as error:
            if not state.stop.is_set():
                state.fail(f"Capture failed: {error}")

    def run_motion_worker() -> None:
        """Bind this run's shared state to the no-argument thread entry point.

        Args:
            None; values are captured from the enclosing function.

        Returns:
            None: The callback result described above.
        """
        return analyze_latest(state)

    # Run pipe draining, capture and motion as threads in this Python process.
    threads = [
        threading.Thread(target=target, daemon=True)
        for target in (log_errors, capture, run_motion_worker)
    ]
    for thread in threads:
        thread.start()
    return process, threads


def stop_workers(
    state: State, process: subprocess.Popen[bytes], threads: Sequence[threading.Thread]
) -> None:
    """Signal workers to finish, stop FFmpeg and close the pipe resources.

    Args:
        state (State): Shared live application state, protected by its locks and stop
            event.
        process (subprocess.Popen[bytes]): FFmpeg child handle whose pipes/lifetime
            belong to this caller.
        threads (Sequence[threading.Thread]): Worker handles to join during shutdown.

    Returns:
        None: waits with bounded timeouts and kills FFmpeg only if termination times
            out.
    """
    # Wake blocked workers and terminate FFmpeg, escalating only after a timeout;
    # join workers before releasing their pipe handles.
    state.stop.set()
    with state.condition:
        state.condition.notify_all()
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)
    for thread in threads:
        thread.join(timeout=3)
    process.stdout.close()
    process.stderr.close()


def make_handler(state: State) -> type[BaseHTTPRequestHandler]:
    """Build an HTTP handler bound to this run's state and fixed preview page.

    Args:
        state (State): Shared live application state, protected by its locks and stop
            event.

    Returns:
        type[BaseHTTPRequestHandler]: Handler class serving only the page and JSON
            snapshot with loopback host checks.
    """
    page = Path(__file__).with_name("preview.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            """Serve an allowed preview route or reject unsupported/cross-site requests.

            Args:
                None.

            Returns:
                None: writes HTTP headers/body and tolerates a disconnected client.
            """
            # Restrict browser access to loopback hosts and reject cross-site requests.
            # The preview is intended for the existing SSH tunnel, not public exposure.
            host = self.headers.get("Host", "").split(":")[0]
            if (
                host not in ("127.0.0.1", "localhost")
                or self.headers.get("Sec-Fetch-Site") == "cross-site"
            ):
                self.send_error(403)
                return

            # Serve only the page and a JSON snapshot; all other paths are rejected.
            path = urlsplit(self.path).path
            if path == "/":
                content, kind = page, "text/html; charset=utf-8"
            elif path == "/api/frame":
                content = json.dumps(state.snapshot(), allow_nan=False).encode()
                kind = "application/json"
            else:
                self.send_error(404)
                return

            # Send an uncached response with its explicit type/length. A disconnected
            # browser is harmless and must not stop the camera workers.
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args: object) -> None:
            """Suppress default per-request terminal logging for the polling preview.

            Args:
                args (object): Unused formatting/message arguments supplied by
                    BaseHTTPRequestHandler.

            Returns:
                None: arguments are intentionally ignored.
            """
            pass

    return Handler


def make_server(state: State, port: int) -> ThreadingHTTPServer:
    """Bind the preview server to loopback rather than exposing it on the network.

    Args:
        state (State): Shared live application state, protected by its locks and stop
            event.
        port (int): Loopback TCP port; main restricts user-selected ports to
            1024..65535.

    Returns:
        ThreadingHTTPServer: Configured server; binding errors propagate to main.
    """
    # Bind locally and keep request handling bounded so shutdown stays responsive.
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    server.daemon_threads = True
    server.timeout = 0.25
    return server


def main() -> None:
    """Parse live options, start selected workers and serve until interruption.

    Args:
        None.

    Returns:
        None: None on normal shutdown; argparse exits for invalid setup or an OS error.
    """
    # Define and parse the input source, optional sensor/model paths and port.
    # Parsing these options does not yet open the camera or load a model.
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--device", help="verified V4L2 camera path")
    source.add_argument(
        "--demo", action="store_true", help="synthetic video; no camera access"
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--imu",
        action="store_true",
        help="read SunFounder SH3001 gyro on a separate thread",
    )
    parser.add_argument(
        "--detect", action="store_true", help="MobileNet-SSD CPU boxes at a target 2 Hz"
    )
    parser.add_argument(
        "--prototxt", type=Path, default=Path("models/mobilenet-ssd/deploy.prototxt")
    )
    parser.add_argument(
        "--weights",
        type=Path,
        default=Path("models/mobilenet-ssd/mobilenet_iter_73000.caffemodel"),
    )
    args = parser.parse_args()

    # Validate basic startup requirements before allocating worker resources.
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    if not shutil.which("ffmpeg"):
        parser.error("existing FFmpeg installation required")

    # Load OpenCV only for detection. Two internal threads are a baseline setting,
    # not reserved CPU cores; disable OpenCL to keep this path on the CPU.
    cv = None
    if args.detect:
        try:
            import cv2 as cv

            cv.setNumThreads(2)
            cv.ocl.setUseOpenCL(False)
        except ImportError:
            parser.exit(1, "--detect requires OpenCV; see docs/DETECTION_BASELINE.md\n")

    # Create shared state and start the server plus core camera/motion workers.
    # Keep resource handles available for cleanup even if later setup fails.
    state = State(imu_enabled=args.imu, detection_enabled=args.detect)
    process = None
    server = None
    try:
        server = make_server(state, args.port)
        process, threads = start_workers(
            state, camera_command(args.device, args.demo, args.detect), cv
        )

        # Construct the detector inside its worker so model loading does not block
        # camera capture; track the thread for orderly shutdown.
        if args.detect:

            def build_detector() -> CpuDetector:
                """Build the configured detector on its own worker, not the capture thread.

                Args:
                    None; values are captured from the enclosing function.

                Returns:
                    CpuDetector: The callback result described above.
                """
                return CpuDetector(cv, args.prototxt, args.weights)

            factory = build_detector
            worker = threading.Thread(
                target=detect_latest, args=(state, factory), daemon=True
            )
            worker.start()
            threads.append(worker)

        # Open the optional raw gyro reader and start its independent polling worker.
        # Report sensor setup failures without taking down the camera.
        if args.imu:
            try:
                from sunfounder_imu import IMU

                sensor = IMU().accel_gyro
                if sensor is None:
                    raise ValueError("No accelerometer/gyroscope found")
                imu_thread = threading.Thread(
                    target=poll_imu, args=(state.imu, sensor, state.stop), daemon=True
                )
                imu_thread.start()
                threads.append(imu_thread)
            except Exception as error:
                state.imu.fail(f"IMU setup failed: {error}")

        # Print the active configuration and measurement limits before serving requests.
        print(
            f"Preview: http://127.0.0.1:{args.port} (use SSH forwarding from your Mac).",
            flush=True,
        )
        print(
            "Camera: synthetic demo"
            if args.demo
            else f"Camera: {args.device}, requested 1280x720 MJPEG at 30 fps",
            flush=True,
        )
        print(
            "Analysis: 320x180 grayscale. No footage saved. Ctrl+C stops.", flush=True
        )
        if args.detect:
            print(
                "Detection: 720p source -> 300x300 model, CPU 2 threads, target 2 Hz. Boxes may lag; age shown.",
                flush=True,
            )
        if args.imu:
            print(
                "IMU: first second must be still; using per-run raw gyro offset. IMU errors appear in browser.",
                flush=True,
            )

        # Serve browser snapshots until interruption, then stop workers and close
        # the server even when startup or request handling raised an error.
        while not state.stop.is_set():
            server.handle_request()
    except KeyboardInterrupt:
        print("\nStopping preview.")
    except OSError as error:
        parser.exit(1, f"Preview failed: {error}\n")
    finally:
        if process is not None:
            stop_workers(state, process, threads)
        if server is not None:
            server.server_close()


if __name__ == "__main__":
    main()
