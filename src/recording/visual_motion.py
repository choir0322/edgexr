"""Offline patch motion versus gyro: approximate host pairing, not synchronization.

Requires existing NumPy, ffmpeg and ffprobe. Pixels refer to 320x180 images.
Run from repo root: PYTHONPATH=src python3 -m recording.visual_motion --help
"""

import argparse
import csv
import json
import math
from pathlib import Path
import shutil
import subprocess

import numpy as np

from .analyze_capture import analyze, numeric_csv, timing


WIDTH, HEIGHT = 320, 180


def patch_shift(first, second):
    """Return content displacement (right/down positive), or reject low quality.

    Phase correlation locates the peak of the normalized cross spectrum. A
    Hann window reduces edge artifacts; peak-to-sidelobe ratio rejects weak
    matches. These quality thresholds are experimental, not probabilities.
    """
    if first.shape != second.shape or first.ndim != 2 or min(first.shape) < 16:
        raise ValueError("Need equal 2D patches at least 16 pixels wide/high")
    a, b = first.astype(float), second.astype(float)
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Nonfinite image data")
    if min(a.std(), b.std()) < 3:
        return None
    window = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    cross = np.fft.fft2((b-b.mean())*window) * np.conj(np.fft.fft2((a-a.mean())*window))
    magnitude = np.abs(cross)
    cross /= np.maximum(magnitude, 1e-9)
    surface = np.fft.ifft2(cross).real
    y, x = np.unravel_index(np.argmax(surface), surface.shape)
    # Remove the wrapped 5x5 peak neighbourhood before estimating background.
    mask = np.ones(surface.shape, dtype=bool)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            mask[(y+dy) % a.shape[0], (x+dx) % a.shape[1]] = False
    side = surface[mask]
    quality = (surface[y,x]-side.mean()) / max(side.std(), 1e-9)

    def refine(index, values):
        left, center, right = values[(index-1) % len(values)], values[index], values[(index+1) % len(values)]
        denominator = left - 2*center + right
        fraction = 0.5*(left-right)/denominator if abs(denominator) > 1e-12 else 0
        return (index if index <= len(values)//2 else index-len(values)) + float(np.clip(fraction, -.5, .5))

    dx, dy = refine(x, surface[y,:]), refine(y, surface[:,x])
    if quality < 8 or abs(dx) > a.shape[1]/4 or abs(dy) > a.shape[0]/4:
        return None
    return dx, dy, float(quality)


def image_shift(first, second):
    """Median translation from agreeing patches spread across the image."""
    if first.shape != (HEIGHT, WIDTH) or second.shape != first.shape:
        raise ValueError("Images must be 320x180 grayscale")
    matches = []
    for y in (5, 62, 119):
        for x in (5, 117, 229):
            match = patch_shift(first[y:y+56, x:x+80], second[y:y+56, x:x+80])
            if match is not None:
                matches.append(match)
    if len(matches) < 4:
        return None
    matches = np.asarray(matches)
    center = np.median(matches[:,:2], axis=0)
    good = matches[np.linalg.norm(matches[:,:2]-center, axis=1) <= 1.5]
    if len(good) < 4:
        return None
    shift = np.median(good[:,:2], axis=0)
    return float(shift[0]), float(shift[1]), len(good), float(np.median(good[:,2]))


def validate_video_times(video_times, frame_rows):
    """Only associate frames by index after checking PTS and count agreement."""
    if len(video_times) != len(frame_rows) or len(video_times) < 3:
        raise ValueError("Video/log frame counts differ or are too short; cannot associate by index")
    if any(r['frame_index'] != i for i,r in enumerate(frame_rows)):
        raise ValueError("Frame indices are not contiguous from zero")
    timing(video_times)
    logged = [r['camera_pts_s'] for r in frame_rows]
    timing(logged)
    # Matroska quantizes these MJPEG timestamps to milliseconds.
    mismatch = max(abs((v-video_times[0])-(p-logged[0])) for v,p in zip(video_times,logged))
    if mismatch > .002:
        raise ValueError("Video/log relative timestamps differ by more than 2 ms")
    return mismatch


def gyro_at(timestamp, times, values):
    """Linear interpolation only inside a close pair of host-timed readings."""
    index = int(np.searchsorted(times, timestamp, side='right'))
    if index == 0 or index == len(times):
        return None
    before, after = times[index-1], times[index]
    if after-before > .15:
        return None
    weight = (timestamp-before)/(after-before)
    return values[index-1]*(1-weight) + values[index]*weight


def inspect_recording(folder):
    baseline = analyze(folder, baseline_seconds=1)
    meta = json.loads((folder/'metadata.json').read_text())
    frames = numeric_csv(folder/'frames.csv')
    imu = numeric_csv(folder/'imu.csv')
    if len(frames) > 3000:
        raise ValueError("This first offline tool is limited to 3000 frames per run")
    probe = subprocess.run(['ffprobe','-v','error','-select_streams','v:0',
        '-show_entries','frame=best_effort_timestamp_time','-of','json',str(folder/'camera.mkv')],
        capture_output=True, text=True, check=True, timeout=120)
    video_times = [float(f['best_effort_timestamp_time']) for f in json.loads(probe.stdout)['frames']]
    mismatch = validate_video_times(video_times, frames)
    decoded = subprocess.run(['ffmpeg','-v','error','-nostdin','-i',str(folder/'camera.mkv'),
        '-map','0:v:0','-vf',f'scale={WIDTH}:{HEIGHT}', '-pix_fmt','gray',
        '-frames:v',str(len(frames)+1),'-fps_mode','passthrough','-f','rawvideo','-'],
        capture_output=True, check=True, timeout=120)
    if len(decoded.stdout) != len(frames)*WIDTH*HEIGHT:
        raise ValueError("Decoded byte count differs from validated frame log")
    images = np.frombuffer(decoded.stdout, dtype=np.uint8).reshape(-1,HEIGHT,WIDTH)
    times = np.asarray([r['host_read_midpoint_s'] for r in imu])
    values = np.asarray([[r[k] for k in ('gx_dps','gy_dps','gz_dps')] for r in imu])
    values -= baseline['baseline_gyro_dps']
    cue = meta['recording_cue_host_s']
    rows = []
    for index in range(2, len(frames)):  # explicitly exclude first startup interval
        a,b = frames[index-1], frames[index]
        host_midpoint = (a['host_receipt_s']+b['host_receipt_s'])/2
        relative = host_midpoint-cue
        if not 0 <= relative <= meta['requested_seconds_after_first_frame']:
            continue
        dt = b['camera_pts_s']-a['camera_pts_s']
        shift = image_shift(images[index-1],images[index])
        gyro = gyro_at(host_midpoint,times,values)
        row = dict(frame_index=index, host_after_cue_s=relative, camera_pts_s=b['camera_pts_s'],
                   camera_interval_s=dt, accepted=False, dx_pixels=None, dy_pixels=None,
                   horizontal_pixels_s=None, vertical_pixels_s=None, agreeing_patches=0,
                   median_peak_quality=None, gx_dps=None, gy_dps=None, gz_dps=None)
        if gyro is not None:
            row.update(zip(('gx_dps','gy_dps','gz_dps'),map(float,gyro)))
        if shift is not None:
            dx,dy,count,quality = shift
            row.update(dx_pixels=dx,dy_pixels=dy, horizontal_pixels_s=dx/dt,
                       vertical_pixels_s=dy/dt,agreeing_patches=count,median_peak_quality=quality)
        row['accepted'] = shift is not None and gyro is not None
        rows.append(row)
    accepted = [r for r in rows if r['accepted']]
    if len(accepted) < 10:
        raise ValueError("Too few reliable visual/gyro pairs; inspect texture and logs")
    visual = np.asarray([r['horizontal_pixels_s'] for r in accepted])
    gyro_y = np.asarray([r['gy_dps'] for r in accepted])
    # Avoid impressive-looking correlations for almost motionless recordings.
    correlation = float(np.corrcoef(visual,gyro_y)[0,1]) if min(visual.std(),gyro_y.std()) > .5 else None
    bins = []
    for second in range(math.ceil(meta['requested_seconds_after_first_frame'])):
        part = [r for r in accepted if second <= r['host_after_cue_s'] < second+1]
        bins.append(dict(second=second, accepted_pairs=len(part),
            median_horizontal_pixels_s=float(np.median([r['horizontal_pixels_s'] for r in part])) if part else None,
            median_gyro_y_dps=float(np.median([r['gy_dps'] for r in part])) if part else None))
    summary = dict(recording=folder.name,analysis_resolution=[WIDTH,HEIGHT],
        numpy_version=np.__version__,comparison='Host receipt midpoint pairing; no fitted time shift',
        baseline_gyro_dps=baseline['baseline_gyro_dps'],baseline_window_after_cue_s=[0,1],
        video_log_max_relative_pts_difference_s=mismatch,compared_pairs=len(rows),
        accepted_pairs=len(accepted),rejected_pairs=len(rows)-len(accepted),
        median_abs_horizontal_pixels_s=float(np.median(np.abs(visual))),
        p95_abs_horizontal_pixels_s=float(np.percentile(np.abs(visual),95)),
        horizontal_vs_gyro_y_correlation=correlation,per_second=bins,
        limitations='Patch translation is not camera rotation. Moving objects/parallax can affect motion. Correlation is exploratory, not measured synchronization or angle calibration.')
    return summary, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    parser.add_argument('--output',type=Path,required=True,help='new directory under recordings/')
    args = parser.parse_args()
    if args.output.exists() or not args.output.resolve().is_relative_to(Path('recordings').resolve()):
        parser.error('choose a new output directory under recordings/, from repo root')
    if not all(shutil.which(name) for name in ('ffmpeg','ffprobe')):
        parser.error('existing ffmpeg and ffprobe are required')
    try:
        summary, rows = inspect_recording(args.folder)
        args.output.mkdir(parents=True,exist_ok=False)
        (args.output/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
        with (args.output/'motion.csv').open('w',newline='') as handle:
            writer = csv.DictWriter(handle,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(json.dumps(summary,indent=2,allow_nan=False))
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        parser.exit(1,f'Visual analysis failed: {error}\n')


if __name__ == '__main__':
    main()
