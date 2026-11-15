"""Build small derived teaching evidence from private Pi sparse trial outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
import cv2 as cv
import numpy as np


def build_trial(root: Path, number: int, calibration: dict[str, Any]) -> dict[str, Any]:
    """Project original Pi points and regenerate descriptor matches for teaching.

    Args:
        root (Path): Desktop containing original private trial folders.
        number (int): Trial number, one or two.
        calibration (dict): Intrinsics and distortion from screen calibration.
    Returns:
        dict: Derived pixels, sampled geometry, association caveats and summary.
    """
    folder = root / f"sparse-scene-{number:02d}-pair-05-15"
    report = json.loads((folder / "report.json").read_text())
    lines = (folder / "points.ply").read_text().splitlines()
    points = np.array([[float(v) for v in line.split()] for line in lines[lines.index("end_header") + 1:]])
    matrix = np.array(calibration["camera_matrix"])
    distortion = np.array(calibration["distortion_coefficients"])
    pose = np.array(report["camera_2_world_to_camera"])
    rvec = cv.Rodrigues(pose[:3, :3])[0]
    p1 = cv.projectPoints(points, np.zeros(3), np.zeros(3), matrix, distortion)[0].reshape(-1, 2)
    p2 = cv.projectPoints(points, rvec, pose[:3, 3], matrix, distortion)[0].reshape(-1, 2)
    images = [cv.imread(str(folder / f"view-{i}.png"), 0) for i in (1, 2)]
    if any(image is None or image.shape != (720, 1280) for image in images):
        raise ValueError(f"{folder}: requires original 1280x720 snapshots")
    orb = cv.ORB_create(nfeatures=3000)
    features = [orb.detectAndCompute(image, None) for image in images]
    matcher = cv.BFMatcher(cv.NORM_HAMMING)
    reverse = {m.queryIdx: m.trainIdx for m in matcher.match(features[1][1], features[0][1])}
    matches = [pair[0] for pair in matcher.knnMatch(features[0][1], features[1][1], k=2)
               if len(pair) == 2 and pair[0].distance < .75 * pair[1].distance
               and reverse.get(pair[0].trainIdx) == pair[0].queryIdx]
    a = np.array([features[0][0][m.queryIdx].pt for m in matches])
    b = np.array([features[1][0][m.trainIdx].pt for m in matches])
    if not matches:
        raise ValueError(f"{folder}: no paired matches for teaching evidence")
    # Original exports lack feature IDs. Recover only unambiguous nearby paired observations.
    associations = []
    for i in range(len(points)):
        distances = np.maximum(np.linalg.norm(a - p1[i], axis=1), np.linalg.norm(b - p2[i], axis=1))
        candidates = np.flatnonzero(distances <= 2.0)
        if len(candidates) == 1:
            j = int(candidates[0])
            associations.append({"id": i, "xyz": points[i].tolist(), "projected": [p1[i].tolist(), p2[i].tolist()],
                                 "observed": [a[j].tolist(), b[j].tolist()],
                                 "residual_px": [float(np.linalg.norm(a[j]-p1[i])), float(np.linalg.norm(b[j]-p2[i]))]})
    # Evenly sample the eligible points; include all 2D projections for coverage.
    if not associations:
        raise ValueError(f"{folder}: no unambiguous point associations")
    chosen = np.linspace(0, len(associations)-1, min(48, len(associations)), dtype=int)
    sv = np.linalg.svd(points - points.mean(axis=0), compute_uv=False)
    return {"name": f"Scene {number:02d}", "folder": folder.name,
            "report": report, "matrix": matrix.tolist(), "distortion": distortion.tolist(),
            "turn_deg": float(np.linalg.norm(rvec) * 180 / np.pi),
            "camera_center": report["camera_2_center"], "camera_forward": (pose[:3,:3].T @ [0,0,1]).tolist(),
            "projections": [p1.tolist(), p2.tolist()],
            "keypoints": [[list(k.pt) for k in feat[0][::20]] for feat in features],
            "matches": [[x.tolist(), y.tolist()] for x,y in zip(a[::max(1,len(a)//60)], b[::max(1,len(b)//60)])],
            "samples": [associations[i] for i in chosen],
            "association_count": len(associations), "regenerated_matches": len(matches),
            "depth_quantiles": np.percentile(points[:,2],[5,50,95]).tolist(),
            "shape_singular_values": sv.tolist(),
            "image_third_counts": [int(np.count_nonzero((p1[:,1]>=lo)&(p1[:,1]<hi))) for lo,hi in [(0,240),(240,480),(480,720)]],
            "limits": "Original Pi cloud projected with original pose/calibration. ORB observations are regenerated on Mac and associated only if exactly one paired match lies within 2px in both views. Original feature IDs were not saved. Lines are thinned; 48 or fewer 3D points are teaching samples, not the full cloud. No metric scale or ground truth."}


def main() -> None:
    """Write browser-loadable evidence without embedding private photographs.

    Args: None.
    Returns: None.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    calibration_path = args.root / "camera-calibration-screen-01/calibration.json"
    calibration = json.loads(calibration_path.read_text())
    calibration_hash = hashlib.sha256(calibration_path.read_bytes()).hexdigest()
    for number in (1, 2):
        report_path = args.root / f"sparse-scene-{number:02d}-pair-05-15/report.json"
        if json.loads(report_path.read_text())["calibration_sha256"] != calibration_hash:
            raise ValueError(f"Calibration does not match {report_path}")
    trials = [build_trial(args.root, number, calibration) for number in (1,2)]
    args.output.write_text("window.SPARSE_EVIDENCE = " + json.dumps(trials, separators=(",",":"), allow_nan=False) + ";\n")
    for trial in trials:
        print(trial["name"], "associations", trial["association_count"], "image thirds", trial["image_third_counts"],
              "depth quantiles", trial["depth_quantiles"], "turn", trial["turn_deg"])


if __name__ == "__main__":
    main()
