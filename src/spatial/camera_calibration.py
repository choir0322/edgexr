"""Fit screen-checkerboard camera intrinsics from a recorded 720p video."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any

import cv2 as cv
import numpy as np

BOARD = (9, 6)  # Interior corners: the displayed board has 10x7 squares.
IMAGE_SIZE = (1280, 720)


def board_points() -> np.ndarray:
    """Create planar, equally spaced board coordinates in arbitrary square units.

    Args: None.
    Returns:
        np.ndarray: 54x3 float32 points; one unit equals one displayed square.
    """
    points = np.zeros((BOARD[0] * BOARD[1], 3), dtype=np.float32)
    points[:, :2] = np.mgrid[0:BOARD[0], 0:BOARD[1]].T.reshape(-1, 2)
    return points


def reprojection_rms(corners: np.ndarray, projected: np.ndarray) -> float:
    """Measure RMS two-dimensional image residual per corner in pixels.

    Args:
        corners (np.ndarray): Observed Nx1x2 or Nx2 image coordinates.
        projected (np.ndarray): Corresponding predicted pixel coordinates.
    Returns:
        float: Square root of mean squared Euclidean distances in pixels.
    """
    difference = np.asarray(corners).reshape(-1, 2) - np.asarray(projected).reshape(-1, 2)
    return float(np.sqrt(np.mean(np.sum(difference * difference, axis=1))))


def fit_observations(observations: list[dict[str, Any]], image_size: tuple[int, int]) -> dict[str, Any]:
    """Fit a pinhole model and assess unseen board poses with fixed intrinsics.

    Args:
        observations (list[dict[str, Any]]): Ordered successful detections containing
            `sample_index`, `time_s` and `corners` as 54x1x2 float32 pixels.
        image_size (tuple[int, int]): Camera width and height in pixels.
    Returns:
        dict[str, Any]: Calibration, per-view errors and diagnostics; not acceptance proof.
    """
    if len(observations) < 15:
        raise ValueError(f"Need at least 15 detected frames; found {len(observations)}")
    training = [item for i, item in enumerate(observations) if i % 5 != 4]
    heldout = [item for i, item in enumerate(observations) if i % 5 == 4]
    if len(training) < 12 or len(heldout) < 3:
        raise ValueError("Need at least 12 training and 3 held-out views")
    obj = board_points()
    rms, matrix, distortion, rotations, translations = cv.calibrateCamera(
        [obj.copy() for _ in training], [item["corners"] for item in training], image_size, None, None)
    if not math.isfinite(float(rms)) or not np.isfinite(matrix).all() or not np.isfinite(distortion).all():
        raise ValueError("Calibration produced non-finite values")
    fit_errors = []
    for item, rotation, translation in zip(training, rotations, translations):
        projected, _ = cv.projectPoints(obj, rotation, translation, matrix, distortion)
        fit_errors.append({"sample_index": item["sample_index"], "time_s": item["time_s"],
                           "rms_px": reprojection_rms(item["corners"], projected)})
    heldout_errors = []
    for item in heldout:
        ok, rotation, translation = cv.solvePnP(obj, item["corners"], matrix, distortion)
        error = None
        if ok:
            projected, _ = cv.projectPoints(obj, rotation, translation, matrix, distortion)
            error = reprojection_rms(item["corners"], projected)
        heldout_errors.append({"sample_index": item["sample_index"], "time_s": item["time_s"],
                               "rms_px": error})
    centers = np.array([item["corners"].reshape(-1, 2).mean(axis=0) for item in observations])
    extent = (centers.max(axis=0) - centers.min(axis=0)) / np.asarray(image_size)
    coverage = []
    for item in observations:
        points = item["corners"].reshape(-1, 2)
        low, high = points.min(axis=0), points.max(axis=0)
        coverage.append({"sample_index": item["sample_index"], "time_s": item["time_s"],
                         "center_xy_px": points.mean(axis=0).tolist(),
                         "bounds_xyxy_px": [*low.tolist(), *high.tolist()]})
    warnings = []
    if extent[0] < 0.25 or extent[1] < 0.20:
        warnings.append("Board centers cover a narrow part of the image; add edge positions.")
    if not (0.1 * image_size[0] < matrix[0, 0] < 10 * image_size[0] and
            0.1 * image_size[1] < matrix[1, 1] < 10 * image_size[1]):
        warnings.append("Estimated focal length is implausible for a typical camera; inspect the fit.")
    if any(item["rms_px"] is None for item in heldout_errors):
        warnings.append("At least one held-out board pose could not be solved.")
    return {"camera_matrix": matrix.tolist(), "distortion_coefficients": distortion.ravel().tolist(),
            "image_size_wh": list(image_size), "board_inner_corners_wh": list(BOARD),
            "board_square_units": "one screen square; physical size unknown",
            "opencv_training_rms_px": float(rms), "training_views": fit_errors,
            "heldout_views": heldout_errors,
            "board_center_span_fraction_xy": extent.tolist(), "detected_board_coverage": coverage,
            "warnings": warnings,
            "status": "needs_review",
            "limits": "Held-out intrinsics are fixed but each held-out board pose is fitted using that same image. Adjacent video views can be correlated. Reprojection error alone does not validate distortion or 3D accuracy; inspect image coverage, tilts, flicker and outliers."}


def analyze_video(video: Path, output: Path, interval: float) -> dict[str, Any]:
    """Extract evenly spaced frames to temporary storage and detect the target.

    Args:
        video (Path): Existing camera recording; never modified.
        output (Path): New JSON path; never overwritten.
        interval (float): Positive seconds between sampled frames.
    Returns:
        dict[str, Any]: Written calibration report; failures leave no output JSON.
    """
    if not video.is_file():
        raise ValueError(f"Video not found: {video}")
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    if not math.isfinite(interval) or not 1 <= interval <= 30:
        raise ValueError("Interval must be between 1 and 30 seconds")
    started = time.monotonic()
    observations = []
    sampled = 0
    with tempfile.TemporaryDirectory(prefix="edgexr-camera-calibration-") as temp:
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(video),
                   "-vf", f"fps=1/{interval}", "-vsync", "0", str(Path(temp) / "frame-%05d.png")]
        subprocess.run(command, check=True)
        frames = sorted(Path(temp).glob("frame-*.png"))
        for index, path in enumerate(frames):
            gray = cv.imread(str(path), cv.IMREAD_GRAYSCALE)
            if gray is None or (gray.shape[1], gray.shape[0]) != IMAGE_SIZE:
                raise ValueError("Expected every decoded image to be 1280x720 grayscale")
            sampled += 1
            found, corners = cv.findChessboardCorners(gray, BOARD)
            if found:
                refined = cv.cornerSubPix(gray, corners, (5, 5), (-1, -1),
                                          (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001))
                observations.append({"sample_index": index, "time_s": (index + 0.5) * interval,
                                     "corners": refined})
            if (index + 1) % 10 == 0:
                print(f"Checked {index + 1}/{len(frames)} sampled frames; found {len(observations)} boards.", flush=True)
    report = fit_observations(observations, IMAGE_SIZE)
    report.update(source_video=str(video), sample_interval_s=interval, sampled_frames=sampled,
                  detected_frames=len(observations), opencv_version=cv.__version__,
                  elapsed_wall_s=time.monotonic() - started,
                  sample_time_scope="approximate fps-filter output midpoint; not sensor exposure time")
    with output.open("x", encoding="utf-8") as file:
        json.dump(report, file, indent=2, allow_nan=False)
        file.write("\n")
    return report


def main() -> int:
    """Parse input/output paths and run a read-only-video offline calibration.

    Args: None.
    Returns:
        int: Zero if a review-needed report was written, one on failure.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    try:
        report = analyze_video(args.video, args.output, args.interval)
    except (ValueError, OSError, subprocess.CalledProcessError, cv.error) as error:
        print(f"Calibration failed: {error}")
        return 1
    print(json.dumps(report, indent=2, allow_nan=False))
    print(f"Saved {args.output}; status needs_review is not an accuracy pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
