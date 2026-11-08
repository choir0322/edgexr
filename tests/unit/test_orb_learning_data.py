"""Verify browser replay evidence remains internally consistent with its gates."""

import json
from pathlib import Path
import unittest


class OrbLearningDataTests(unittest.TestCase):
    def test_actual_descriptors_and_production_counts(self) -> None:
        """Check XOR distance, match gates, geometry counts and distinct outcomes.

        Args: None.
        Returns: None.
        """
        root = Path(__file__).resolve().parents[2] / "docs/learning/images"
        raw = (root / "orb-scene-data.js").read_text()
        data = json.loads(raw.removeprefix("window.ORB_DATA=").strip().removesuffix(";"))
        self.assertEqual([e["decision"]["state"] for e in data["examples"]], ["known", "unknown"])
        for example in data["examples"]:
            candidate = example["decision"]["candidates"][0]
            self.assertEqual(len(example["bits_a"]), 256)
            self.assertEqual(sum(a != b for a, b in zip(example["bits_a"], example["bits_b"])),
                             example["selected"]["d1"])
            good = [p for p in example["pairs"] if p["accepted"]]
            self.assertEqual(len(good), candidate["matches"])
            self.assertEqual(sum(p["inlier"] for p in good), candidate["inliers"])
            for pair in example["pairs"]:
                self.assertEqual(pair["accepted"], pair["d1"] <= 64 and pair["d1"] < 0.75 * pair["d2"] and pair["mutual"])
            self.assertTrue((root / example["reference"]).is_file())
            self.assertTrue((root / example["query"]).is_file())
