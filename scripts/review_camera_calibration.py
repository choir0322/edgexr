"""Review screen-target calibration recordings jointly and across sessions.

Run on the Mac (needs OpenCV/NumPy, not project dependencies), for example:
    PYTHONPATH=src python scripts/review_camera_calibration.py \
        ~/Desktop/camera-calibration-screen-02/camera.mkv \
        ~/Desktop/camera-calibration-screen-03/camera.mkv --output review.json
Detection matches spatial.camera_calibration (every 2 s, 9x6 corners, subpixel).
For the free 5-coefficient model and for k3 fixed at zero it reports: each
recording's fit tested on the other recording, a joint fit with every fifth view
held out, interleaved-half focal lengths, the lens-polynomial fold radius,
image-corner round trips and image coverage. Reads videos; writes only --output.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

import cv2 as cv
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from spatial.camera_calibration import BOARD, IMAGE_SIZE, board_points  # noqa: E402

CORNERS = [(0, 0), (1279, 0), (0, 719), (1279, 719)]


def detect(video: Path, interval: float = 2.0) -> list[np.ndarray]:
    """Find refined 9x6 board corners in frames sampled from one recording.

    Args:
        video (Path): Calibration recording.
        interval (float): Seconds between sampled frames, as on the Pi.
    Returns:
        list[np.ndarray]: 54x1x2 float32 corner arrays for detected boards.
    """
    found_views = []
    with tempfile.TemporaryDirectory() as temp:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(video),
                        "-vf", f"fps=1/{interval}", "-vsync", "0", f"{temp}/f-%05d.png"], check=True)
        for path in sorted(Path(temp).glob("f-*.png")):
            gray = cv.imread(str(path), cv.IMREAD_GRAYSCALE)
            ok, corners = cv.findChessboardCorners(gray, BOARD)
            if ok:
                found_views.append(cv.cornerSubPix(gray, corners, (5, 5), (-1, -1),
                    (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)))
    return found_views


def fit(views: list[np.ndarray], flags: int) -> tuple[float, np.ndarray, np.ndarray]:
    """Fit intrinsics and distortion to board views.

    Args:
        views (list[np.ndarray]): Detected corner arrays.
        flags (int): OpenCV calibration flags (0 or CALIB_FIX_K3).
    Returns:
        tuple[float, np.ndarray, np.ndarray]: RMS px, 3x3 matrix, 5 distortion coefficients.
    """
    obj = board_points()
    rms, matrix, distortion, _, _ = cv.calibrateCamera([obj.copy() for _ in views], views,
                                                       IMAGE_SIZE, None, None, flags=flags)
    return float(rms), matrix, distortion.ravel()


def errors(matrix: np.ndarray, distortion: np.ndarray, views: list[np.ndarray]) -> dict[str, float]:
    """Per-view RMS error of unseen views with intrinsics held fixed.

    Args:
        matrix (np.ndarray): Camera matrix.
        distortion (np.ndarray): Distortion coefficients.
        views (list[np.ndarray]): Views not used for fitting.
    Returns:
        dict[str, float]: Median, 95th percentile and maximum in pixels.
    """
    obj, values = board_points(), []
    for corners in views:
        _, rotation, translation = cv.solvePnP(obj, corners, matrix, distortion)
        projected, _ = cv.projectPoints(obj, rotation, translation, matrix, distortion)
        values.append(math.sqrt(float(np.mean(np.sum((projected.reshape(-1, 2) - corners.reshape(-1, 2)) ** 2, 1)))))
    array = np.array(values)
    return {"median": float(np.median(array)), "p95": float(np.percentile(array, 95)), "max": float(array.max())}


def fold_radius(distortion: np.ndarray) -> float | None:
    """Distorted normalized radius where the radial polynomial stops increasing.

    Args:
        distortion (np.ndarray): k1, k2, p1, p2, k3.
    Returns:
        float | None: Fold radius, or None if monotonic up to ideal radius 2.
    """
    k1, k2, k3 = distortion[0], distortion[1], distortion[4]
    r = np.linspace(0, 2, 200001)
    falling = 1 + 3 * k1 * r**2 + 5 * k2 * r**4 + 7 * k3 * r**6 <= 0
    if not falling.any():
        return None
    x = r[int(np.argmax(falling))]
    return float(x * (1 + k1 * x**2 + k2 * x**4 + k3 * x**6))


def corner_round_trips(matrix: np.ndarray, distortion: np.ndarray) -> list[float]:
    """Undistort each image corner (OpenCV default) and project it back.

    Args:
        matrix (np.ndarray): Camera matrix.
        distortion (np.ndarray): Distortion coefficients.
    Returns:
        list[float]: Pixel error for top-left, top-right, bottom-left, bottom-right.
    """
    result = []
    for u, v in CORNERS:
        x, y = cv.undistortPoints(np.array([[[u, v]]], float), matrix, distortion).reshape(2)
        back, _ = cv.projectPoints(np.array([[x, y, 1.0]]), np.zeros(3), np.zeros(3), matrix, distortion)
        result.append(float(np.linalg.norm(back.reshape(2) - [u, v])))
    return result


def coverage(views: list[np.ndarray]) -> dict[str, Any]:
    """Board-centre span and closest detected corner to each image corner.

    Args:
        views (list[np.ndarray]): Detected corner arrays.
    Returns:
        dict[str, Any]: Span fractions (x, y) and distances in pixels.
    """
    points = np.concatenate([v.reshape(-1, 2) for v in views])
    centres = np.array([v.reshape(-1, 2).mean(axis=0) for v in views])
    span = (centres.max(axis=0) - centres.min(axis=0)) / np.array(IMAGE_SIZE)
    return {"centre_span_fraction_xy": span.tolist(),
            "closest_point_to_corner_px": [float(np.min(np.hypot(*(points - c).T))) for c in CORNERS]}


def main() -> int:
    """Review two or more recordings and write one JSON summary.

    Args: None.
    Returns:
        int: Zero after writing the summary.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("videos", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sessions = {video.parent.name: detect(video) for video in args.videos}
    combined = [view for views in sessions.values() for view in views]
    report: dict[str, Any] = {"opencv": cv.__version__, "views": {k: len(v) for k, v in sessions.items()},
                              "coverage": {**{k: coverage(v) for k, v in sessions.items()}, "joint": coverage(combined)},
                              "models": {}}
    for name, flags in (("free_k1_k2_p1_p2_k3", 0), ("k3_fixed_zero", cv.CALIB_FIX_K3)):
        # Each session's model tested on every other session's views.
        cross = {}
        for train_name, train_views in sessions.items():
            _, matrix, distortion = fit(train_views, flags)
            for test_name, test_views in sessions.items():
                if test_name != train_name:
                    cross[f"{train_name} -> {test_name}"] = {"fx": float(matrix[0, 0]), **errors(matrix, distortion, test_views)}
        training = [v for i, v in enumerate(combined) if i % 5 != 4]
        heldout = [v for i, v in enumerate(combined) if i % 5 == 4]
        rms, matrix, distortion = fit(training, flags)
        half_a = fit(combined[0::2], flags)[1][0, 0]
        half_b = fit(combined[1::2], flags)[1][0, 0]
        report["models"][name] = {
            "cross_session": cross, "joint_training_rms_px": rms,
            "camera_matrix": matrix.tolist(), "distortion_k1_k2_p1_p2_k3": distortion.tolist(),
            "joint_heldout_px": errors(matrix, distortion, heldout),
            "interleaved_half_fx": [float(half_a), float(half_b)],
            "interleaved_half_fx_difference_pct": float(100 * abs(half_a - half_b) / ((half_a + half_b) / 2)),
            "fold_distorted_radius": fold_radius(distortion),
            "corner_round_trip_px_tl_tr_bl_br": corner_round_trips(matrix, distortion)}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=1)
        stream.write("\n")
    print(json.dumps(report["models"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
