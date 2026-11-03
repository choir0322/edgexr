"""Known geometry and bounded history tests; no camera or IMU required."""

import math
import unittest

from spatial.view_map import ViewMap, direction_to_view, orientation_context


def context(axis: int = 1, degrees: float = 0, stamp: float = 1,
            epoch: float = 0) -> dict:
    """Construct a unit rotation and preceding sample for deterministic tests.

    Args:
        axis (int): Quaternion component 1/2/3 for camera X/Y/Z.
        degrees (float): Single-axis rotation.
        stamp (float): Frame and sample host time.
        epoch (float): Gyro reference time.
    Returns:
        dict: Ready orientation_at-shaped record.
    """
    q = [math.cos(math.radians(degrees) / 2), 0, 0, 0]
    q[axis] = math.sin(math.radians(degrees) / 2)
    return {"status": "ready", "quaternion_wxyz": q,
            "reference_monotonic_s": epoch, "sample_monotonic_s": stamp}


def decision(kind: str, scene_id: int | None = None, evicted: int | None = None) -> dict:
    """Build a minimal scene decision without running ORB.

    Args:
        kind (str): enrolled/known/unknown.
        scene_id (int | None): Existing or newly explicit scene ID.
        evicted (int | None): Scene memory's evicted ID.
    Returns:
        dict: Input to ViewMap.update.
    """
    return {"state": kind, "scene_id": scene_id, "label": f"View-{scene_id}",
            "evicted_id": evicted, "reason": "test"}


class ViewMapTests(unittest.TestCase):
    def test_bearings_roll_and_quaternion_sign(self) -> None:
        """Right/up signs follow camera convention; roll is not a pointing turn.

        Args: None.
        Returns: None.
        """
        identity = orientation_context(context(), 1)
        right = orientation_context(context(axis=2, degrees=30), 1)
        self.assertAlmostEqual(direction_to_view(identity, right)["yaw_right_deg"], 30)
        rolled = orientation_context(context(axis=3, degrees=90), 1)
        self.assertAlmostEqual(direction_to_view(rolled, right)["elevation_up_deg"], 30)
        vertical = orientation_context(context(axis=1, degrees=90), 1)
        self.assertIsNone(direction_to_view(identity, vertical)["yaw_right_deg"])
        self.assertAlmostEqual(direction_to_view(right, identity)["yaw_right_deg"], -30)
        up = orientation_context(context(axis=1, degrees=20), 1)
        self.assertAlmostEqual(direction_to_view(identity, up)["elevation_up_deg"], 20)
        roll = orientation_context(context(axis=3, degrees=45), 1)
        difference = direction_to_view(identity, roll)
        self.assertAlmostEqual(difference["pointing_separation_deg"], 0)
        self.assertAlmostEqual(difference["rotation_difference_deg"], 45)
        right["quaternion_wxyz"] = [-v for v in right["quaternion_wxyz"]]
        self.assertAlmostEqual(direction_to_view(identity, right)["yaw_right_deg"], 30)

    def test_invalid_stale_and_different_epochs_remain_unknown(self) -> None:
        """Do not compare stale, future, malformed or restarted gyro references.

        Args: None.
        Returns: None.
        """
        for bad in [context(stamp=0.5), context(stamp=2),
                    dict(context(), quaternion_wxyz=[0, 0, 0, 0]),
                    dict(context(), quaternion_wxyz=[float('nan'), 0, 0, 0]),
                    {"status": "unknown", "reason": "gap"}]:
            self.assertEqual(orientation_context(bad, 1)["status"], "unknown")
        self.assertEqual(direction_to_view(orientation_context(context(), 1),
                         orientation_context(context(epoch=0.5), 1))["status"], "unknown")

    def test_unknown_bridge_and_enrollment_context_not_overwritten(self) -> None:
        """Observed links mark unknown intervals; matching never rewrites orientation.

        Args: None.
        Returns: None.
        """
        m = ViewMap()
        m.update(decision('enrolled', 1), context(stamp=1), 1)
        m.update(decision('enrolled', 2), context(axis=2, degrees=30, stamp=2), 2)
        r = m.update(decision('unknown'), context(stamp=3), 3)
        self.assertIsNone(r['current_scene_id'])
        r = m.update(decision('known', 1), context(axis=2, degrees=5, stamp=4), 4)
        self.assertEqual(r['latest_transition']['intervening_unknown_observations'], 1)
        self.assertEqual(r['latest_transition']['from_scene_id'], 2)
        self.assertEqual(r['nodes'][0]['orientation']['quaternion_wxyz'], [1, 0, 0, 0])
        self.assertAlmostEqual(r['nodes'][0]['direction_from_current']['yaw_right_deg'], -5)
        r['nodes'][0]['label'] = 'external mutation'
        self.assertEqual(m.nodes[1]['label'], 'View-1')
        r = m.update(decision('known', 1), {'status':'unknown'}, 5)
        self.assertEqual(r['current_scene_id'], 1)
        self.assertEqual(r['nodes'][0]['direction_from_current']['status'], 'unknown')
        self.assertIsNone(r['latest_transition'])

    def test_eviction_bounds_edges_and_never_backfills_missing_context(self) -> None:
        """Eviction prunes links; missing enrollment orientation is never invented.

        Args: None.
        Returns: None.
        """
        m = ViewMap(2)
        m.update(decision('enrolled', 1), {'status':'unknown'}, 1)
        m.update(decision('enrolled', 2), context(stamp=2), 2)
        r = m.update(decision('known', 1), context(stamp=3), 3)
        self.assertEqual(r['nodes'][0]['direction_from_current']['status'], 'unknown')
        r = m.update(decision('enrolled', 3, evicted=1), context(stamp=4), 4)
        self.assertEqual([n['scene_id'] for n in r['nodes']], [2, 3])
        self.assertEqual(r['edges'], [])
        with self.assertRaises(ValueError):
            m.update(decision('enrolled', 4), context(stamp=5), 5)
        with self.assertRaises(ValueError):
            m.update(decision('known', 1), context(stamp=5), 5)
        with self.assertRaises(ValueError):
            m.update(decision('unknown'), {}, 4)
