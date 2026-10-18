"""Check timestamp coverage and unknown intervals without camera hardware."""

import unittest

from vision.motion_history import MotionHistory


class MotionHistoryTests(unittest.TestCase):
    def test_partial_endpoints_integrate_only_reliable_covered_time(self) -> None:
        """Interpolate within analyzed pairs and reject uncovered endpoints.

        Args:
            None.

        Returns:
            None: Assertions check partial-pair integration.
        """
        history = MotionHistory()
        history.add(1, 1.0, 2, 1.05, (2.0, -1.0))
        history.add(2, 1.05, 4, 1.10, (4.0, -2.0))
        dx, dy = history.displacement(1.025, 1.075)
        self.assertAlmostEqual(dx, 3.0)
        self.assertAlmostEqual(dy, -1.5)
        self.assertIsNone(history.displacement(0.99, 1.075))
        self.assertIsNone(history.displacement(1.025, 1.101))

    def test_unreliable_or_long_pair_is_unknown_not_zero(self) -> None:
        """One invalid segment prevents a false displacement across the gap.

        Args:
            None.

        Returns:
            None: Assertions check that unknown is not counted as zero.
        """
        history = MotionHistory()
        history.add(1, 1.0, 2, 1.05, (1.0, 0.0))
        history.add(2, 1.05, 3, 1.10, None)
        history.add(3, 1.10, 4, 1.15, (1.0, 0.0))
        self.assertIsNone(history.displacement(1.0, 1.15))
        self.assertEqual(history.displacement(1.10, 1.15), (1.0, 0.0))
        history.add(4, 1.15, 5, 1.40, (20.0, 0.0))
        self.assertIsNone(history.displacement(1.15, 1.40))

    def test_bounded_history_and_discontinuity(self) -> None:
        """Old or disconnected records cannot provide apparent coverage.

        Args:
            None.

        Returns:
            None: Assertions check bounded and discontinuous history.
        """
        history = MotionHistory(limit=2)
        history.add(1, 1.0, 2, 1.05, (1.0, 0.0))
        history.add(2, 1.05, 3, 1.10, (1.0, 0.0))
        history.add(3, 1.10, 4, 1.15, (1.0, 0.0))
        self.assertIsNone(history.displacement(1.0, 1.15))
        history.add(8, 2.0, 9, 2.05, (2.0, 0.0))
        self.assertEqual(history.displacement(2.0, 2.05), (2.0, 0.0))
        self.assertIsNone(history.displacement(1.10, 2.05))


if __name__ == "__main__":
    unittest.main()
