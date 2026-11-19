"""Judge a step-2 object-memory trial (stay / removed / moved) from its logs.

Usage (standard library only):
    python3 scripts/analyze_object_trial.py ~/Desktop/object-trial-stay --case stay --output summary.json
Reads telemetry.jsonl (preview snapshots incl. object_map) and servo_commands.jsonl
from spatial.servo_orientation_demo --pan-only --hold-away-seconds N. The head pans
0 → −20 → +20, holds at +20 (object out of view, scene may be changed), returns to 0.
Expected outcomes were fixed on 2026-11-20 before any step-2 trial
(docs/STEP2_OBJECT_TRIAL.md). Reads only the run folder; writes only --output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(run: Path) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, float]]:
    """Unique object-memory events, the last object-map snapshot and sweep times.

    Args:
        run (Path): Servo-demo output folder.
    Returns:
        tuple: Events in time order, last snapshot, and times sweep_start/hold_start/hold_end.
    """
    events: dict[tuple, dict[str, Any]] = {}
    last: dict[str, Any] = {}
    for line in (run / "telemetry.jsonl").read_text().splitlines():
        snapshot = json.loads(line).get("telemetry", {}).get("object_map", {})
        if snapshot.get("status") in (None, "off"):
            continue
        last = snapshot
        for event in snapshot.get("events", []):
            events[(round(event["frame_s"], 6), event["event"], event["id"])] = event
    commands = [json.loads(line) for line in (run / "servo_commands.jsonl").read_text().splitlines() if line.strip()]
    moves = [c for c in commands if c["angle_deg"] != 0]
    hold = next(i for i, c in enumerate(commands) if c["axis"] == "pan" and c["angle_deg"] == 20)
    times = {"sweep_start": moves[0]["host_command_s"], "hold_start": commands[hold]["host_command_s"],
             "hold_end": commands[hold + 1]["host_command_s"]}
    ordered = sorted(events.values(), key=event_time)
    return ordered, last, times


def event_time(event: dict[str, Any]) -> float:
    """Sort key for events.

    Args:
        event (dict[str, Any]): Object-map event.
    Returns:
        float: Frame receipt seconds.
    """
    return float(event["frame_s"])


def judge(case: str, events: list[dict[str, Any]], last: dict[str, Any], times: dict[str, float],
          label: str = "bottle") -> dict[str, Any]:
    """Apply the fixed expectations for one case.

    Args:
        case (str): stay, removed or moved.
        events (list[dict[str, Any]]): Unique events in time order.
        last (dict[str, Any]): Final object-map snapshot.
        times (dict[str, float]): sweep_start, hold_start and hold_end host seconds.
        label (str): Object class under test.
    Returns:
        dict[str, Any]: Checks, pass flag and the key event list.
    """
    mine = [e for e in events if e["label"] == label]
    before = [e for e in mine if e["event"] == "new" and e["frame_s"] < times["sweep_start"]]
    target = before[0]["id"] if len(before) == 1 else None
    of = [e for e in mine if e["id"] == target]
    after_hold = [e for e in of if e["frame_s"] >= times["hold_end"]]
    final = next((o for o in last.get("objects", []) if o["id"] == target), None)
    checks = {"one_object_learned_before_sweep": target is not None}
    if case == "stay":
        checks["confirmed_on_return"] = any(e["event"] == "confirmed_return" for e in after_hold)
        checks["never_missing_or_moved"] = not any(e["event"] in ("missing", "moved") for e in of)
    elif case == "removed":
        missing = [e for e in after_hold if e["event"] == "missing"]
        checks["missing_within_5_s_of_return"] = bool(missing) and missing[0]["frame_s"] - times["hold_end"] <= 5.0
        checks["not_confirmed_after_return"] = not any(e["event"] == "confirmed_return" for e in after_hold)
    elif case == "moved":
        moved = [e for e in of if e["event"] == "moved" and e["frame_s"] >= times["hold_start"]]
        checks["moved_reported_same_id"] = bool(moved) and moved[0]["moved_deg"] >= 6.0
        checks["not_left_missing"] = final is not None and final["state"] != "missing"
    else:
        raise ValueError("case must be stay, removed or moved")
    others = [e for e in mine if e["event"] == "new" and e["id"] != target and e["frame_s"] >= times["sweep_start"]
              and not any(m["event"] == "moved" and m.get("merged_id") == e["id"] for m in of)]
    checks["no_unexplained_new_objects"] = not others
    return {"case": case, "target_id": target, "checks": checks, "pass": all(checks.values()),
            "target_events": of, "other_new_events": others,
            "prediction_error_px": [e.get("prediction_error_px") for e in of if e["event"] == "confirmed_return"],
            "final_state": final, "update_ms": {k: last.get(k) for k in ("update_ms_last", "update_ms_mean", "update_ms_max")},
            "updates": last.get("updates"), "relative_times_s": {k: v - times["sweep_start"] for k, v in times.items()}}


def main() -> int:
    """Write the case summary and print it.

    Args: None.
    Returns:
        int: Zero after writing; the pass flag is in the JSON.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--case", required=True, choices=("stay", "removed", "moved"))
    parser.add_argument("--label", default="bottle")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    events, last, times = load(args.run)
    summary = judge(args.case, events, last, times, args.label)
    summary["all_events"] = events
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=1, allow_nan=False)
        stream.write("\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("all_events", "target_events")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
