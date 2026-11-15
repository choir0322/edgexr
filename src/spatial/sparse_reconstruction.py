"""Reconstruct a provisional two-view sparse cloud from a calibrated recording."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import time
from typing import Any

import cv2 as cv
import numpy as np


def reconstruct(a: np.ndarray, b: np.ndarray, matrix: np.ndarray,
                distortion: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    """Estimate geometry from corresponding distorted image coordinates.

    Args:
        a (np.ndarray): Nx2 first-view pixel coordinates.
        b (np.ndarray): Nx2 matching second-view pixel coordinates.
        matrix (np.ndarray): 3x3 calibrated intrinsic matrix.
        distortion (np.ndarray): OpenCV lens distortion coefficients.
    Returns:
        tuple: Accepted Nx3 points in camera-one coordinates and diagnostics.
    """
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.shape != b.shape or a.ndim != 2 or a.shape[1] != 2 or len(a) < 30:
        raise ValueError("Need at least 30 matching Nx2 image coordinates")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Image coordinates must be finite")
    # Remove lens distortion before fitting epipolar geometry in normalized rays.
    na = cv.undistortPoints(a[:, None], matrix, distortion).reshape(-1, 2)
    nb = cv.undistortPoints(b[:, None], matrix, distortion).reshape(-1, 2)
    cv.setRNGSeed(0)
    essential, mask = cv.findEssentialMat(
        na, nb, np.eye(3), method=cv.RANSAC, prob=0.999,
        threshold=1.5 / float((matrix[0, 0] + matrix[1, 1]) / 2))
    if essential is None or essential.shape != (3, 3) or mask is None:
        raise ValueError("No unique essential matrix; choose a different pair")
    essential_count = int(np.count_nonzero(mask))
    _, rotation, translation, mask = cv.recoverPose(
        essential, na, nb, np.eye(3), mask=mask)
    selected = mask.ravel() != 0
    if np.count_nonzero(selected) < 30:
        raise ValueError("Too few positive-depth pose inliers; translation may be insufficient")

    # Triangulate rays, then measure depth, parallax and distorted-pixel residuals.
    homogeneous = cv.triangulatePoints(np.eye(3, 4),
        np.column_stack((rotation, translation)), na[selected].T, nb[selected].T)
    with np.errstate(divide="ignore", invalid="ignore"):
        points = (homogeneous[:3] / homogeneous[3]).T
    finite = np.isfinite(points).all(axis=1)
    points = points[finite]
    aa, bb = a[selected][finite], b[selected][finite]
    second = points @ rotation.T + translation.ravel()
    center = -rotation.T @ translation.ravel()
    ray1, ray2 = points, points - center
    cosine = np.sum(ray1 * ray2, axis=1) / (
        np.linalg.norm(ray1, axis=1) * np.linalg.norm(ray2, axis=1))
    angles = np.degrees(np.arccos(np.clip(cosine, -1, 1)))
    pa, _ = cv.projectPoints(points, np.zeros(3), np.zeros(3), matrix, distortion)
    pb, _ = cv.projectPoints(points, cv.Rodrigues(rotation)[0], translation, matrix, distortion)
    error = np.maximum(np.linalg.norm(pa.reshape(-1, 2) - aa, axis=1),
                       np.linalg.norm(pb.reshape(-1, 2) - bb, axis=1))
    keep = (points[:, 2] > 0) & (second[:, 2] > 0) & (angles >= 1.0) & (error <= 2.0)
    count = int(np.count_nonzero(keep))
    # A tiny cluster of matches is poor evidence for reconstructing the scene.
    support = []
    vertical_support = []
    for pixels in (aa[keep], bb[keep]):
        quadrants = set((int(x >= matrix[0, 2]), int(y >= matrix[1, 2])) for x, y in pixels)
        support.append(len(quadrants))
        vertical_support.append({"above": int(np.count_nonzero(pixels[:, 1] < matrix[1, 2])),
                                 "below": int(np.count_nonzero(pixels[:, 1] >= matrix[1, 2]))})
    minimum_per_half = max(10, math.ceil(0.2 * count))
    vertical_ok = all(min(item.values()) >= minimum_per_half for item in vertical_support)
    report = {"correspondences": len(a), "essential_inliers": essential_count,
              "pose_inliers": int(np.count_nonzero(selected)), "accepted_points": count,
              "rejected_after_triangulation": int(np.count_nonzero(selected)) - count,
              "minimum_parallax_deg": 1.0, "maximum_per_view_error_px": 2.0,
              "minimum_accepted_points": 30,
              "occupied_principal_point_quadrants": support,
              "minimum_occupied_quadrants_each_view": 3,
              "vertical_half_support": vertical_support,
              "minimum_vertical_half_points": minimum_per_half,
              "minimum_vertical_half_fraction": 0.2,
              "median_parallax_deg": float(np.median(angles[keep])) if count else None,
              "median_max_reprojection_px": float(np.median(error[keep])) if count else None,
              "p95_max_reprojection_px": float(np.percentile(error[keep], 95)) if count else None,
              "camera_1_world_to_camera": np.eye(4).tolist(),
              "camera_2_world_to_camera": np.vstack((np.column_stack((rotation, translation)),
                                                     [0, 0, 0, 1])).tolist(),
              "camera_2_center": center.tolist(),
              "status": "candidate_needs_review" if count >= 30 and min(support) >= 3 and vertical_ok else "rejected"}
    if report["status"] == "rejected":
        report["reason"] = ("Insufficient vertical point coverage in the scene"
                            if not vertical_ok else
                            "Too few triangulated points or insufficient spatial distribution")
    return points[keep], report


def extract_frame(video: Path, seconds: float) -> np.ndarray:
    """Decode one full-resolution grayscale frame without temporary image files.

    Args:
        video (Path): Source video.
        seconds (float): Requested position on the video timeline, not exposure time.
    Returns:
        np.ndarray: Decoded uint8 grayscale image.
    """
    result = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", str(seconds),
        "-i", str(video), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        check=True, capture_output=True)
    gray = cv.imdecode(np.frombuffer(result.stdout, np.uint8), cv.IMREAD_GRAYSCALE) if result.stdout else None
    if gray is None:
        raise ValueError(f"No frame at {seconds} seconds")
    return gray


def run(video: Path, calibration: Path, output: Path,
        first: float, second: float) -> dict[str, Any]:
    """Match ORB features, reconstruct and save auditable local artifacts.

    Args:
        video (Path): Input recording.
        calibration (Path): Existing candidate calibration JSON.
        output (Path): New output directory; never overwritten.
        first (float): First requested video position in seconds.
        second (float): Later requested video position in seconds.
    Returns:
        dict: Report including rejection, provenance and elapsed analysis time.
    """
    if not np.isfinite([first, second]).all() or not 0 <= first < second:
        raise ValueError("Require finite times: 0 <= first < second")
    if not video.is_file():
        raise ValueError("Input video does not exist")
    raw = calibration.read_bytes()
    config = json.loads(raw)
    matrix = np.asarray(config["camera_matrix"], dtype=float)
    distortion = np.asarray(config["distortion_coefficients"], dtype=float)
    if (matrix.shape != (3, 3) or not np.isfinite(matrix).all()
            or matrix[0, 0] <= 0 or matrix[1, 1] <= 0
            or distortion.size not in (4, 5, 8, 12, 14) or not np.isfinite(distortion).all()):
        raise ValueError("Invalid camera intrinsics or distortion")
    output.mkdir(parents=True, exist_ok=False)
    started, cpu_started = time.perf_counter(), time.process_time()
    cv.setNumThreads(2)
    report: dict[str, Any] = {"status": "rejected", "source_video": str(video),
        "calibration": str(calibration), "calibration_sha256": hashlib.sha256(raw).hexdigest(),
        "calibration_status": config.get("status"), "requested_video_seconds": [first, second],
        "opencv_version": cv.__version__, "host": platform.platform(),
        "opencv_threads": 2, "orb_max_features": 3000, "descriptor_ratio": 0.75,
        "scope": "Two-view candidate; arbitrary scale with unit camera baseline. Camera one is the reference, X right/Y down/Z forward. No IMU fusion, bundle adjustment, independent accuracy validation or metric distance. Pure rotation and planar scenes can be degenerate; gates are not proof of reconstruction accuracy."}
    try:
        images = [extract_frame(video, position) for position in (first, second)]
        for index, gray in enumerate(images):
            if list(gray.shape[::-1]) != config["image_size_wh"]:
                raise ValueError("Decoded image size differs from calibration; do not resize")
            if not cv.imwrite(str(output / f"view-{index + 1}.png"), gray):
                raise OSError("Could not save selected frame")
        orb = cv.ORB_create(nfeatures=3000)
        ka, da = orb.detectAndCompute(images[0], None)
        kb, db = orb.detectAndCompute(images[1], None)
        if da is None or db is None or min(len(da), len(db)) < 2:
            raise ValueError("Too few textured features")
        # Require a distinctive descriptor and mutual best match to avoid duplicate claims.
        matcher = cv.BFMatcher(cv.NORM_HAMMING)
        reverse = matcher.match(db, da)
        reverse_best = {m.queryIdx: m.trainIdx for m in reverse}
        matches = [pair[0] for pair in matcher.knnMatch(da, db, k=2)
                   if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance
                   and reverse_best.get(pair[0].trainIdx) == pair[0].queryIdx]
        a = np.array([ka[m.queryIdx].pt for m in matches], dtype=float).reshape(-1, 2)
        b = np.array([kb[m.trainIdx].pt for m in matches], dtype=float).reshape(-1, 2)
        report.update(keypoints=[len(ka), len(kb)], descriptor_matches=len(matches))
        points, geometry = reconstruct(a, b, matrix, distortion)
        report.update(geometry)
        if report["status"] == "candidate_needs_review":
            # Plain ASCII PLY loads in point-cloud software; no implied meters or surface mesh.
            with (output / "points.ply").open("x") as stream:
                stream.write(f"ply\nformat ascii 1.0\nelement vertex {len(points)}\n"
                             "property float x\nproperty float y\nproperty float z\nend_header\n")
                np.savetxt(stream, points, fmt="%.8g")
    except (ValueError, cv.error) as error:
        report.update(status="rejected", reason=str(error))
    report.update(elapsed_wall_s=time.perf_counter() - started,
                  python_process_cpu_s=time.process_time() - cpu_started,
                  timing_scope="One offline run; Python CPU excludes FFmpeg subprocess. Includes image I/O; not live workload CPU, peak memory or energy.")
    with (output / "report.json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return report


def main() -> int:
    """Parse the selected pair and report success or actionable rejection.

    Args: None.
    Returns:
        int: Zero for reviewable candidate, one for rejection or input failure.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--first-seconds", type=float, default=5)
    parser.add_argument("--second-seconds", type=float, default=15)
    args = parser.parse_args()
    try:
        report = run(args.video, args.calibration, args.output, args.first_seconds, args.second_seconds)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError, cv.error) as error:
        print(f"Reconstruction failed: {error}")
        return 1
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "candidate_needs_review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
