"""One-shot, attended ±20° pan/tilt demonstration for the live IMU view.

Run the read-only live preview separately first. This command does not open the
camera, read the IMU, or expose servo controls over HTTP.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import time
from typing import Callable, Protocol


PAN_CHANNEL = 2
TILT_CHANNEL = 3
LIMIT_DEG = 20
STEP_SECONDS = 0.1  # 1 commanded degree per 100 ms: at most 10 commanded °/s.


class ServoPort(Protocol):
    """Only the existing Fusion HAT angle method is needed by this test."""

    def angle(self, degrees: int) -> None:
        """Command one servo position in degrees."""


@dataclass(frozen=True)
class Step:
    """One bounded motor command after the initial 0° center."""

    axis: str
    angle_deg: int
    due_s: float


def build_steps() -> list[Step]:
    """Make sequential pan and tilt paths: 0 → −20 → +20 → 0.

    Returns:
        list[Step]: 160 one-degree commands, with 2 s settling between axes.
    """
    steps: list[Step] = []
    due = 0.0
    for axis in ("pan", "tilt"):
        current = 0
        for target in (-LIMIT_DEG, LIMIT_DEG, 0):
            while current != target:
                current += 1 if target > current else -1
                due += STEP_SECONDS
                steps.append(Step(axis, current, due))
        due += 2.0
    return steps


def run_steps(
    steps: list[Step], servos: dict[str, ServoPort], *,
    clock: Callable[[], float] = time.monotonic,
    pause: Callable[[float], None] = time.sleep,
) -> int:
    """Send one axis at a time, preserving step spacing if Linux runs late.

    Args:
        steps (list[Step]): Fixed, prevalidated center-bounded schedule.
        servos (dict[str, ServoPort]): Hardware servos or test doubles.
        clock (Callable[[], float]): Monotonic seconds for deadlines.
        pause (Callable[[float], None]): Sleep callback, injectable in tests.

    Returns:
        int: Number of issued 1° steps; interruption stops future commands.
    """
    last_angle = {"pan": 0, "tilt": 0}
    start = clock()
    previous_actual: float | None = None
    previous_due = 0.0
    for step in steps:
        if (step.axis not in last_angle or abs(step.angle_deg) > LIMIT_DEG or
                abs(step.angle_deg - last_angle[step.axis]) != 1 or
                step.due_s - previous_due < STEP_SECONDS - 1e-9):
            raise ValueError("Invalid servo schedule; no further commands sent")
        deadline = start + step.due_s
        if previous_actual is not None:
            deadline = max(deadline, previous_actual + step.due_s - previous_due)
        while clock() < deadline:
            pause(min(0.05, deadline - clock()))
        servos[step.axis].angle(step.angle_deg)
        last_angle[step.axis] = step.angle_deg
        previous_actual = clock()
        previous_due = step.due_s
    return len(steps)


def main() -> int:
    """Arm and execute one supervised sweep without opening camera or IMU.

    Returns:
        int: Zero on a full center return, nonzero on interrupted/failed motion.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="actually command the servos")
    parser.add_argument("--confirm-centered", action="store_true", help="both axes' 0° positions are safe")
    parser.add_argument("--confirm-clearance", action="store_true", help="both axes and cables are clear through ±20°")
    args = parser.parse_args()
    steps = build_steps()
    print("Pan 0 → −20 → +20 → 0, then tilt 0 → −20 → +20 → 0; "
          f"{len(steps)} one-degree commands at ≤10 commanded °/s.", flush=True)
    if not args.execute:
        print("No motors commanded. Add --execute and both confirmation flags for the real run.")
        return 0
    if not args.confirm_centered or not args.confirm_clearance:
        parser.error("Real motion requires --confirm-centered --confirm-clearance")

    # The user observes the rig during a cancel window. Importing the vendor
    # driver and writing 0° only happens after explicit arming.
    try:
        print("Armed. Ctrl+C within 3 seconds to cancel before servo initialization.", flush=True)
        time.sleep(3)
        from fusion_hat.servo import Servo

        servos: dict[str, ServoPort] = {
            "pan": Servo(PAN_CHANNEL), "tilt": Servo(TILT_CHANNEL),
        }
        servos["pan"].angle(0)
        servos["tilt"].angle(0)
        print("Centered both axes. Hold still for 2 seconds; then pan starts.", flush=True)
        time.sleep(2)
        count = run_steps(steps, servos)
        print(f"Completed {count} commands; pan and tilt returned to commanded 0°. "
              "Compare the browser's peak and final relative-turn values.", flush=True)
        return 0
    except KeyboardInterrupt:
        print("Interrupted: no further commands. A servo may hold its last position; "
              "inspect the rig before moving it.", flush=True)
        return 130
    except Exception as error:
        print(f"Servo test stopped: {error}. A servo may hold its last position.", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
