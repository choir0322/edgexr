"""Loopback-only camera motion preview, accessed remotely using an SSH tunnel."""

# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Describe data contracts without adding third-party runtime dependencies.
from typing import Any, BinaryIO, Sequence, TYPE_CHECKING

# Resolve documentation-only types for editors; this block does not run in production.
if TYPE_CHECKING:
    # Reuse the documented frame, sensor and report vocabulary for type checking.
    from _contracts import Frame, MotionShift, Record


# Parse and validate explicit command-line options.
import argparse

# Encode raw small-image bytes for transport inside JSON.
import base64

# Keep bounded timestamp/diagnostic histories with deque.
from collections import deque

# Serve a loopback-only preview page and JSON snapshots.
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Read or serialize metadata and browser/report payloads.
import json

# Work with explicit filesystem paths rather than shell expansions.
from pathlib import Path

# Check whether an existing external tool is available on PATH.
import shutil

# Run existing FFmpeg/ffprobe/Git tools with explicit argument lists.
import subprocess

# Coordinate independent workers using threads, locks, conditions and events.
import threading

# Measure host intervals and provide bounded polling pauses.
import time

# Extract HTTP route paths without treating queries as filesystem paths.
from urllib.parse import urlsplit

# Perform typed array and numerical operations; no sensor access occurs on import.
import numpy as np

# Reuse recording.visual_motion helpers rather than duplicating their behavior here.
from recording.visual_motion import WIDTH, HEIGHT, image_shift

# Reuse imu.live_reader helpers rather than duplicating their behavior here.
from imu.live_reader import LiveImu, poll_imu

# Reuse vision.live_detector helpers rather than duplicating their behavior here.
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
    # Accumulate short pipe reads until exactly one image has arrived.
    chunks = bytearray()
    # A pipe read may be short, so continue until the expected byte count is complete.
    while len(chunks) < size:
        # Take the next chunk or selected subset needed by this operation.
        part = stream.read(size - len(chunks))
        # Handle absent data explicitly instead of interpreting it as a valid zero.
        if not part:
            # Reject this invalid input before it can produce misleading output.
            if chunks:
                # Stop this operation with an explicit error rather than publishing invalid
                # data.
                raise ValueError("Camera pipe ended partway through a frame")
            # Represent missing or rejected data explicitly as None, not a measured zero.
            return None
        # Retain this item/chunk for the current calculation or bounded history.
        chunks.extend(part)
    # Return the documented result to the caller without starting another operation.
    return bytes(chunks)


