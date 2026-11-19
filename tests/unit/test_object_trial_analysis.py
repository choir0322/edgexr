"""The step-2 trial judge on simulated runs of each case."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_object_map as sim  # noqa: E402  (shared simulation helpers)
from spatial.object_map import ObjectMap  # noqa: E402

SPEC = importlib.util.spec_from_file_location("analyze_object_trial", ROOT / "scripts" / "analyze_object_trial.py")
judge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(judge)


def write_run(folder: Path, after: list) -> None:
    """Simulate still → pan −20 → +20 (hold) → 0 at 2 Hz and write the logs.

    Args:
        folder (Path): Empty run folder.
        after (list): World objects present after the hold (before it: the bottle).
    Returns:
        None: Writes telemetry.jsonl and servo_commands.jsonl.
    """
    memory, t, rows = ObjectMap(sim.MODEL), 100.0, []
    commands = [{"host_command_s": 99.0, "axis": "pan", "angle_deg": 0}]
    # (head pan, 2 Hz updates, visible world objects, pan command logged at phase start)
    phases = [(0.0, 6, [sim.BOTTLE], None), (-20.0, 4, [sim.BOTTLE], -1), (20.0, 4, [sim.BOTTLE], 20),
              (20.0, 10, after, None), (0.0, 8, after, 19)]
    for pan, count, objects, command in phases:
        if command is not None:
            commands.append({"host_command_s": t, "axis": "pan", "angle_deg": command})
        for _ in range(count):
            memory.update(sim.boxes(objects, pan, t), sim.orientation(pan, t), t)
            rows.append({"host_poll_midpoint_s": t + 0.1, "telemetry": {"object_map": memory.snapshot(t + 0.1)}})
            t += 0.5
    (folder / "telemetry.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (folder / "servo_commands.jsonl").write_text("\n".join(json.dumps(c) for c in commands) + "\n")


class ObjectTrialJudgeTests(unittest.TestCase):
    """Each simulated case passes its own expectations and fails another's."""

    def check(self, after: list, case: str, wrong: str) -> None:
        """Simulate, then judge as the right and a wrong case.

        Args:
            after (list): Objects after the hold.
            case (str): Correct case name.
            wrong (str): A case whose expectations must fail.
        Returns:
            None: Assertions only.
        """
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            write_run(run, after)
            events, last, times = judge.load(run)
            right = judge.judge(case, events, last, times)
            self.assertTrue(right["pass"], right["checks"])
            self.assertFalse(judge.judge(wrong, events, last, times)["pass"])

    def test_stay(self) -> None:
        """Bottle left in place.

        Args: None.
        Returns: None.
        """
        self.check([sim.BOTTLE], "stay", "removed")

    def test_removed(self) -> None:
        """Bottle taken away during the hold.

        Args: None.
        Returns: None.
        """
        self.check([], "removed", "stay")

    def test_moved(self) -> None:
        """Bottle moved to about −15° during the hold (visible to the turned head).

        Args: None.
        Returns: None.
        """
        self.check([("bottle", -15.0, 0.0)], "moved", "stay")


if __name__ == "__main__":
    unittest.main()
