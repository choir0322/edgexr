"""Verify controlled workload matching and additional CPU accounting."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from profiling.compare_imu_resources import compare, read_run


class CompareImuResourceTests(unittest.TestCase):
    """Use known process work to check the benchmark's comparison direction."""

    def test_completed_files_produce_quality_and_incomplete_resources_are_refused(self) -> None:
        """Read a synthetic stationary run through the actual file/analysis path.

        Args:
            None.

        Returns:
            None: Checks measured rate, zero residual and failure-status enforcement.
        """
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            meta=dict(status='complete',measure_resources=True,imu_sleep_seconds=.05,
                      requested_seconds_after_first_frame=5.,recording_cue_host_s=0.,
                      imu_samples=101,requested_mode='test',host='Pi',python='3.11',notes='test')
            (folder/'metadata.json').write_text(json.dumps(meta))
            (folder/'imu.csv').write_text('host_read_midpoint_s,read_duration_s,gx_dps,gy_dps,gz_dps\n'+
                ''.join(f'{i*.05},.002,1,2,3\n' for i in range(101)))
            (folder/'frames.csv').write_text('camera_pts_s\n0\n.033\n.066\n')
            (folder/'servo_quality_summary.json').write_text('{"git_commit":"same"}')
            (folder/'servo_commands.json').write_text('{"planned_phases":[]}')
            report=dict(status='complete',capture_status='complete',throttle_before='0x0',
                        throttle_after='0x0',imu_sleep_seconds=.05,requested_seconds=5.,
                        summary={'recorder_cpu_seconds':.2})
            (folder/'resources.json').write_text(json.dumps(report))
            row=read_run(folder)
            self.assertAlmostEqual(row['imu_rate_hz'],20.)
            self.assertEqual(row['final_rotation_residual_deg'],0.)
            self.assertEqual(row['recorder_cpu_seconds'],.2)
            meta.update(imu_policy='command-driven',imu_active_sleep_seconds=.01,
                origin_monotonic_ns=0,imu_policy_transitions=[
                    {'mode':'idle','host_s':0.,'sleep_seconds':.05},
                    {'mode':'fast','host_s':2.4,'sleep_seconds':.01},
                    {'mode':'idle','host_s':4.5,'sleep_seconds':.05}])
            report.update(imu_policy='command-driven',imu_active_sleep_seconds=.01)
            (folder/'metadata.json').write_text(json.dumps(meta))
            (folder/'resources.json').write_text(json.dumps(report))
            commands=dict(planned_phases=[],issued_commands=[
                {'host_command_ns':2_700_000_000},{'host_command_ns':3_500_000_000}])
            (folder/'servo_commands.json').write_text(json.dumps(commands))
            self.assertEqual(read_run(folder)['imu_policy'],'command-driven')
            meta['imu_policy_transitions'][1]['host_s']=2.8
            (folder/'metadata.json').write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,'cover motion'):
                read_run(folder)
            report['status']='incomplete'
            (folder/'resources.json').write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,'incomplete'):
                read_run(folder)

    def test_extra_cpu_seconds_and_points_are_not_confused(self) -> None:
        """Differences use 10 ms minus 50 ms and preserve individual trial evidence.

        Args:
            None.

        Returns:
            None: Checks seconds, one-core percentage points and mismatched workloads.
        """
        slow=dict(requested_seconds=20,camera_mode='test',host='Pi',python='3.11',
                  git_commit='same',planned_phases=[],imu_sleep_seconds=.05,
                  recorder_cpu_seconds=.2,ffmpeg_cpu_seconds=6.,combined_cpu_seconds=6.2,
                  recorder_mean_cpu_pct_one_core=1.,ffmpeg_mean_cpu_pct_one_core=30.,
                  combined_mean_cpu_pct_one_core=31.,
                  imu_rate_hz=19.,imu_samples_in_window=400,final_rotation_residual_deg=11.)
        fast=dict(slow,imu_sleep_seconds=.01,recorder_cpu_seconds=.8,
                  combined_cpu_seconds=6.8,recorder_mean_cpu_pct_one_core=4.,
                  combined_mean_cpu_pct_one_core=34.,imu_rate_hz=80.,imu_samples_in_window=1700,
                  final_rotation_residual_deg=2.)
        with patch('profiling.compare_imu_resources.read_run',side_effect=[slow,fast]):
            report=compare([Path('slow'),Path('fast')])
        delta=report['faster_minus_slower']
        self.assertAlmostEqual(delta['recorder_cpu_seconds'],.6)
        self.assertEqual(delta['recorder_mean_cpu_pct_one_core'],3.)
        self.assertEqual(delta['final_rotation_residual_deg'],-9.)
        adaptive=dict(fast,imu_policy='command-driven',imu_sleep_seconds=.05,
                      recorder_cpu_seconds=.7,combined_cpu_seconds=6.7)
        with patch('profiling.compare_imu_resources.read_run',side_effect=[slow,fast,adaptive]):
            report=compare([Path('slow'),Path('fast'),Path('adaptive')])
        self.assertAlmostEqual(report['adaptive_minus_fixed_10ms']['recorder_cpu_seconds'],-.1)
        self.assertEqual(report['medians']['adaptive']['run_count'],1)
        with patch('profiling.compare_imu_resources.read_run',
                   side_effect=[slow,dict(fast,git_commit='different')]):
            with self.assertRaisesRegex(ValueError,'git_commit'):
                compare([Path('slow'),Path('fast')])
