"""Offline patch motion versus gyro: approximate host pairing, not synchronization.

Requires existing NumPy, ffmpeg and ffprobe. Pixels refer to 320x180 images.
Run from repo root: PYTHONPATH=src python3 -m recording.visual_motion --help
"""

# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Describe data contracts without adding third-party runtime dependencies.
from typing import Sequence, TYPE_CHECKING

# Resolve documentation-only types for editors; this block does not run in production.
if TYPE_CHECKING:
    # Perform typed array and numerical operations; no sensor access occurs on import.
    import numpy as np

    # Reuse the documented frame, sensor and report vocabulary for type checking.
    from _contracts import MotionShift, NumericRow, Record


# Parse and validate explicit command-line options.
import argparse

# Read/write explicit numeric columns for reproducible offline analysis.
import csv

# Read or serialize metadata and browser/report payloads.
import json

# Validate finite numbers and perform scalar numerical calculations.
import math

# Work with explicit filesystem paths rather than shell expansions.
from pathlib import Path

# Check whether an existing external tool is available on PATH.
import shutil

# Run existing FFmpeg/ffprobe/Git tools with explicit argument lists.
import subprocess

# Perform typed array and numerical operations; no sensor access occurs on import.
import numpy as np

# Reuse analyze_capture helpers rather than duplicating their behavior here.
from .analyze_capture import analyze, numeric_csv, timing


# Use 320 columns and 180 rows for all motion-estimator inputs.
WIDTH, HEIGHT = 320, 180


def patch_shift(
    first: np.ndarray, second: np.ndarray
) -> tuple[float, float, float] | None:
    """Estimate scene-content translation from one pair of textured image patches.

    Return content displacement (right/down positive), or reject low quality.

    Phase correlation locates the peak of the normalized cross spectrum. A
    Hann window reduces edge artifacts; peak-to-sidelobe ratio rejects weak
    matches. These quality thresholds are experimental, not probabilities.

    Args:
        first (np.ndarray): Earlier 2D grayscale numeric patch, at least 16 pixels
            on each side; the caller normally selects a (56, 80) patch.
        second (np.ndarray): Later grayscale 2D numeric array with the same shape as
            first.

    Returns:
        tuple[float, float, float] | None: dx/dy pixels and peak quality, or None for
            ambiguous/large shifts.
    """
    # Reject this invalid input before it can produce misleading output.
    if first.shape != second.shape or first.ndim != 2 or min(first.shape) < 16:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Need equal 2D patches at least 16 pixels wide/high")
    # Use floating point so centering and Fourier arithmetic do not overflow uint8.
    a, b = first.astype(float), second.astype(float)
    # Reject this invalid input before it can produce misleading output.
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Nonfinite image data")
    # Reject flat patches: there is too little texture to locate a meaningful shift.
    if min(a.std(), b.std()) < 3:
        # Represent missing or rejected data explicitly as None, not a measured zero.
        return None
    # Taper patch edges in both dimensions to reduce artificial wraparound features.
    window = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    # Compare Fourier phases; this order gives scene displacement from first to second.
    cross = np.fft.fft2((b - b.mean()) * window) * np.conj(
        np.fft.fft2((a - a.mean()) * window)
    )
    # Measure spectrum amplitude so it can be removed from the phase comparison.
    magnitude = np.abs(cross)
    # Remove amplitude while flooring tiny magnitudes to avoid division by zero.
    cross /= np.maximum(magnitude, 1e-9)
    # Transform phase agreement back to displacement space; its peak locates the shift.
    surface = np.fft.ifft2(cross).real
    # Locate the strongest displacement candidate on the correlation surface.
    y, x = np.unravel_index(np.argmax(surface), surface.shape)
    # Remove the wrapped 5x5 peak neighbourhood before estimating background.
    mask = np.ones(surface.shape, dtype=bool)
    # Walk the small neighbourhood that must be excluded from background peak statistics.
    for dy in range(-2, 3):
        # Walk the small neighbourhood that must be excluded from background peak statistics.
        for dx in range(-2, 3):
            # Exclude the peak neighbourhood even when it wraps across an array edge.
            mask[(y + dy) % a.shape[0], (x + dx) % a.shape[1]] = False
    # Measure background correlation away from the peak neighbourhood.
    side = surface[mask]
    # Compare peak height to background variation; this is not a probability.
    quality = (surface[y, x] - side.mean()) / max(side.std(), 1e-9)

    def refine(index: int, values: np.ndarray) -> float:
        """Refine a correlation peak below one pixel and unwrap signed displacement.

        Args:
            index (int): Integer location of the strongest correlation peak.
            values (np.ndarray): One-dimensional row/column of the correlation surface
                through the peak.

        Returns:
            float: Signed pixel displacement with local correction clipped to half a pixel.
        """
        # Read wrapped neighbours on both sides of the one-dimensional peak.
        left, center, right = (
            values[(index - 1) % len(values)],
            values[index],
            values[(index + 1) % len(values)],
        )
        # Measure local curvature for a parabolic peak refinement.
        denominator = left - 2 * center + right
        # Avoid unstable division when the peak neighbourhood is nearly flat.
        fraction = 0.5 * (left - right) / denominator if abs(denominator) > 1e-12 else 0
        # Unwrap the periodic peak and add a bounded half-pixel local refinement.
        return (index if index <= len(values) // 2 else index - len(values)) + float(
            np.clip(fraction, -0.5, 0.5)
        )

    # Refine horizontal and vertical peaks independently to subpixel precision.
    dx, dy = refine(x, surface[y, :]), refine(y, surface[:, x])
    # Reject weak peaks and shifts too large for this small-patch translation model.
    if quality < 8 or abs(dx) > a.shape[1] / 4 or abs(dy) > a.shape[0] / 4:
        # Represent missing or rejected data explicitly as None, not a measured zero.
        return None
    # Return the documented result to the caller without starting another operation.
    return dx, dy, float(quality)