def rate(times: Sequence[float]) -> float | None:
    """Estimate event frequency from observed monotonic timestamps.

    Args:
        times (Sequence[float]): Ordered observation timestamps in seconds; arrays are
            one-dimensional.

    Returns:
        float | None: Events per second, or None when fewer than two usable times exist.
    """
    # A frequency needs at least two observations with positive elapsed time.
    if len(times) < 2 or times[-1] <= times[0]:
        # Represent missing or rejected data explicitly as None, not a measured zero.
        return None
    # N observations contain N-1 measured intervals, not N full intervals.
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
        # Coordinate publication and wake workers without polling an old-frame queue.
        self.condition = threading.Condition()
        # Share one interruptible shutdown signal across application workers.
        self.stop = threading.Event()
        # Retain only the newest observation; readers may still hold an earlier local reference.
        self.latest = None
        # Count complete decoded-frame receipts rather than detector updates.
        self.received = 0
        # Count completed motion-analysis attempts, including unreliable estimates.
        self.analyzed = 0
        # Count decoded sequences bypassed by the motion worker, not detector sampling.
        self.skipped = 0
        # Bound capture timing history so memory does not grow with run duration.
        self.capture_times = deque(maxlen=60)
        # Bound completion history used to estimate recent motion throughput.
        self.analysis_times = deque(maxlen=60)
        # Keep one published result instead of an ever-growing result history.
        self.result = None
        # Retain the failure message for subsequent status snapshots.
        self.error = None
        # Remember monotonic startup time for no-data timeout checks.
        self.started = time.monotonic()
        # Create isolated IMU state even when that optional path is disabled.
        self.imu = LiveImu(imu_enabled)
        # Create isolated detector state with its own error/freshness policy.
        self.detector = DetectionState(detection_enabled)
        # Keep full pixels separately from the small motion image.
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
        # Hold the shared-state lock only while reading or replacing shared values.
        with self.condition:
            # Count complete decoded-frame receipts rather than detector updates.
            self.received += 1
            # Retain only the newest observation; readers may still hold an earlier local
            # reference.
            self.latest = (self.received, timestamp, pixels)
            # Only use the full-resolution detector path when detection was requested.
            if detection_pixels is not None and self.detector.enabled:
                # Keep full pixels separately from the small motion image.
                self.detection_frame = (self.received, timestamp, detection_pixels)
            # Retain this item/chunk for the current calculation or bounded history.
            self.capture_times.append(timestamp)
            # Wake waiting workers so they can observe the new data or stop/error state.
            self.condition.notify_all()

    def fail(self, message: str) -> None:
        """Publish a camera/analysis failure and wake workers so they can stop.

        Args:
            message (str): Human-readable error retained for the terminal or browser.

        Returns:
            None: leaves the error visible in future snapshots.
        """
        # Hold the shared-state lock only while reading or replacing shared values.
        with self.condition:
            # Retain the failure message for subsequent status snapshots.
            self.error = message
            # Wake waiting workers so they can observe the new data or stop/error state.
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
        # Unpack sequence, host receipt seconds and the analyzed image bytes.
        seq, captured, pixels = frame
        # Bundle analyzed pixels (Base64 for JSON), timing and an initially unavailable shift.
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
        # Use this estimate only after its reliability checks accepted it.
        if shift is not None:
            # Add the fields produced by this step while preserving the other report fields.
            result.update(
                dx=shift[0],
                dy=shift[1],
                patches=shift[2],
                quality=shift[3],
                motion="reliable",
            )
        # Hold the shared-state lock only while reading or replacing shared values.
        with self.condition:
            # Count decoded sequences bypassed by the motion worker, not detector sampling.
            self.skipped += max(0, seq - previous_seq - 1)
            # Count completed motion-analysis attempts, including unreliable estimates.
            self.analyzed += 1
            # Retain this item/chunk for the current calculation or bounded history.
            self.analysis_times.append(finished)
            # Keep one published result instead of an ever-growing result history.
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
        # Prepare now for the next step using the values calculated so far.
        now = time.monotonic() if now is None else now
        # Hold the shared-state lock only while reading or replacing shared values.
        with self.condition:
            # Copy the stored result before adding age/status, leaving published state intact.
            result = dict(self.result) if self.result else {}
            # Measure age from the observation/source time, not from when its result was
            # published.
            age = now - result["captured"] if result else None
            # Choose the visible state from enablement, errors, startup and freshness.
            status = (
                "error"
                if self.error
                else ("starting" if age is None else "stale" if age > 2 else "live")
            )
            # Report startup failure if no analyzed image appeared within ten host seconds.
            startup_timeout = age is None and now - self.started > 10
            # Choose the next branch using startup_timeout.
            if startup_timeout:
                # Choose the visible state from enablement, errors, startup and freshness.
                status = "error"
            # Add the fields produced by this step while preserving the other report fields.
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
            # Choose the next branch using startup_timeout and (not self.error).
            if startup_timeout and not self.error:
                # Prepare result['error'] for the next step using the values calculated so far.
                result[
                    "error"
                ] = "No analyzed frame within 10 seconds. Check the camera path, permissions and other camera readers."
            # Apply the freshness/status policy before exposing values to the user.
            if status != "live":
                # Add the fields produced by this step while preserving the other report fields.
                result.update(motion="unavailable", dx=None, dy=None)
            # Call result.pop for this step; its contract describes the result or side effect.
            result.pop("captured", None)
            # Prepare result['imu'] for the next step using the values calculated so far.
            result["imu"] = self.imu.snapshot(now)
            # Prepare result['detector'] for the next step using the values calculated so far.
            result["detector"] = self.detector.snapshot(now, status == "live")
            # Return the documented result to the caller without starting another operation.
            return result


