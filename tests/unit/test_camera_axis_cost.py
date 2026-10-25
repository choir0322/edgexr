"""Hardware-independent checks for the camera-axis conversion cost report."""

import math
import unittest

from profiling.camera_axis_cost import measure


class CameraAxisCostTests(unittest.TestCase):
    """Keep the microbenchmark finite and explicit about its measurement scope."""

    def test_measure_reports_finite_cost_and_correct_components(self) -> None:
        """Exercise the real conversion using a known orthonormal basis."""
        basis = ((0, 0, 1), (0, 1, 0), (-1, 0, 0))
        result = measure(basis, warmup_seconds=0, measure_seconds=0.01,
                         batch_size=10)
        self.assertEqual(result["output_camera_xyz_dps"], [0.3, 0.2, -0.1])
        self.assertGreater(result["calls"], 0)
        self.assertEqual(result["calls"], result["batches"] * 10)
        for key in ("wall_us_per_call_batch_median", "wall_us_per_call_batch_p95",
                    "process_cpu_us_per_call_total"):
            self.assertTrue(math.isfinite(result[key]))
            self.assertGreater(result[key], 0)

    def test_rejects_invalid_benchmark_settings(self) -> None:
        """Avoid zero-call or unbounded measurement configurations."""
        basis = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        for settings in ({"measure_seconds": 0}, {"warmup_seconds": -1},
                         {"batch_size": 0}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                measure(basis, **settings)


if __name__ == "__main__":
    unittest.main()
