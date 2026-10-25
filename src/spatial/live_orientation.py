"""Bounded gyro-only camera rotation relative to a run's still reference."""

from __future__ import annotations

import math
from typing import Iterable

from spatial.relative_orientation import quaternion_product, rotation_vector_degrees


class RelativeCameraOrientation:
    """Integrate camera-axis angular rates without bridging missing IMU time."""

    def __init__(self, max_gap_seconds: float = 0.2) -> None:
        """Start at identity; the first sample establishes the time reference.

        Args:
            max_gap_seconds (float): Largest trusted interval between host read midpoints.
        """
        if not math.isfinite(max_gap_seconds) or max_gap_seconds <= 0:
            raise ValueError("Orientation gap limit must be positive and finite")
        self.max_gap_seconds = max_gap_seconds
        self.quaternion = (1.0, 0.0, 0.0, 0.0)
        self.first_time: float | None = None
        self.last_time: float | None = None
        self.last_rate: tuple[float, float, float] | None = None
        self.integrated_intervals = 0
        self.status = "starting"
        self.reason: str | None = None

    def invalidate(self, reason: str) -> None:
        """Stop publishing an orientation until a new still-calibrated run.

        Args:
            reason (str): Explicit reason for lost continuity.
        """
        self.status = "unknown"
        self.reason = reason
        self.last_rate = None

    def add(self, timestamp: float, camera_rate_dps: Iterable[float]) -> None:
        """Compose one midpoint-timed camera-axis gyro increment.

        Args:
            timestamp (float): Host monotonic read-midpoint time in seconds.
            camera_rate_dps (Iterable[float]): Bias-corrected camera XYZ rates in deg/s.
        """
        if self.status == "unknown":
            return
        rates = tuple(camera_rate_dps)
        if (not math.isfinite(timestamp) or len(rates) != 3 or
                not all(math.isfinite(value) for value in rates)):
            self.invalidate("non-finite time or camera-axis rate")
            return
        if self.last_time is None:
            self.first_time = self.last_time = timestamp
            self.last_rate = rates
            self.status = "ready"
            return

        dt = timestamp - self.last_time
        if dt <= 0 or dt > self.max_gap_seconds:
            self.invalidate("non-increasing time or IMU gap over limit")
            return

        # The average of adjacent body-frame rates approximates the turn over dt.
        turn = tuple(math.radians((old + new) / 2) * dt
                     for old, new in zip(self.last_rate, rates))
        angle = math.sqrt(sum(value * value for value in turn))
        if angle:
            factor = math.sin(angle / 2) / angle
            increment = (math.cos(angle / 2), *(value * factor for value in turn))
            composed = quaternion_product(self.quaternion, increment)
            magnitude = math.sqrt(sum(value * value for value in composed))
            self.quaternion = tuple(value / magnitude for value in composed)
        self.last_time = timestamp
        self.last_rate = rates
        self.integrated_intervals += 1

    def snapshot(self, now: float) -> dict:
        """Return finite JSON-ready rotation or an explicit unavailable state.

        Args:
            now (float): Host monotonic time in seconds for sample age.
        """
        ready = self.status == "ready"
        vector = rotation_vector_degrees(self.quaternion) if ready else None
        return {
            "status": self.status,
            "reason": self.reason,
            "quaternion_wxyz": list(self.quaternion) if ready else None,
            "rotation_vector_deg": list(vector) if vector is not None else None,
            "angle_deg": math.sqrt(sum(value * value for value in vector)) if vector is not None else None,
            "reference_monotonic_s": self.first_time,
            "sample_age_ms": (now - self.last_time) * 1000 if self.last_time is not None else None,
            "integrated_intervals": self.integrated_intervals,
        }
