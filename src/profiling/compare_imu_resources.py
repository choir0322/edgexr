"""Compare completed fixed-interval capture resource trials and orientation quality."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
from typing import Any

from spatial.relative_orientation import analyze
from recording.analyze_capture import numeric_csv, timing


def read_run(folder: Path) -> dict[str, Any]:
    """Load a complete resource trial and recompute its offline rotation quality.

    Args:
        folder (Path): Run directory containing metadata, resources and servo summary.

    Returns:
        dict[str, Any]: Compact quality/resource row plus comparable workload identity.
    """
    meta = json.loads((folder/'metadata.json').read_text())
    resources = json.loads((folder/'resources.json').read_text())
    servo = json.loads((folder/'servo_quality_summary.json').read_text())
    schedule = json.loads((folder/'servo_commands.json').read_text())['planned_phases']
    if (meta['status'] != 'complete' or resources['status'] != 'complete'
            or resources['capture_status'] != 'complete' or not meta.get('measure_resources')):
        raise ValueError(f'{folder}: recording/resource measurement incomplete')
    if meta['imu_sleep_seconds'] not in (.05,.01):
        raise ValueError('This first comparison accepts only fixed 50 ms and 10 ms sleep')
    if (resources['imu_sleep_seconds'] != meta['imu_sleep_seconds'] or
            resources['requested_seconds'] != meta['requested_seconds_after_first_frame']):
        raise ValueError('Resource report configuration disagrees with recording metadata')
    orientation = analyze(folder,bias_seconds=2)
    cpu = resources['summary']
    vector = orientation['final_rotation_vector_deg']
    rows = numeric_csv(folder/'imu.csv')
    return dict(
        recording=folder.name, imu_sleep_seconds=meta['imu_sleep_seconds'],
        requested_seconds=meta['requested_seconds_after_first_frame'],
        camera_mode=meta['requested_mode'], host=meta['host'], python=meta['python'],
        git_commit=servo['git_commit'], notes=meta['notes'], planned_phases=schedule,
        **cpu,
        imu_rate_hz=(orientation['samples']-1)/orientation['span_s'],
        imu_max_gap_ms=orientation['max_gap_ms'],
        imu_median_read_ms=1000*statistics.median(r['read_duration_s'] for r in rows),
        final_rotation_residual_deg=math.sqrt(sum(v*v for v in vector)),
        final_rotation_vector_deg=vector,
        camera_pts=timing([r['camera_pts_s'] for r in numeric_csv(folder/'frames.csv')][1:]),
        throttle_before=resources['throttle_before'], throttle_after=resources['throttle_after'],
    )


def compare(folders: list[Path]) -> dict[str, Any]:
    """Calculate per-configuration medians and extra CPU work for faster polling.

    Args:
        folders (list[Path]): Completed trials with the same workload and observer.

    Returns:
        dict[str, Any]: Per-run results, group medians and 10 ms minus 50 ms differences.
    """
    runs = [read_run(folder) for folder in folders]
    if not runs:
        raise ValueError('Need completed fixed-rate trials')
    # Do not silently compare different software, movement or capture settings.
    for key in ('requested_seconds','camera_mode','host','python','git_commit','planned_phases'):
        if any(run[key] != runs[0][key] for run in runs):
            raise ValueError(f'Workload mismatch: {key}')
    metrics = ('recorder_cpu_seconds','ffmpeg_cpu_seconds','combined_cpu_seconds',
               'recorder_mean_cpu_pct_one_core','ffmpeg_mean_cpu_pct_one_core',
               'combined_mean_cpu_pct_one_core',
               'imu_rate_hz','final_rotation_residual_deg')
    groups = {}
    for sleep,label in ((.05,'50ms'),(.01,'10ms')):
        selected = [run for run in runs if run['imu_sleep_seconds'] == sleep]
        if not selected:
            raise ValueError('Need both fixed 50 ms and 10 ms trials')
        groups[label] = dict(run_count=len(selected), **{
            key: statistics.median(row[key] for row in selected) for key in metrics})
    return dict(runs=runs, medians=groups, faster_minus_slower={
        key:groups['10ms'][key]-groups['50ms'][key] for key in metrics},
        limits=('Short paired trials, not a significance test. CPU differences describe '
                'the recorder/FFmpeg workload with observer overhead included, not pure '
                'I2C time. Match scene, power and thermal state manually using run notes '
                'and temperatures. Residual assumes a physical return; camera command '
                'angles are not ground truth. CPU time is not electrical energy.'))


def main() -> None:
    """Print a comparison and optionally save a new small shareable JSON report.

    Args:
        None: Paths/options are read from the command line.

    Returns:
        None: Writes stdout and an optional new report, or exits with a clear error.
    """
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folders',type=Path,nargs='+')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        report=compare(args.folders)
        text=json.dumps(report,indent=2,allow_nan=False)+'\n'
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            with args.output.open('x') as handle:
                handle.write(text)
        print(text,end='')
    except (OSError,ValueError,KeyError,TypeError) as error:
        parser.exit(1,f'Resource comparison failed: {error}\n')


if __name__ == '__main__':
    main()
