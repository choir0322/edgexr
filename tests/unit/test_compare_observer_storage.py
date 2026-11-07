"""Comparison fixtures preserve missing evidence and avoid counting cycles twice."""

import json
from pathlib import Path
import tempfile
import unittest

from profiling.compare_observer_storage import counter, distribution, summarize


class CompareObserverStorageTests(unittest.TestCase):
    def test_missing_is_not_zero(self) -> None:
        """Report unavailable counters separately from valid zeros.

        Args: None.
        Returns: None.
        """
        self.assertEqual(distribution([None, float("nan")])["count"], 0)
        self.assertIsNone(distribution([])["max"])
        self.assertEqual(counter("VmRSS:\t2048 kB\nVmSwap:\t0 kB", "VmSwap"), 0)
        self.assertIsNone(counter(None, "VmRSS"))

    def test_last_cycle_deduplicated_and_export_cpu_separate(self) -> None:
        """Use recorded collection CPU, not post-run export CPU.

        Args: None.
        Returns: None.
        """
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            cycle = {"sample_index": 0, "write_wall_ms": 5}
            metadata = {"observer_output_mode": "ram", "vmstat_before": {"text": "pswpout 3\npswpin 2"}}
            summary = {"elapsed_s": 10, "observer_cpu_s": 1,
                       "last_observer_cycle": cycle, "sample_export": {"cpu_s": 10},
                       "vmstat_after": {"text": "pswpout 4\npswpin 2"}}
            (folder / "metadata.json").write_text(json.dumps(metadata))
            (folder / "summary.json").write_text(json.dumps(summary))
            (folder / "samples.jsonl").write_text(json.dumps({"previous_observer_cycle": cycle}) + "\n")
            result = summarize(folder)
            self.assertEqual(result["metrics"]["write_wall_ms"]["count"], 1)
            self.assertEqual(result["observer_average_cpu_pct_one_core"], 10)
            self.assertEqual(result["swap"]["pswpout_pages_delta"], 1)
            self.assertFalse(result["scene_updates_available"])
            self.assertIsNone(result["scene_recording"])