def image_shift(first: np.ndarray, second: np.ndarray) -> MotionShift | None:
    """Combine agreeing patch translations across two 320x180 grayscale images.

    Args:
        first (np.ndarray): Earlier grayscale 2D numeric array; image_shift expects
            shape (180, 320).
        second (np.ndarray): Later grayscale 2D numeric array with the same shape as
            first.

    Returns:
        MotionShift | None: dx/dy pixels, agreeing-patch count and median quality, or
            None.
    """
    # Reject this invalid input before it can produce misleading output.
    if first.shape != (HEIGHT, WIDTH) or second.shape != first.shape:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Images must be 320x180 grayscale")
    # Collect valid patch translations before testing cross-image agreement.
    matches = []
    # Visit the fixed patch positions so motion is checked across the image.
    for y in (5, 62, 119):
        # Visit the fixed patch positions so motion is checked across the image.
        for x in (5, 117, 229):
            # Compare the same 56-row by 80-column region in both images.
            match = patch_shift(
                first[y : y + 56, x : x + 80], second[y : y + 56, x : x + 80]
            )
            # Use this estimate only after its reliability checks accepted it.
            if match is not None:
                # Retain this item/chunk for the current calculation or bounded history.
                matches.append(match)
    # Require enough independent observations before accepting this estimate.
    if len(matches) < 4:
        # Represent missing or rejected data explicitly as None, not a measured zero.
        return None
    # Collect valid patch translations before testing cross-image agreement.
    matches = np.asarray(matches)
    # Use a median displacement so one locally moving region has less influence.
    center = np.median(matches[:, :2], axis=0)
    # Keep only patch translations within 1.5 pixels of the consensus center.
    good = matches[np.linalg.norm(matches[:, :2] - center, axis=1) <= 1.5]
    # Require enough independent observations before accepting this estimate.
    if len(good) < 4:
        # Represent missing or rejected data explicitly as None, not a measured zero.
        return None
    # Take the final robust displacement from the agreeing patches only.
    shift = np.median(good[:, :2], axis=0)
    # Return the documented result to the caller without starting another operation.
    return float(shift[0]), float(shift[1]), len(good), float(np.median(good[:, 2]))


