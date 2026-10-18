"""Test tracking-trial accounting without a Pi, camera, or HTTP socket."""

import json
from pathlib import Path
import tempfile
import unittest

from vision.tracking_trial import TrialSummary, compact_sample, run_trial
from vision.compare_tracking_trials import comparison, load_report


def snapshot(sequence: int, track_id: int | None, mode: str = "motion-aware") -> dict:
    """Build a minimal preview-shaped telemetry result for one detection.

    Args:
        sequence (int): Source camera sequence for this detector update.
        track_id (int | None): Synthetic person's ID; None means no person.
        mode (str): Preview tracking mode.

    Returns:
        dict: JSON-compatible telemetry without image pixels.
    """
    boxes = [] if track_id is None else [
        {"label": "person", "track_id": track_id, "confidence": .8, "box_xyxy": [1, 2, 3, 4]}
    ]
    return {
        "status": "live", "received": sequence, "analyzed": sequence - 1,
        "skipped": 2, "analysis_fps": 25.0, "analysis_ms": 30.0,
        "imu": {"status": "ready", "rate_hz": 19.0, "gyro_dps": [0.0, 12.0, 0.0]},
        "detector": {
            "status": "ready", "tracking_mode": mode, "sequence": sequence,
            "compute_ms": 220.0, "age_ms": 400.0, "boxes": boxes,
            "tracking_stats": {
                "covered_tracks": 1 if mode == "motion-aware" else 0,
                "fallback_tracks": 0,
                "motion_matches": 1 if mode == "motion-aware" else 0,
                "motion_only_matches": 0,
            },
        },
    }


class TrackingTrialTests(unittest.TestCase):
    def test_distinct_updates_and_continuous_id_changes(self) -> None:
        """Count unique results, not repeated polls or post-disappearance IDs.

        Args:
            None.

        Returns:
            None: Assertions check scope and target-continuity rules.
        """
        summary = TrialSummary("motion-aware", "person")
        for sequence, track_id in [(1, 1), (1, 1), (2, 1), (3, 2), (4, None), (5, 3)]:
            summary.add(compact_sample(snapshot(sequence, track_id), float(sequence)))
        report = summary.report(5.0, 0)
        self.assertEqual(report["detector_updates_observed"], 5)
        self.assertEqual(report["continuous_target_id_changes"], 1)
        self.assertEqual(report["target_missing_updates"], 1)
        self.assertEqual(report["tracking_counts_across_observed_updates"]["motion_matches"], 5)
        self.assertEqual(report["tracking_counts_across_observed_updates"]["motion_only_matches"], 0)
        self.assertEqual(report["motion_coverage_fraction"], 1.0)

    def test_missing_or_multiple_targets_break_identity_continuity(self) -> None:
        """Do not infer identity when a target is absent or duplicated.

        Args:
            None.

        Returns:
            None: Assertions check ambiguity and no false transition claim.
        """
        summary = TrialSummary("basic", "person")
        summary.add(compact_sample(snapshot(1, 1, "basic"), 0))
        ambiguous = snapshot(2, 2, "basic")
        ambiguous["detector"]["boxes"].append(
            {"label": "person", "track_id": 3, "box_xyxy": [5, 6, 7, 8]}
        )
        summary.add(compact_sample(ambiguous, 1))
        summary.add(compact_sample(snapshot(3, 4, "basic"), 2))
        report = summary.report(3, 0)
        self.assertEqual(report["continuous_target_id_changes"], 0)
        self.assertEqual(report["target_ambiguous_updates"], 1)
        self.assertIsNone(report["motion_coverage_fraction"])

    def test_mode_mismatch_does_not_create_output(self) -> None:
        """Refuse an incorrectly labelled trial before creating files.

        Args:
            None.

        Returns:
            None: Assertions check non-destructive mode validation.
        """
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "trial"

            def fake_fetch(url: str) -> dict:
                """Return a basic-mode response regardless of the requested URL.

                Args:
                    url (str): Ignored loopback endpoint.

                Returns:
                    dict: One fake basic snapshot.
                """
                return snapshot(1, 1, "basic")

            with self.assertRaisesRegex(ValueError, "Preview mode"):
                run_trial("http://127.0.0.1:8765/api/telemetry", "motion-aware",
                          "person", 1, .1, output, "", fake_fetch)
            self.assertFalse(output.exists())

            def detector_off(url: str) -> dict:
                """Return a baseline preview with detection disabled.

                Args:
                    url (str): Ignored loopback endpoint.

                Returns:
                    dict: Synthetic off-detector response.
                """
                result = snapshot(1, None, "basic")
                result["detector"]["status"] = "off"
                return result

            with self.assertRaisesRegex(ValueError, "Detector is off"):
                run_trial("http://127.0.0.1:8765/api/telemetry", "basic",
                          "person", 1, .1, output, "", detector_off)
            self.assertFalse(output.exists())

    def test_short_trial_writes_metrics_not_frames(self) -> None:
        """Write a readable summary and samples without camera imagery.

        Args:
            None.

        Returns:
            None: Assertions check on-disk trial format.
        """
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "trial"

            def fake_fetch(url: str) -> dict:
                """Supply repeatable detector telemetry for a brief local trial.

                Args:
                    url (str): Ignored loopback endpoint.

                Returns:
                    dict: One synthetic motion-aware result.
                """
                return snapshot(1, 1)

            report = run_trial("http://127.0.0.1:8765/api/telemetry", "motion-aware",
                               "person", .03, .01, output, "stationary fixture", fake_fetch)
            self.assertGreaterEqual(report["detector_updates_observed"], 1)
            self.assertEqual(json.loads((output / "metadata.json").read_text())["status"], "complete")
            self.assertNotIn("pixels_b64", (output / "samples.jsonl").read_text())
            self.assertEqual(json.loads((output / "summary.json").read_text())["mode"], "motion-aware")
            self.assertEqual(load_report(output, "motion-aware")["target_label"], "person")
            with self.assertRaisesRegex(ValueError, "not a complete basic"):
                load_report(output, "basic")

    def test_comparison_requires_the_same_target_class(self) -> None:
        """Reject comparisons whose ID transitions describe different objects.

        Args:
            None.

        Returns:
            None: Assertions check shared-target validation and side-by-side values.
        """
        basic = TrialSummary("basic", "person").report(60, 0)
        aware = TrialSummary("motion-aware", "chair").report(60, 0)
        with self.assertRaisesRegex(ValueError, "same target label"):
            comparison(basic, aware)
        aware["target_label"] = "person"
        self.assertIn("aware_matching", comparison(basic, aware)["metrics"])


if __name__ == "__main__":
    unittest.main()
