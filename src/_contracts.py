"""Small shared vocabulary for reading type hints; no hardware is initialized.

Runtime modules import these names only under TYPE_CHECKING, so standalone
scripts still work without modifying sys.path or importing optional libraries.
Record is deliberately flexible for evolving JSON reports; each producer's
docstring and docs/learning explain its fields, shapes and measurement scope.
"""

from __future__ import annotations
from typing import Any, Protocol, TypeAlias

# Describe sensor samples without runtime wrappers: XYZ units come from the
# caller (g or degrees/s), and TimedGyro starts with monotonic host seconds.
Axes: TypeAlias = tuple[float, float, float]
TimedGyro: TypeAlias = tuple[float, Axes]
SensorSample: TypeAlias = tuple[Axes, Axes]

# Describe pipeline payloads: Frame is sequence/receipt/gray bytes; MotionShift
# is dx/dy pixels, agreeing-patch count and quality. Reports remain flexible maps.
Frame: TypeAlias = tuple[int, float, bytes]
MotionShift: TypeAlias = tuple[float, float, int, float]
NumericRow: TypeAlias = dict[str, float]
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
        ...
