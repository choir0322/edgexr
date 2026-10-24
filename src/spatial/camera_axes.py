"""Fit a provisional camera coordinate frame from saved pan and tilt sweeps.

This offline tool uses host-timed gyro observations and physical direction
notes. It does not measure servo angles, camera pose, depth or world heading.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Sequence

from recording.analyze_capture import numeric_csv
from spatial.relative_orientation import analyze


Vector = tuple[float, float, float]


def dot(left: Sequence[float], right: Sequence[float]) -> float:
    """Return the dot product of two XYZ vectors.

    Args:
        left (Sequence[float]): First XYZ vector.
        right (Sequence[float]): Second XYZ vector.

    Returns:
        float: Sum of corresponding products.
    """
    if (len(left) != 3 or len(right) != 3 or
            not all(math.isfinite(value) for value in (*left, *right))):
        raise ValueError("Dot product requires two finite XYZ vectors")
    return sum(a * b for a, b in zip(left, right))


def unit(vector: Sequence[float]) -> Vector:
    """Normalize one finite XYZ vector, rejecting negligible movement.

    Args:
        vector (Sequence[float]): Three vector components in common units.

    Returns:
        Vector: Unit direction in the same coordinate frame.
    """
    if len(vector) != 3 or not all(math.isfinite(value) for value in vector):
        raise ValueError("Expected three finite vector components")
    length = math.sqrt(dot(vector, vector))
    if length < 1e-9:
        raise ValueError("Movement axis is too small to normalize")
    return tuple(value / length for value in vector)  # type: ignore[return-value]


def angle_degrees(first: Sequence[float], second: Sequence[float]) -> float:
    """Measure the unsigned angle between two nonzero XYZ vectors.

    Args:
        first (Sequence[float]): First XYZ vector.
        second (Sequence[float]): Second XYZ vector.

    Returns:
        float: Angle in degrees, from zero to 180.
    """
    cosine = dot(unit(first), unit(second))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def camera_components(vector: Sequence[float], basis: Sequence[Sequence[float]]) -> Vector:
    """Express an IMU angular vector along the fitted camera XYZ axes.

    Args:
        vector (Sequence[float]): IMU XYZ angular rate or rotation vector.
        basis (Sequence[Sequence[float]]): Camera right, down and forward unit
            axes, each represented in IMU coordinates at the neutral head pose.

    Returns:
        Vector: Camera XYZ components in the input's original units.
    """
    if len(vector) != 3 or len(basis) != 3 or not all(
            math.isfinite(value) for value in vector):
        raise ValueError("Expected a finite IMU XYZ vector and three camera axes")
    if any(len(axis) != 3 or not all(math.isfinite(value) for value in axis)
           for axis in basis):
        raise ValueError("Every camera axis must contain three finite components")
    return tuple(dot(vector, axis) for axis in basis)  # type: ignore[return-value]


def movement_legs(folder: Path, axis: str) -> tuple[Vector, Vector, Vector]:
    """Integrate bias-corrected gyro rates within three actual command legs.

    Args:
        folder (Path): Complete combined-capture directory with IMU and command logs.
        axis (str): Expected servo axis, ``pan`` or ``tilt``.

    Returns:
        tuple[Vector, Vector, Vector]: Negative, positive and return leg
            integrals in IMU XYZ degrees. Windows use host command timestamps;
            they are approximate motor-response intervals, not shaft angles.
    """
    if axis not in ("pan", "tilt"):
        raise ValueError("Expected a pan or tilt recording")
    orientation = analyze(folder, bias_seconds=2.0)
    meta = json.loads((folder / "metadata.json").read_text())
    command_log = json.loads((folder / "servo_commands.json").read_text())
    commands = [command for command in command_log["issued_commands"]
                if command["axis"] == axis]
    origin = int(meta["origin_monotonic_ns"])
    if not commands:
        raise ValueError(f"Recording lacks a {axis} command sweep")

    # Group commands by the sign of each one-degree step. The bounded existing
    # schedule has three legs: zero to negative, through positive, back to zero.
    legs: list[list[dict[str, object]]] = []
    signs: list[int] = []
    previous_angle = 0
    previous_time = -math.inf
    for command in commands:
        raw_angle = float(command["angle_deg"])
        if not math.isfinite(raw_angle) or not raw_angle.is_integer():
            raise ValueError("Servo command angle must be a finite whole degree")
        angle = int(raw_angle)
        stamp = (int(command["host_command_ns"]) - origin) / 1e9
        step = angle - previous_angle
        if step not in (-1, 1) or stamp <= previous_time:
            raise ValueError("Servo command path or host timestamps are invalid")
        sign = 1 if step > 0 else -1
        if not signs or sign != signs[-1]:
            signs.append(sign)
            legs.append([])
        legs[-1].append(command)
        previous_angle, previous_time = angle, stamp
    if signs != [-1, 1, -1] or previous_angle != 0:
        raise ValueError("Expected a completed zero/negative/positive/zero sweep")

    rows = numeric_csv(folder / "imu.csv")
    bias = orientation["bias_dps"]
    vectors: list[Vector] = []
    for leg in legs:
        first = (int(leg[0]["host_command_ns"]) - origin) / 1e9 - 0.025
        last = (int(leg[-1]["host_command_ns"]) - origin) / 1e9 + 0.12
        samples = [row for row in rows if first <= row["host_read_midpoint_s"] <= last]
        if len(samples) < 2:
            raise ValueError("Too few IMU samples during a servo leg")
        # Approximate each leg's signed angular change with actual IMU time
        # gaps. The response margins are fixed for this first commissioning run.
        vector = [0.0, 0.0, 0.0]
        for before, after in zip(samples, samples[1:]):
            gap = after["host_read_midpoint_s"] - before["host_read_midpoint_s"]
            if gap <= 0 or gap > 0.2:
                raise ValueError("Invalid IMU interval inside a servo leg")
            for index, key in enumerate(("gx_dps", "gy_dps", "gz_dps")):
                vector[index] += gap * ((before[key] + after[key]) / 2 - bias[index])
        vectors.append(tuple(vector))  # type: ignore[arg-type]
    return tuple(vectors)  # type: ignore[return-value]


def fitted_direction(legs: Sequence[Sequence[float]]) -> tuple[Vector, list[float]]:
    """Fit on the first two legs and reserve the final leg as a direction check.

    Args:
        legs (Sequence[Sequence[float]]): Three signed IMU XYZ leg integrals.

    Returns:
        tuple[Vector, list[float]]: First-leg direction and each leg's angle
            from its expected sign. A weak or inconsistent sweep raises ValueError.
    """
    if len(legs) != 3 or any(math.sqrt(dot(leg, leg)) < 0.4 for leg in legs):
        raise ValueError("A movement leg is too weak for this provisional fit")
    reverse = tuple(-value for value in legs[1])
    direction = unit(tuple(a + b for a, b in zip(unit(legs[0]), unit(reverse))))
    deviations = [angle_degrees(direction, leg) for leg in
                  (legs[0], reverse, legs[2])]
    if max(deviations) > 20:
        raise ValueError("Servo-leg IMU directions disagree by more than 20 degrees")
    return direction, deviations


def fit_camera_axes(pan_legs: Sequence[Sequence[float]],
                    tilt_legs: Sequence[Sequence[float]], *,
                    pan_first: str, tilt_first: str) -> dict[str, object]:
    """Build a right-handed neutral-pose camera basis from two measured axes.

    Args:
        pan_legs (Sequence[Sequence[float]]): Three pan IMU XYZ integrals in degrees.
        tilt_legs (Sequence[Sequence[float]]): Three tilt IMU XYZ integrals in degrees.
        pan_first (str): Observed first lens direction, ``right`` or ``left``.
        tilt_first (str): Observed first lens direction, ``up`` or ``down``.

    Returns:
        dict[str, object]: Camera right/down/forward axes in IMU XYZ, raw axis
            angle and held-out-leg deviations. This is a provisional mounting fit.
    """
    if pan_first not in ("right", "left") or tilt_first not in ("up", "down"):
        raise ValueError("Physical first-leg directions must be supplied")
    pan, pan_deviation = fitted_direction(pan_legs)
    tilt, tilt_deviation = fitted_direction(tilt_legs)
    if pan_first == "left":
        pan = tuple(-value for value in pan)
    if tilt_first == "down":
        tilt = tuple(-value for value in tilt)
    separation = angle_degrees(pan, tilt)
    if abs(separation - 90) > 20:
        raise ValueError("Pan and tilt axes are not sufficiently independent")

    # Camera coordinates are x right, y down, z forward. Positive rotation
    # about x tilts the lens up; positive rotation about y pans it right.
    x_axis = tilt
    projection = dot(pan, x_axis)
    y_axis = unit(tuple(value - projection * x for value, x in zip(pan, x_axis)))
    z_axis = unit((x_axis[1] * y_axis[2] - x_axis[2] * y_axis[1],
                   x_axis[2] * y_axis[0] - x_axis[0] * y_axis[2],
                   x_axis[0] * y_axis[1] - x_axis[1] * y_axis[0]))
    return {
        "camera_axes_in_imu_xyz": [list(x_axis), list(y_axis), list(z_axis)],
        "raw_pan_tilt_axis_angle_deg": separation,
        "pan_leg_deviation_deg": pan_deviation,
        "tilt_leg_deviation_deg": tilt_deviation,
        "pan_first_lens_direction": pan_first,
        "tilt_first_lens_direction": tilt_first,
    }


def validate_recording(folder: Path, basis: Sequence[Sequence[float]], *,
                       pan_first: str, tilt_first: str) -> dict[str, object]:
    """Check a fixed candidate basis on a separate combined pan/tilt recording.

    Args:
        folder (Path): Complete combined commissioning run, separate from fits.
        basis (Sequence[Sequence[float]]): Candidate camera axes in IMU XYZ.
        pan_first (str): Physical first pan direction for this mounting.
        tilt_first (str): Physical first tilt direction for this mounting.

    Returns:
        dict[str, object]: Per-leg mapped components and angular deviations;
            weak, wrong-sign or off-axis motion raises ValueError.
    """
    if pan_first not in ("right", "left") or tilt_first not in ("up", "down"):
        raise ValueError("Physical first-leg directions must be supplied")
    results: dict[str, object] = {"recording": folder.name}
    for axis, component, first_sign in (
            ("pan", 1, 1 if pan_first == "right" else -1),
            ("tilt", 0, 1 if tilt_first == "up" else -1)):
        legs = movement_legs(folder, axis)
        mapped = [camera_components(leg, basis) for leg in legs]
        deviations = []
        for index, (leg, values) in enumerate(zip(legs, mapped)):
            magnitude = math.sqrt(dot(leg, leg))
            expected_sign = first_sign * (-1 if index == 1 else 1)
            if magnitude < 0.4:
                raise ValueError(f"Independent {axis} leg {index + 1} is too weak")
            cosine = expected_sign * values[component] / magnitude
            deviation = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
            deviations.append(deviation)
            if deviation > 20:
                raise ValueError(f"Independent {axis} leg {index + 1} disagrees with fit")
        results[axis] = {
            "legs_camera_xyz_deg": mapped,
            "axis_deviation_deg": deviations,
        }
    return results


def analyze_recordings(pan_folder: Path, tilt_folder: Path, *,
                       pan_first: str, tilt_first: str,
                       validation_folder: Path | None = None) -> dict[str, object]:
    """Fit and report a mounting-specific camera basis from two complete runs.

    Args:
        pan_folder (Path): Pan capture with metadata, IMU CSV and servo commands.
        tilt_folder (Path): Tilt capture with the same schema and unchanged mount.
        pan_first (str): Observed first pan direction, ``right`` or ``left``.
        tilt_first (str): Observed first tilt direction, ``up`` or ``down``.
        validation_folder (Path | None): Optional separate combined pan/tilt
            capture whose movement legs were not used to fit the basis.

    Returns:
        dict[str, object]: Compact offline fit with source names and limits.
    """
    pan_legs = movement_legs(pan_folder, "pan")
    tilt_legs = movement_legs(tilt_folder, "tilt")
    fit = fit_camera_axes(pan_legs, tilt_legs, pan_first=pan_first,
                          tilt_first=tilt_first)
    result: dict[str, object] = {
        "pan_recording": pan_folder.name,
        "tilt_recording": tilt_folder.name,
        "pan_legs_imu_deg": pan_legs,
        "tilt_legs_imu_deg": tilt_legs,
        **fit,
        "scope": ("Offline neutral-head axis fit from two separate runs. Last leg "
                  "checks direction within each run. Independent validation appears "
                  "only when a separate capture is supplied. No measured shaft angle, "
                  "exposure synchronization, world heading, position or depth."),
    }
    if validation_folder is not None:
        if validation_folder.resolve() in (pan_folder.resolve(), tilt_folder.resolve()):
            raise ValueError("Validation capture must be separate from fit captures")
        result["independent_validation"] = validate_recording(
            validation_folder, fit["camera_axes_in_imu_xyz"],
            pan_first=pan_first, tilt_first=tilt_first)
    return result


def main() -> None:
    """Print the read-only camera-axis fit for saved pan and tilt recordings.

    Args:
        None: Two folders and observed physical directions come from CLI options.

    Returns:
        None: Prints JSON or exits with a diagnostic; never writes recordings.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pan_folder", type=Path)
    parser.add_argument("tilt_folder", type=Path)
    parser.add_argument("--pan-first", choices=("right", "left"), required=True)
    parser.add_argument("--tilt-first", choices=("up", "down"), required=True)
    parser.add_argument("--validate-folder", type=Path,
                        help="separate combined pan/tilt recording for direction checks")
    args = parser.parse_args()
    try:
        print(json.dumps(analyze_recordings(args.pan_folder, args.tilt_folder,
                                            pan_first=args.pan_first,
                                            tilt_first=args.tilt_first,
                                            validation_folder=args.validate_folder),
                         indent=2, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Camera-axis fit failed: {error}\n")


if __name__ == "__main__":
    main()
