"""Print OpenCV reference values for the camera-geometry learning page check.

Run with any Python that has OpenCV and NumPy (not a project dependency):
    python scripts/learning_geometry_fixtures.py > /tmp/geometry-fixtures.json
The output is pasted into scripts/check_learning_pages.js so the browser
arithmetic in docs/learning/camera-geometry-math.js is compared with
cv.undistortPoints (default five iterations) and cv.projectPoints. Reads only the
committed calibration summary; writes nothing.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2 as cv
import numpy as np

CALIBRATION = Path(__file__).resolve().parents[1] / "benchmarks/results/camera-calibration-screen-01.json"
PIXELS = [(640, 360), (900, 300), (100, 600), (1279, 330.78), (0, 330.78),
          (670.33, 0), (670.33, 719), (1100, 650), (300, 120)]
BEARINGS = [(0.0, 0.0), (15.0, 0.0), (-30.0, 10.0), (35.0, -20.0), (-5.0, 22.0)]


def main() -> int:
    """Compute undistorted rays, bearings and projections for fixed inputs.

    Args: None.
    Returns:
        int: Zero after printing one JSON object to standard output.
    """
    config = json.loads(CALIBRATION.read_text())
    matrix = np.asarray(config["camera_matrix"], dtype=float)
    distortion = np.asarray(config["distortion_k1_k2_p1_p2_k3"], dtype=float)

    # Pixel -> ideal normalized point -> bearing, exactly as OpenCV defaults do.
    pixels = np.asarray(PIXELS, dtype=float)
    ideal = cv.undistortPoints(pixels[:, None], matrix, distortion).reshape(-1, 2)
    forward = []
    for (u, v), (x, y) in zip(PIXELS, ideal):
        forward.append({"pixel": [u, v], "ideal": [float(x), float(y)],
                        "yaw": math.degrees(math.atan2(x, 1.0)),
                        "pitch": math.degrees(math.atan2(-y, math.hypot(x, 1.0)))})

    # Bearing -> ray at unit depth -> distorted pixel.
    reverse = []
    for yaw, pitch in BEARINGS:
        a, b = math.radians(yaw), math.radians(pitch)
        ray = np.array([[math.tan(a), -math.tan(b) / math.cos(a), 1.0]])
        pixel, _ = cv.projectPoints(ray, np.zeros(3), np.zeros(3), matrix, distortion)
        reverse.append({"yaw": yaw, "pitch": pitch, "pixel": pixel.reshape(2).tolist()})

    print(json.dumps({"opencv": cv.__version__, "pixel_to_bearing": forward,
                      "bearing_to_pixel": reverse}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