def validate_video_times(
    video_times: Sequence[float], frame_rows: Sequence[NumericRow]
) -> float:
    """Verify decoded video and frame-log indices/timing before pairing by position.

    Args:
        video_times (Sequence[float]): Decoded video presentation times in seconds from
            ffprobe.
        frame_rows (Sequence[NumericRow]): Logged numeric rows with contiguous
            frame_index and camera_pts_s.

    Returns:
        float: Largest relative-PTS disagreement in seconds; raises ValueError on
            mismatches.
    """
    # Reject this invalid input before it can produce misleading output.
    if len(video_times) != len(frame_rows) or len(video_times) < 3:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError(
            "Video/log frame counts differ or are too short; cannot associate by index"
        )
    # Reject this invalid input before it can produce misleading output.
    if any(r["frame_index"] != i for i, r in enumerate(frame_rows)):
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Frame indices are not contiguous from zero")
    # Call timing for this step; its contract describes the result or side effect.
    timing(video_times)
    # Extract original camera PTS from the recorded frame log.
    logged = [r["camera_pts_s"] for r in frame_rows]
    # Call timing for this step; its contract describes the result or side effect.
    timing(logged)
    # Matroska quantizes these MJPEG timestamps to milliseconds.
    mismatch = max(
        abs((v - video_times[0]) - (p - logged[0])) for v, p in zip(video_times, logged)
    )
    # Reject this invalid input before it can produce misleading output.
    if mismatch > 0.002:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Video/log relative timestamps differ by more than 2 ms")
    # Return the documented result to the caller without starting another operation.
    return mismatch


def gyro_at(
    timestamp: float, times: np.ndarray, values: np.ndarray
) -> np.ndarray | None:
    """Interpolate XYZ gyro only inside two sufficiently close host observations.

    Args:
        timestamp (float): Host monotonic observation time in seconds, not sensor
            exposure time.
        times (np.ndarray): Ordered observation timestamps in seconds; arrays are one-
            dimensional.
        values (np.ndarray): N-by-3 numeric array of bias-corrected XYZ degrees/s,
            aligned with times.

    Returns:
        np.ndarray | None: Three interpolated degrees/s values, or None outside
            coverage/over a large gap.
    """
    # Find the first observation to the right of the desired host timestamp.
    index = int(np.searchsorted(times, timestamp, side="right"))
    # Choose the next branch using index == 0 or index == len(times).
    if index == 0 or index == len(times):
        # Represent missing or rejected data explicitly as None, not a measured zero.
        return None
    # Select the pair of observation times that brackets the requested time.
    before, after = times[index - 1], times[index]
    # Choose the next branch using after - before > 0.15.
    if after - before > 0.15:
        # Represent missing or rejected data explicitly as None, not a measured zero.
        return None
    # Measure the fractional position between the two bracketing timestamps.
    weight = (timestamp - before) / (after - before)
    # Linearly blend the two bracketing vectors without extrapolating outside the data.
    return values[index - 1] * (1 - weight) + values[index] * weight


