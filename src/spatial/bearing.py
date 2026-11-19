"""Convert detection boxes into bearings: directions from the head's start pose.

A bearing combines two estimates. Calibration turns a pixel into a viewing ray in
the camera's own frame (x right, y down, z forward). The gyro quaternion paired
with the frame's host receipt time rotates that ray into the reference frame of
the still start. Yaw/pitch are reported in degrees (yaw right-positive, pitch
up-positive). This is a direction only: no distance, position or world heading.
Receipt time is not exposure time, so a turning head adds error of roughly
turn rate x unknown camera latency; the trial measures it.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Sequence

from spatial.relative_orientation import quaternion_product
from spatial.view_map import orientation_context


@dataclass(frozen=True)
class CameraModel:
    """Pinhole intrinsics, OpenCV 5-coefficient distortion and measured-support cells."""

    fx: float
    fy: float
    cx: float
    cy: float
    k1: float
    k2: float
    p1: float
    p2: float
    k3: float
    width: int
    height: int
    cell_px: int
    support: tuple[str, ...]


def load_camera_model(path: Path) -> CameraModel:
    """Read and validate a calibration config written by review_camera_calibration.py.

    Args:
        path (Path): JSON with camera_matrix, distortion_coefficients, image_size_wh,
            support_cell_px and support_grid.
    Returns:
        CameraModel: Validated model for 1280x720-style source pixels.
    """
    config = json.loads(path.read_text())
    try:
        matrix = config["camera_matrix"]
        k1, k2, p1, p2, k3 = (float(v) for v in config["distortion_coefficients"])
        width, height = (int(v) for v in config["image_size_wh"])
        cell = int(config["support_cell_px"])
        grid = tuple(str(row) for row in config["support_grid"])
        model = CameraModel(float(matrix[0][0]), float(matrix[1][1]), float(matrix[0][2]),
                            float(matrix[1][2]), k1, k2, p1, p2, k3, width, height, cell, grid)
    except (KeyError, TypeError, ValueError, IndexError) as error:
        raise ValueError(f"Invalid camera calibration config: {error}") from error
    values = (model.fx, model.fy, model.cx, model.cy, k1, k2, p1, p2, k3)
    if (not all(math.isfinite(v) for v in values) or model.fx <= 0 or model.fy <= 0
            or cell <= 0 or len(grid) != height // cell
            or any(len(row) != width // cell or set(row) - {"0", "1"} for row in grid)):
        raise ValueError("Camera calibration config has invalid values or support grid")
    return model


def distort(model: CameraModel, x: float, y: float) -> tuple[float, float]:
    """Apply the lens model to an ideal normalized point (as cv.projectPoints does).

    Args:
        model (CameraModel): Calibration.
        x (float): Ideal normalized x (X/Z).
        y (float): Ideal normalized y (Y/Z).
    Returns:
        tuple[float, float]: Distorted pixel (u, v).
    """
    r2 = x * x + y * y
    radial = 1 + model.k1 * r2 + model.k2 * r2 * r2 + model.k3 * r2 * r2 * r2
    xd = x * radial + 2 * model.p1 * x * y + model.p2 * (r2 + 2 * x * x)
    yd = y * radial + model.p1 * (r2 + 2 * y * y) + 2 * model.p2 * x * y
    return model.fx * xd + model.cx, model.fy * yd + model.cy


def max_ideal_radius(model: CameraModel) -> float:
    """Largest ideal normalized radius before the radial polynomial folds back.

    Beyond it, distort() maps directions far outside the view back into the image,
    so callers must treat larger radii as out of view rather than project them.

    Args:
        model (CameraModel): Calibration.
    Returns:
        float: Radius (tan of the off-axis angle); 10 if no fold before that.
    """
    previous = 0.0
    for step in range(1, 10001):
        r = step * 0.001
        r2 = r * r
        distorted = r * (1 + model.k1 * r2 + model.k2 * r2 * r2 + model.k3 * r2 * r2 * r2)
        if distorted <= previous:
            return r - 0.001
        previous = distorted
    return 10.0


def undistort(model: CameraModel, u: float, v: float, iterations: int = 20) -> tuple[float, float, float]:
    """Invert the lens model by fixed-point iteration (OpenCV's method, more steps).

    Args:
        model (CameraModel): Calibration.
        u (float): Pixel column.
        v (float): Pixel row.
        iterations (int): Maximum iterations; OpenCV's default is 5.
    Returns:
        tuple[float, float, float]: Ideal normalized x, y and the round-trip pixel
            error after re-applying the lens model (large means no valid inverse).
    """
    x0, y0 = (u - model.cx) / model.fx, (v - model.cy) / model.fy
    x, y = x0, y0
    for _ in range(iterations):
        r2 = x * x + y * y
        radial = 1 + model.k1 * r2 + model.k2 * r2 * r2 + model.k3 * r2 * r2 * r2
        dx = 2 * model.p1 * x * y + model.p2 * (r2 + 2 * x * x)
        dy = model.p1 * (r2 + 2 * y * y) + 2 * model.p2 * x * y
        x, y = (x0 - dx) / radial, (y0 - dy) / radial
    pu, pv = distort(model, x, y)
    return x, y, math.hypot(pu - u, pv - v)


def supported(model: CameraModel, u: float, v: float) -> bool:
    """Whether calibration data existed near this pixel.

    Args:
        model (CameraModel): Calibration with a support grid.
        u (float): Pixel column.
        v (float): Pixel row.
    Returns:
        bool: True if the pixel's cell contained detected board corners.
    """
    column, row = int(u // model.cell_px), int(v // model.cell_px)
    return 0 <= row < len(model.support) and 0 <= column < len(model.support[row]) \
        and model.support[row][column] == "1"


def rotate(quaternion: Sequence[float], vector: Sequence[float]) -> tuple[float, float, float]:
    """Rotate a camera-frame vector into the reference (start) frame.

    Args:
        quaternion (Sequence[float]): Unit (w, x, y, z) from RelativeCameraOrientation.
        vector (Sequence[float]): Camera-frame XYZ vector.
    Returns:
        tuple[float, float, float]: Reference-frame XYZ vector.
    """
    w, x, y, z = quaternion
    rotated = quaternion_product(quaternion_product((w, x, y, z), (0.0, *vector)), (w, -x, -y, -z))
    return rotated[1], rotated[2], rotated[3]


def angles(vector: Sequence[float]) -> tuple[float, float]:
    """Yaw and pitch of a direction (x right, y down, z forward).

    Args:
        vector (Sequence[float]): Nonzero XYZ direction.
    Returns:
        tuple[float, float]: Yaw right-positive and pitch up-positive, degrees.
    """
    x, y, z = vector
    return math.degrees(math.atan2(x, z)), math.degrees(math.atan2(-y, math.hypot(x, z)))


def box_bearing(model: CameraModel, box_xyxy: Sequence[float], orientation: dict,
                frame_s: float) -> dict[str, Any]:
    """Bearing of one box centre, using the orientation paired with its frame.

    Args:
        model (CameraModel): Working calibration.
        box_xyxy (Sequence[float]): Left, top, right, bottom in source pixels.
        orientation (dict): LiveImu.orientation_at() context for this frame (may be unknown).
        frame_s (float): Frame host receipt seconds.
    Returns:
        dict[str, Any]: status ready/unknown, image yaw/pitch (camera frame), bearing
            yaw/pitch (start frame), head yaw/pitch and quaternion (where the lens
            points), extrapolated flag, orientation lag in ms.
    """
    u, v = (box_xyxy[0] + box_xyxy[2]) / 2, (box_xyxy[1] + box_xyxy[3]) / 2
    x, y, round_trip = undistort(model, u, v)
    if not math.isfinite(round_trip) or round_trip > 0.5:
        return {"status": "unknown", "reason": "lens_model_not_invertible", "pixel": [u, v]}
    ray = (x, y, 1.0)
    image_yaw, image_pitch = angles(ray)
    result: dict[str, Any] = {"pixel": [u, v], "image_yaw_deg": image_yaw,
                              "image_pitch_deg": image_pitch,
                              "extrapolated": not supported(model, u, v)}
    context = orientation_context(orientation or {}, frame_s)
    if context["status"] != "ready":
        return {**result, "status": "unknown", "reason": context["reason"]}
    yaw, pitch = angles(rotate(context["quaternion_wxyz"], ray))
    head_yaw, head_pitch = angles(rotate(context["quaternion_wxyz"], (0.0, 0.0, 1.0)))
    return {**result, "status": "ready", "yaw_deg": yaw, "pitch_deg": pitch,
            "head_yaw_deg": head_yaw, "head_pitch_deg": head_pitch,
            "head_quaternion_wxyz": list(context["quaternion_wxyz"]),
            "orientation_lag_ms": (frame_s - context["sample_monotonic_s"]) * 1000,
            "reference_monotonic_s": context["reference_monotonic_s"]}


def attach_bearings(boxes: list[dict[str, Any]], model: CameraModel, orientation: dict | None,
                    frame_s: float) -> list[dict[str, Any]]:
    """Add a ``bearing`` record to each detection box (new dicts; inputs unchanged).

    Args:
        boxes (list[dict[str, Any]]): Detections with box_xyxy in source pixels.
        model (CameraModel): Working calibration.
        orientation (dict | None): Orientation context paired with the frame.
        frame_s (float): Frame host receipt seconds.
    Returns:
        list[dict[str, Any]]: Copies of the boxes with a bearing field.
    """
    return [{**box, "bearing": box_bearing(model, box["box_xyxy"], orientation or {}, frame_s)}
            for box in boxes]
