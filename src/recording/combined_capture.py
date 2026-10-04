"""Record local MJPEG video and raw IMU data; timestamps are not synchronized."""

import argparse
import csv
import json
import math
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import threading
import time


FRAME_RE = re.compile(r"\bn:\s*(\d+)\s+pts:\s*\S+\s+pts_time:\s*([-+\d.eE]+)")


def parse_frame(line):
    if "Parsed_showinfo" not in line:
        return None
    match = FRAME_RE.search(line)
    if not match:
        return None
    number, pts = int(match[1]), float(match[2])
    return (number, pts) if math.isfinite(pts) else None


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return number


def read_row(sensor, origin_ns, clock=time.monotonic_ns):
    before = clock()
    accel, gyro, _temperature = sensor.read_raw()
    after = clock()
    if len(accel) != 3 or len(gyro) != 3 or not all(
        math.isfinite(value) for value in (*accel, *gyro)
    ):
        raise ValueError("IMU returned invalid axes")
    return [(before + after) / 2e9 - origin_ns / 1e9,
            (after - before) / 1e9, *accel, *gyro]


def camera_command(device, video):
    # First output preserves compressed packets; second decodes for timing logs.
    return ["ffmpeg", "-hide_banner", "-nostdin", "-nostats", "-loglevel", "info",
            "-n", "-f", "v4l2", "-input_format", "mjpeg", "-video_size", "1280x720",
            "-framerate", "30", "-i", device,
            "-map", "0:v:0", "-c:v", "copy", str(video),
            "-map", "0:v:0", "-vf", "showinfo=checksum=0",
            "-fps_mode", "passthrough", "-f", "null", "-"]


def stop_camera(process):
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
        raise RuntimeError("FFmpeg required forced shutdown; video may be incomplete")


def record(sensor, args):
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    origin = time.monotonic_ns()
    command = camera_command(args.device, output / "camera.mkv")
    metadata = {
        "status": "incomplete", "host": platform.platform(),
        "python": platform.python_version(), "notes": args.notes,
        "requested_mode": "1280x720 MJPEG 30 fps",
        "requested_seconds_after_first_frame": args.seconds,
        "imu_sleep_seconds": args.interval, "origin_monotonic_ns": origin,
        "started_unix_seconds": time.time(), "command": command,
        "timestamp_scope": "camera PTS separate; host receipts and IMU read midpoints share monotonic clock",
        "calibration": "raw SH3001 driver units; no saved corrections applied",
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    first_frame = threading.Event()
    frames = []
    reader_errors = []
    imu_count = 0
    process = None
    reader = None
    failure = None

    def drain_camera():
        try:
            with (output / "ffmpeg.log").open("w") as log, (output / "frames.csv").open("w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["frame_index", "camera_pts_s", "host_receipt_s"])
                for line in process.stderr:
                    received = (time.monotonic_ns() - origin) / 1e9
                    log.write(line)
                    frame = parse_frame(line)
                    if frame is not None:
                        row = [*frame, received]
                        writer.writerow(row)
                        frames.append(row)
                        first_frame.set()
        except Exception as error:
            reader_errors.append(str(error))

    try:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, text=True)
        reader = threading.Thread(target=drain_camera)
        reader.start()
        print("Starting camera; remain still until RECORDING appears.", flush=True)
        startup = time.monotonic()
        deadline = None
        with (output / "imu.csv").open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["host_read_midpoint_s", "read_duration_s",
                             "ax_g", "ay_g", "az_g", "gx_dps", "gy_dps", "gz_dps"])
            while True:
                now = time.monotonic()
                if reader_errors:
                    raise RuntimeError(reader_errors[0])
                if process.poll() is not None:
                    raise RuntimeError("FFmpeg exited early; inspect ffmpeg.log")
                if deadline is None and first_frame.is_set():
                    deadline = now + args.seconds
                    metadata["recording_cue_host_s"] = now - origin / 1e9
                    print(f"RECORDING for {args.seconds:g} seconds.", flush=True)
                if deadline is not None and now >= deadline:
                    break
                if deadline is None and now - startup > 10:
                    raise RuntimeError("No decoded camera frame within 10 seconds")
                writer.writerow(read_row(sensor, origin))
                imu_count += 1
                time.sleep(args.interval)
    except KeyboardInterrupt:
        failure = "Interrupted by user"
    except Exception as error:
        failure = str(error)
    finally:
        if process is not None:
            try:
                stop_camera(process)
            except Exception as error:
                failure = failure or str(error)
            if reader is not None:
                reader.join(timeout=5)
            if process.stderr:
                process.stderr.close()
            metadata["ffmpeg_returncode"] = process.returncode
            # FFmpeg normally returns 255 after intentional SIGINT shutdown.
            if process.returncode not in (0, 255):
                failure = failure or "FFmpeg failed; inspect ffmpeg.log"
        if reader_errors:
            failure = failure or reader_errors[0]
        if len(frames) < 2 or imu_count < 2:
            failure = failure or "Insufficient frames or IMU samples"
        metadata.update(status="failed" if failure else "complete",
                        error=failure, decoded_frames=len(frames), imu_samples=imu_count,
                        elapsed_seconds=(time.monotonic_ns() - origin) / 1e9)
        if frames:
            metadata["first_frame_host_receipt_s"] = frames[0][2]
            metadata["last_frame_host_receipt_s"] = frames[-1][2]
            metadata["camera_pts_nonincreasing"] = sum(
                b[1] <= a[1] for a, b in zip(frames, frames[1:]))
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Saved {len(frames)} decoded-frame records and {imu_count} IMU samples to {output}")
    if failure:
        print(f"Incomplete run: {failure}", file=sys.stderr)
        return 1
    print("Video: camera.mkv. Timing is approximate host observation, not exposure synchronization.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True)
    parser.add_argument("--seconds", type=positive, default=15)
    parser.add_argument("--interval", type=positive, default=0.05)
    parser.add_argument("--output", type=Path, required=True, help="new directory under recordings/")
    parser.add_argument("--notes", default="Not supplied; experiment conditions unknown")
    args = parser.parse_args(argv)
    if not args.output.resolve().is_relative_to(Path("recordings").resolve()):
        parser.error("output must be under recordings/ (run from repository root)")
    if args.output.exists():
        parser.error("output already exists; choose a new run directory")
    if not shutil.which("ffmpeg"):
        parser.error("the existing FFmpeg installation is required")
    try:
        from sunfounder_imu import IMU
        sensor = IMU().accel_gyro
        if sensor is None:
            raise RuntimeError("No accelerometer/gyro found")
        return record(sensor, args)
    except Exception as error:
        print(f"Capture failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