def inspect_recording(folder: Path) -> tuple[Record, list[Record]]:
    """Compare recorded patch motion and bias-corrected gyro using approximate host pairing.

    Args:
        folder (Path): Existing local recording/comparison directory; raw data remains
            out of Git.

    Returns:
        tuple[Record, list[Record]]: Summary and per-pair rows; no sensor
            synchronization or fitted camera calibration.
    """
    # Validate the recording and estimate bias from its assumed-still first second.
    baseline = analyze(folder, baseline_seconds=1)
    # Read the existing recording metadata before trusting frame or IMU logs.
    meta = json.loads((folder / "metadata.json").read_text())
    # Collect frame-log rows used for saved counts and timing checks.
    frames = numeric_csv(folder / "frames.csv")
    # Load the saved numeric IMU rows for host-time interpolation.
    imu = numeric_csv(folder / "imu.csv")
    # Reject this invalid input before it can produce misleading output.
    if len(frames) > 3000:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("This first offline tool is limited to 3000 frames per run")
    # Ask ffprobe for saved-video timestamps before matching frames to log rows.
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "frame=best_effort_timestamp_time",
            "-of",
            "json",
            str(folder / "camera.mkv"),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    # Read saved-video presentation times separately from host receipt times.
    video_times = [
        float(f["best_effort_timestamp_time"])
        for f in json.loads(probe.stdout)["frames"]
    ]
    # Compare relative PTS to tolerate the container's timestamp quantization.
    mismatch = validate_video_times(video_times, frames)
    # Decode the saved video into small grayscale frames for offline analysis.
    decoded = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(folder / "camera.mkv"),
            "-map",
            "0:v:0",
            "-vf",
            f"scale={WIDTH}:{HEIGHT}",
            "-pix_fmt",
            "gray",
            "-frames:v",
            str(len(frames) + 1),
            "-fps_mode",
            "passthrough",
            "-f",
            "rawvideo",
            "-",
        ],
        capture_output=True,
        check=True,
        timeout=120,
    )
    # Reject this invalid input before it can produce misleading output.
    if len(decoded.stdout) != len(frames) * WIDTH * HEIGHT:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Decoded byte count differs from validated frame log")
    # View decoded bytes as a frame stack without changing pixel ordering.
    images = np.frombuffer(decoded.stdout, dtype=np.uint8).reshape(-1, HEIGHT, WIDTH)
    # Calculate times with array operations while preserving the documented shape.
    times = np.asarray([r["host_read_midpoint_s"] for r in imu])
    # Calculate values with array operations while preserving the documented shape.
    values = np.asarray([[r[k] for k in ("gx_dps", "gy_dps", "gz_dps")] for r in imu])
    # Subtract the independently estimated XYZ bias from all recorded gyro samples.
    values -= baseline["baseline_gyro_dps"]
    # Use the saved RECORDING cue as the experiment-relative time origin.
    cue = meta["recording_cue_host_s"]
    # Prepare/read the detailed rows that will be validated or summarized next.
    rows = []
    # Process each index in the selected collection.
    for index in range(2, len(frames)):  # explicitly exclude first startup interval
        # Select adjacent saved frame-log rows, excluding the startup pair.
        a, b = frames[index - 1], frames[index]
        # Approximate the pair's observation time using two host frame receipts.
        host_midpoint = (a["host_receipt_s"] + b["host_receipt_s"]) / 2
        # Express this pair time relative to the user-visible recording cue.
        relative = host_midpoint - cue
        # Choose the next branch using not 0 <= relative <=
        # meta['requested_seconds_after_first_frame'].
        if not 0 <= relative <= meta["requested_seconds_after_first_frame"]:
            # Skip this unusable item and look for the next eligible observation.
            continue
        # Use camera PTS separation to convert pair displacement into pixels/second.
        dt = b["camera_pts_s"] - a["camera_pts_s"]
        # Apply the same nine-patch estimator used by the live motion worker.
        shift = image_shift(images[index - 1], images[index])
        # Interpolate gyro near the host observation midpoint, not the camera exposure.
        gyro = gyro_at(host_midpoint, times, values)
        # Preserve rejected pairs too, with absent values distinguished from zero motion.
        row = dict(
            frame_index=index,
            host_after_cue_s=relative,
            camera_pts_s=b["camera_pts_s"],
            camera_interval_s=dt,
            accepted=False,
            dx_pixels=None,
            dy_pixels=None,
            horizontal_pixels_s=None,
            vertical_pixels_s=None,
            agreeing_patches=0,
            median_peak_quality=None,
            gx_dps=None,
            gy_dps=None,
            gz_dps=None,
        )
        # Choose the next branch using gyro is not None.
        if gyro is not None:
            # Add the fields produced by this step while preserving the other report fields.
            row.update(zip(("gx_dps", "gy_dps", "gz_dps"), map(float, gyro)))
        # Use this estimate only after its reliability checks accepted it.
        if shift is not None:
            # Unpack pixel displacement, agreeing patches and correlation-peak quality.
            dx, dy, count, quality = shift
            # Add the fields produced by this step while preserving the other report fields.
            row.update(
                dx_pixels=dx,
                dy_pixels=dy,
                horizontal_pixels_s=dx / dt,
                vertical_pixels_s=dy / dt,
                agreeing_patches=count,
                median_peak_quality=quality,
            )
        # Accept a pair only if both the visual estimate and gyro interpolation succeeded.
        row["accepted"] = shift is not None and gyro is not None
        # Retain this item/chunk for the current calculation or bounded history.
        rows.append(row)
    # Keep only rows where both visual displacement and gyro pairing succeeded.
    accepted = [r for r in rows if r["accepted"]]
    # Reject this invalid input before it can produce misleading output.
    if len(accepted) < 10:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Too few reliable visual/gyro pairs; inspect texture and logs")
    # Extract accepted horizontal scene speeds in pixels/second.
    visual = np.asarray([r["horizontal_pixels_s"] for r in accepted])
    # Extract paired corrected sensor-Y rates for the exploratory comparison.
    gyro_y = np.asarray([r["gy_dps"] for r in accepted])
    # Avoid impressive-looking correlations for almost motionless recordings.
    correlation = (
        float(np.corrcoef(visual, gyro_y)[0, 1])
        if min(visual.std(), gyro_y.std()) > 0.5
        else None
    )
    # Prepare one-second summaries for easier visual/gyro comparison.
    bins = []
    # Process each second in the selected collection.
    for second in range(math.ceil(meta["requested_seconds_after_first_frame"])):
        # Take the next chunk or selected subset needed by this operation.
        part = [r for r in accepted if second <= r["host_after_cue_s"] < second + 1]
        # Retain this item/chunk for the current calculation or bounded history.
        bins.append(
            dict(
                second=second,
                accepted_pairs=len(part),
                median_horizontal_pixels_s=float(
                    np.median([r["horizontal_pixels_s"] for r in part])
                )
                if part
                else None,
                median_gyro_y_dps=float(np.median([r["gy_dps"] for r in part]))
                if part
                else None,
            )
        )
    # Package measurements with settings and limitations for reproducible interpretation.
    summary = dict(
        recording=folder.name,
        analysis_resolution=[WIDTH, HEIGHT],
        numpy_version=np.__version__,
        comparison="Host receipt midpoint pairing; no fitted time shift",
        baseline_gyro_dps=baseline["baseline_gyro_dps"],
        baseline_window_after_cue_s=[0, 1],
        video_log_max_relative_pts_difference_s=mismatch,
        compared_pairs=len(rows),
        accepted_pairs=len(accepted),
        rejected_pairs=len(rows) - len(accepted),
        median_abs_horizontal_pixels_s=float(np.median(np.abs(visual))),
        p95_abs_horizontal_pixels_s=float(np.percentile(np.abs(visual), 95)),
        horizontal_vs_gyro_y_correlation=correlation,
        per_second=bins,
        limitations="Patch translation is not camera rotation. Moving objects/parallax can affect motion. Correlation is exploratory, not measured synchronization or angle calibration.",
    )
    # Return the documented result to the caller without starting another operation.
    return summary, rows