def analyze_latest(state: State) -> None:
    """Compare the previous processed image with the newest available image until stopped.

    Args:
        state (State): Shared live application state, protected by its locks and stop
            event.

    Returns:
        None: publishes motion results or a camera-analysis error.
    """
    # Remember the last processed frame, not necessarily the last captured frame.
    previous = None
    # Repeat until the stop signal, deadline or explicit exit condition is reached.
    while not state.stop.is_set():
        # Hold the shared-state lock only while reading or replacing shared values.
        with state.condition:

            def motion_frame_ready() -> bool | str:
                """Wake on shutdown, a nonempty error, or a new eligible source sequence.

                Args:
                    None; values are captured from the enclosing function.

                Returns:
                    bool | str: The callback result described above.
                """
                # Evaluate the original callback expression only when the caller invokes it.
                return (
                    state.stop.is_set()
                    or state.error
                    or (
                        state.latest is not None
                        and (previous is None or state.latest[0] != previous[0])
                    )
                )

            # Wait for new eligible data or shutdown; notification can wake this before the
            # timeout.
            state.condition.wait_for(
                motion_frame_ready,
                timeout=0.5,
            )
            # Check shutdown/failure before starting another unit of worker work.
            if state.stop.is_set() or state.error:
                # Leave this loop; the enclosing cleanup/status code still runs.
                break
            # Hold a local reference to the latest slot so replacement cannot change this work
            # item.
            frame = state.latest
        # Handle absent data explicitly instead of interpreting it as a valid zero.
        if frame is None or (previous is not None and frame[0] == previous[0]):
            # Skip this unusable item and look for the next eligible observation.
            continue
        # Keep failure handling alongside the operation so cleanup/status remains explicit.
        try:
            # Start an elapsed computation timer, excluding capture and later browser display.
            begin = time.perf_counter()
            # Startup or a long observation gap must not produce a fabricated zero shift.
            shift = None
            # Compare only nearby observations; a long interruption is not ordinary frame-to-
            # frame motion.
            if previous is not None and frame[1] - previous[1] <= 0.5:
                # View the previously analyzed small frame as a (180, 320) pixel array.
                first = np.frombuffer(previous[2], dtype=np.uint8).reshape(
                    HEIGHT, WIDTH
                )
                # View the newest selected small frame with the same shape and dtype.
                second = np.frombuffer(frame[2], dtype=np.uint8).reshape(HEIGHT, WIDTH)
                # Estimate displacement only from these image pixels, not from gyro data.
                shift = image_shift(first, second)
            # Convert the measured estimator duration from seconds to milliseconds.
            elapsed = (time.perf_counter() - begin) * 1000
            # Publish completed work through the state object's synchronization boundary.
            state.publish_result(
                frame, previous[0] if previous else 0, shift, elapsed, time.monotonic()
            )
            # Remember the last processed frame, not necessarily the last captured frame.
            previous = frame
        # Handle this failure without losing the error or skipping the enclosing cleanup.
        except Exception as error:
            # Call state.fail for this step; its contract describes the result or side effect.
            state.fail(f"Analysis failed: {error}")
            # Leave this loop; the enclosing cleanup/status code still runs.
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
    # Build the explicit external-tool argument list with the existing settings.
    command = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "warning"]
    # Choose the next branch using demo.
    if demo:
        # Prepare size for the next step using the values calculated so far.
        size = f"{SOURCE_WIDTH}x{SOURCE_HEIGHT}" if detection else f"{WIDTH}x{HEIGHT}"
        # Update command with this step's contribution.
        command += ["-re", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30"]
    else:
        # Update command with this step's contribution.
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
    # Choose grayscale output dimensions for the full detector or small motion path.
    width, height = (SOURCE_WIDTH, SOURCE_HEIGHT) if detection else (WIDTH, HEIGHT)
    # Return the documented result to the caller without starting another operation.
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
    # Hold the child-process handle so its lifecycle can be managed safely.
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Retain only recent FFmpeg diagnostics, separate from binary pixel data.
    diagnostics = deque(maxlen=8)

    def log_errors() -> None:
        """Drain FFmpeg stderr independently so diagnostics cannot fill its pipe.

        Args:
            None.

        Returns:
            None: retains the last eight diagnostic lines in the enclosing deque.
        """
        # Process each line in the selected collection.
        for line in iter(process.stderr.readline, b""):
            # Retain this item/chunk for the current calculation or bounded history.
            diagnostics.append(line.decode(errors="replace").strip())

    def capture() -> None:
        """Receive complete decoded images and publish small/full images for the workers.

        Args:
            None.

        Returns:
            None: updates enclosing state and reports unexpected EOF or read failures.
        """
        # Keep failure handling alongside the operation so cleanup/status remains explicit.
        try:
            # Repeat until the stop signal, deadline or explicit exit condition is reached.
            while not state.stop.is_set():
                # Choose the pipe byte count from the enabled path, not the browser canvas size.
                full_size = (
                    SOURCE_WIDTH * SOURCE_HEIGHT
                    if state.detector.enabled
                    else WIDTH * HEIGHT
                )
                # Prepare pixels for the next step using the values calculated so far.
                pixels = read_frame(process.stdout, full_size)
                # Handle absent data explicitly instead of interpreting it as a valid zero.
                if pixels is None:
                    # Check shutdown/failure before starting another unit of worker work.
                    if not state.stop.is_set():
                        # Call state.fail for this step; its contract describes the result or
                        # side effect.
                        state.fail("FFmpeg stopped. " + " | ".join(diagnostics))
                    # Finish this handler/worker without producing another result.
                    return
                # Stamp host receipt; this is not the camera sensor exposure time.
                received = time.monotonic()
                # Choose the next branch using state.detector.enabled.
                if state.detector.enabled:
                    # Interpret the image as one grayscale intensity per pixel with explicit
                    # dimensions.
                    gray = np.frombuffer(pixels, dtype=np.uint8).reshape(
                        SOURCE_HEIGHT, SOURCE_WIDTH
                    )
                    # Downsample once for motion/display, retaining full source pixels
                    # separately.
                    small = cv.resize(
                        gray, (WIDTH, HEIGHT), interpolation=cv.INTER_AREA
                    ).tobytes()
                    # Publish completed work through the state object's synchronization
                    # boundary.
                    state.publish_frame(small, received, pixels)
                else:
                    # Publish completed work through the state object's synchronization
                    # boundary.
                    state.publish_frame(pixels, received)
        # Handle this failure without losing the error or skipping the enclosing cleanup.
        except Exception as error:
            # Check shutdown/failure before starting another unit of worker work.
            if not state.stop.is_set():
                # Call state.fail for this step; its contract describes the result or side
                # effect.
                state.fail(f"Capture failed: {error}")

    def run_motion_worker() -> None:
        """Bind this run's shared state to the no-argument thread entry point.

        Args:
            None; values are captured from the enclosing function.

        Returns:
            None: The callback result described above.
        """
        # Evaluate the original callback expression only when the caller invokes it.
        return analyze_latest(state)

    # Prepare handles for diagnostics, capture and motion so shutdown can join them.
    threads = [
        threading.Thread(target=target, daemon=True)
        for target in (log_errors, capture, run_motion_worker)
    ]
    # Process each thread in the selected collection.
    for thread in threads:
        # Start the worker so it can run independently of the caller's next step.
        thread.start()
    # Return the documented result to the caller without starting another operation.
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
    # Signal waiting work through the shared event rather than a busy loop.
    state.stop.set()
    # Hold the shared-state lock only while reading or replacing shared values.
    with state.condition:
        # Wake waiting workers so they can observe the new data or stop/error state.
        state.condition.notify_all()
    # Handle absent data explicitly instead of interpreting it as a valid zero.
    if process.poll() is None:
        # Call process.terminate for this step; its contract describes the result or side
        # effect.
        process.terminate()
    # Keep failure handling alongside the operation so cleanup/status remains explicit.
    try:
        # Pause for the configured interval; read/compute overhead is additional time.
        process.wait(timeout=3)
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except subprocess.TimeoutExpired:
        # Call process.kill for this step; its contract describes the result or side effect.
        process.kill()
        # Pause for the configured interval; read/compute overhead is additional time.
        process.wait(timeout=3)
    # Process each thread in the selected collection.
    for thread in threads:
        # Wait for this worker to finish, respecting the existing bounded timeout.
        thread.join(timeout=3)
    # Release the stream or server resource after use.
    process.stdout.close()
    # Release the stream or server resource after use.
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
    # Load the fixed preview page once rather than serving arbitrary files.
    page = Path(__file__).with_name("preview.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            """Serve an allowed preview route or reject unsupported/cross-site requests.

            Args:
                None.

            Returns:
                None: writes HTTP headers/body and tolerates a disconnected client.
            """
            # Extract the requested hostname before checking the loopback allowlist.
            host = self.headers.get("Host", "").split(":")[0]
            # Choose the next branch using host not in ('127.0.0.1', 'localhost') or
            # self.headers.get('Sec-Fetch-Sit....
            if (
                host not in ("127.0.0.1", "localhost")
                or self.headers.get("Sec-Fetch-Site") == "cross-site"
            ):
                # Call self.send_error for this step; its contract describes the result or side
                # effect.
                self.send_error(403)
                # Finish this handler/worker without producing another result.
                return
            # Resolve the local path or requested route used by the next operation.
            path = urlsplit(self.path).path
            # Choose the next branch using path == '/'.
            if path == "/":
                # Pair the response payload with its correct HTTP content type.
                content, kind = page, "text/html; charset=utf-8"
            # Choose the next branch using path == '/api/frame'.
            elif path == "/api/frame":
                # Prepare content for the next step using the values calculated so far.
                content = json.dumps(state.snapshot(), allow_nan=False).encode()
                # Prepare kind for the next step using the values calculated so far.
                kind = "application/json"
            else:
                # Call self.send_error for this step; its contract describes the result or side
                # effect.
                self.send_error(404)
                # Finish this handler/worker without producing another result.
                return
            # Call self.send_response for this step; its contract describes the result or side
            # effect.
            self.send_response(200)
            # Describe response encoding, length or cache/security policy to the browser.
            self.send_header("Content-Type", kind)
            # Describe response encoding, length or cache/security policy to the browser.
            self.send_header("Content-Length", str(len(content)))
            # Describe response encoding, length or cache/security policy to the browser.
            self.send_header("Cache-Control", "no-store")
            # Describe response encoding, length or cache/security policy to the browser.
            self.send_header("X-Content-Type-Options", "nosniff")
            # Call self.end_headers for this step; its contract describes the result or side
            # effect.
            self.end_headers()
            # Keep failure handling alongside the operation so cleanup/status remains explicit.
            try:
                # Call self.wfile.write for this step; its contract describes the result or side
                # effect.
                self.wfile.write(content)
            # Handle this failure without losing the error or skipping the enclosing cleanup.
            except (BrokenPipeError, ConnectionResetError):
                # Intentionally do nothing here; the surrounding status or cleanup policy
                # handles this case.
                pass

        def log_message(self, *args: object) -> None:
            """Suppress default per-request terminal logging for the polling preview.

            Args:
                args (object): Unused formatting/message arguments supplied by
                    BaseHTTPRequestHandler.

            Returns:
                None: arguments are intentionally ignored.
            """
            # Intentionally do nothing here; the surrounding status or cleanup policy handles
            # this case.
            pass

    # Return the documented result to the caller without starting another operation.
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
    # Create the loopback server that serves independent browser requests.
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    # Allow request threads to finish without preventing application exit.
    server.daemon_threads = True
    # Bound idle request waiting so shutdown can be checked promptly.
    server.timeout = 0.25
    # Return the documented result to the caller without starting another operation.
    return server


def main() -> None:
    """Parse live options, start selected workers and serve until interruption.

    Args:
        None.

    Returns:
        None: None on normal shutdown; argparse exits for invalid setup or an OS error.
    """
    # Define the command-line interface without starting hardware work yet.
    parser = argparse.ArgumentParser(description=__doc__)
    # Require exactly one input source: real device or synthetic demo.
    source = parser.add_mutually_exclusive_group(required=True)
    # Declare --device with its existing default, validation and help text.
    source.add_argument("--device", help="verified V4L2 camera path")
    # Declare --demo with its existing default, validation and help text.
    source.add_argument(
        "--demo", action="store_true", help="synthetic video; no camera access"
    )
    # Declare --port with its existing default, validation and help text.
    parser.add_argument("--port", type=int, default=8765)
    # Declare --imu with its existing default, validation and help text.
    parser.add_argument(
        "--imu",
        action="store_true",
        help="read SunFounder SH3001 gyro on a separate thread",
    )
    # Declare --detect with its existing default, validation and help text.
    parser.add_argument(
        "--detect", action="store_true", help="MobileNet-SSD CPU boxes at a target 2 Hz"
    )
    # Declare --prototxt with its existing default, validation and help text.
    parser.add_argument(
        "--prototxt", type=Path, default=Path("models/mobilenet-ssd/deploy.prototxt")
    )
    # Declare --weights with its existing default, validation and help text.
    parser.add_argument(
        "--weights",
        type=Path,
        default=Path("models/mobilenet-ssd/mobilenet_iter_73000.caffemodel"),
    )
    # Parse command-line values into the namespace used by this operation.
    args = parser.parse_args()
    # Choose the next branch using not 1024 <= args.port <= 65535.
    if not 1024 <= args.port <= 65535:
        # Call parser.error for this step; its contract describes the result or side effect.
        parser.error("port must be between 1024 and 65535")
    # Choose the next branch using not shutil.which('ffmpeg').
    if not shutil.which("ffmpeg"):
        # Call parser.error for this step; its contract describes the result or side effect.
        parser.error("existing FFmpeg installation required")
    # Hold the optional OpenCV runtime; it is not imported for motion-only operation.
    cv = None
    # Only use the full-resolution detector path when detection was requested.
    if args.detect:
        # Keep failure handling alongside the operation so cleanup/status remains explicit.
        try:
            # Load optional OpenCV only for detection or its explicit runtime test.
            import cv2 as cv

            # Request OpenCV parallelism; this neither reserves cores nor sets detector update
            # frequency.
            cv.setNumThreads(2)
            # Keep this baseline on the CPU rather than using an implicit OpenCL path.
            cv.ocl.setUseOpenCL(False)
        # Handle this failure without losing the error or skipping the enclosing cleanup.
        except ImportError:
            # Call parser.exit for this step; its contract describes the result or side effect.
            parser.exit(1, "--detect requires OpenCV; see docs/DETECTION_BASELINE.md\n")
    # Create or select shared live state for this run.
    state = State(imu_enabled=args.imu, detection_enabled=args.detect)
    # Hold the child-process handle so its lifecycle can be managed safely.
    process = None
    # Create the loopback server that serves independent browser requests.
    server = None
    # Keep failure handling alongside the operation so cleanup/status remains explicit.
    try:
        # Create the loopback server that serves independent browser requests.
        server = make_server(state, args.port)
        # Prepare process, threads for the next step using the values calculated so far.
        process, threads = start_workers(
            state, camera_command(args.device, args.demo, args.detect), cv
        )
        # Only use the full-resolution detector path when detection was requested.
        if args.detect:

            def build_detector() -> CpuDetector:
                """Build the configured detector on its own worker, not the capture thread.

                Args:
                    None; values are captured from the enclosing function.

                Returns:
                    CpuDetector: The callback result described above.
                """
                # Evaluate the original callback expression only when the caller invokes it.
                return CpuDetector(cv, args.prototxt, args.weights)

            # Delay detector construction until its own worker starts.
            factory = build_detector
            # Prepare the separate detection worker so inference cannot block capture directly.
            worker = threading.Thread(
                target=detect_latest, args=(state, factory), daemon=True
            )
            # Start the worker so it can run independently of the caller's next step.
            worker.start()
            # Retain this item/chunk for the current calculation or bounded history.
            threads.append(worker)
        # Only create the I2C worker when the user requested live IMU readings.
        if args.imu:
            # Keep failure handling alongside the operation so cleanup/status remains explicit.
            try:
                # Import the existing Pi driver only when a real sensor path is requested.
                from sunfounder_imu import IMU

                # Select the accelerometer/gyroscope driver interface, not the saved calibration
                # output.
                sensor = IMU().accel_gyro
                # Reject this invalid input before it can produce misleading output.
                if sensor is None:
                    # Stop this operation with an explicit error rather than publishing invalid
                    # data.
                    raise ValueError("No accelerometer/gyroscope found")
                # Prepare I2C reads on their own worker rather than the image-analysis thread.
                imu_thread = threading.Thread(
                    target=poll_imu, args=(state.imu, sensor, state.stop), daemon=True
                )
                # Start the worker so it can run independently of the caller's next step.
                imu_thread.start()
                # Retain this item/chunk for the current calculation or bounded history.
                threads.append(imu_thread)
            # Handle this failure without losing the error or skipping the enclosing cleanup.
            except Exception as error:
                # Call state.imu.fail for this step; its contract describes the result or side
                # effect.
                state.imu.fail(f"IMU setup failed: {error}")
        # Explain the current result, progress or failure in the terminal.
        print(
            f"Preview: http://127.0.0.1:{args.port} (use SSH forwarding from your Mac).",
            flush=True,
        )
        # Explain the current result, progress or failure in the terminal.
        print(
            "Camera: synthetic demo"
            if args.demo
            else f"Camera: {args.device}, requested 1280x720 MJPEG at 30 fps",
            flush=True,
        )
        # Explain the current result, progress or failure in the terminal.
        print(
            "Analysis: 320x180 grayscale. No footage saved. Ctrl+C stops.", flush=True
        )
        # Only use the full-resolution detector path when detection was requested.
        if args.detect:
            # Explain the current result, progress or failure in the terminal.
            print(
                "Detection: 720p source -> 300x300 model, CPU 2 threads, target 2 Hz. Boxes may lag; age shown.",
                flush=True,
            )
        # Only create the I2C worker when the user requested live IMU readings.
        if args.imu:
            # Explain the current result, progress or failure in the terminal.
            print(
                "IMU: first second must be still; using per-run raw gyro offset. IMU errors appear in browser.",
                flush=True,
            )
        # Repeat until the stop signal, deadline or explicit exit condition is reached.
        while not state.stop.is_set():
            # Call server.handle_request for this step; its contract describes the result or
            # side effect.
            server.handle_request()
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except KeyboardInterrupt:
        # Explain the current result, progress or failure in the terminal.
        print("\nStopping preview.")
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except OSError as error:
        # Call parser.exit for this step; its contract describes the result or side effect.
        parser.exit(1, f"Preview failed: {error}\n")
    finally:
        # Choose the next branch using process is not None.
        if process is not None:
            # Call stop_workers for this step; its contract describes the result or side effect.
            stop_workers(state, process, threads)
        # Choose the next branch using server is not None.
        if server is not None:
            # Release the stream or server resource after use.
            server.server_close()


# Run the command only when executed directly, not when imported by tests or another module.
if __name__ == "__main__":
    # Call main for this step; its contract describes the result or side effect.
    main()
