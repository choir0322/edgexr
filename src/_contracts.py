"""Small shared vocabulary for reading type hints; no hardware is initialized.

Runtime modules import these names only under TYPE_CHECKING, so standalone
scripts still work without modifying sys.path or importing optional libraries.
Record is deliberately flexible for evolving JSON reports; each producer's
docstring and docs/learning explain its fields, shapes and measurement scope.
"""

# Keep annotations descriptive without evaluating referenced types during import.
from __future__ import annotations

# Only standard-library typing helpers are needed to describe data boundaries.
from typing import Any, Protocol, TypeAlias

# Ordered XYZ numbers; the caller's docstring specifies g, degrees/s or degrees.
Axes: TypeAlias = tuple[float, float, float]
# One gyro observation pairs host monotonic seconds with XYZ degrees/second.
TimedGyro: TypeAlias = tuple[float, Axes]
# One baseline sample contains acceleration in g, followed by gyro in degrees/s.
SensorSample: TypeAlias = tuple[Axes, Axes]
# Live frame fields are sequence, host receipt seconds, and immutable gray bytes.
Frame: TypeAlias = tuple[int, float, bytes]
# Image displacement is dx/dy pixels, agreeing-patch count and peak quality.
MotionShift: TypeAlias = tuple[float, float, int, float]
# CSV readers convert all numeric columns to finite floating-point values.
NumericRow: TypeAlias = dict[str, float]
# JSON reports combine strings, scalars, lists and nested dictionaries.
Record: TypeAlias = dict[str, Any]


class Sensor(Protocol):
    """The read-only driver interface used by production code and fake sensors."""

    def read_raw(self) -> tuple[Axes, Axes, float]:
        """Read driver-converted acceleration, gyro and temperature.

        Args:
            None; self is the sensor implementation.

        Returns:
            Tuple of XYZ acceleration (g), XYZ angular rate (degrees/s), and
            temperature (degrees C). This is not uninterpreted register data.

        Raises:
            OSError or a driver-specific error when the hardware read fails.
        """
        # A Protocol describes a contract; concrete drivers supply the operation.
        ...