def main() -> None:
    """Analyze one recorded clip and save comparison JSON/CSV to a new directory.

    Args:
        None.

    Returns:
        None: argparse reports read/analysis failures without overwriting previous
            results.
    """
    # Define the command-line interface without starting hardware work yet.
    parser = argparse.ArgumentParser(description=__doc__)
    # Declare folder with its existing default, validation and help text.
    parser.add_argument("folder", type=Path)
    # Declare --output with its existing default, validation and help text.
    parser.add_argument(
        "--output", type=Path, required=True, help="new directory under recordings/"
    )
    # Parse command-line values into the namespace used by this operation.
    args = parser.parse_args()
    # Choose the next branch using args.output.exists() or not
    # args.output.resolve().is_relative_to(Path('re....
    if args.output.exists() or not args.output.resolve().is_relative_to(
        Path("recordings").resolve()
    ):
        # Call parser.error for this step; its contract describes the result or side effect.
        parser.error("choose a new output directory under recordings/, from repo root")
    # Choose the next branch using not all((shutil.which(name) for name in ('ffmpeg',
    # 'ffprobe'))).
    if not all(shutil.which(name) for name in ("ffmpeg", "ffprobe")):
        # Call parser.error for this step; its contract describes the result or side effect.
        parser.error("existing ffmpeg and ffprobe are required")
    # Keep failure handling alongside the operation so cleanup/status remains explicit.
    try:
        # Separate the aggregate report from detailed per-frame comparison measurements.
        summary, rows = inspect_recording(args.folder)
        # Create the explicit output/test directory using the existing overwrite policy.
        args.output.mkdir(parents=True, exist_ok=False)
        # Persist this explicitly requested local output; raw artifacts stay outside Git.
        (args.output / "summary.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n"
        )
        # Keep these resources scoped so they are released even if the operation fails.
        with (args.output / "motion.csv").open("w", newline="") as handle:
            # Serialize named measurements as CSV rather than conflating them with image bytes.
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            # Write the documented CSV fields in a reproducible column order.
            writer.writeheader()
            # Write the documented CSV fields in a reproducible column order.
            writer.writerows(rows)
        # Explain the current result, progress or failure in the terminal.
        print(json.dumps(summary, indent=2, allow_nan=False))
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        # Call parser.exit for this step; its contract describes the result or side effect.
        parser.exit(1, f"Visual analysis failed: {error}\n")


# Run the command only when executed directly, not when imported by tests or another module.
if __name__ == "__main__":
    # Call main for this step; its contract describes the result or side effect.
    main()
