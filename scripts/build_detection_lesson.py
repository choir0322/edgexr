"""Derive compact lesson assets from an existing Pi image and detection report.

Uses the project's existing FFmpeg executable; the website has no dependencies.
No camera, network or model inference is involved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main() -> None:
    """Validate provenance, then derive the local illustration and numeric sample.

    Args:
        None: command-line image and report paths identify the saved Pi trial.

    Returns:
        None: writes a small image and a JavaScript data asset inside docs/learning.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    digest = hashlib.sha256(args.image.read_bytes()).hexdigest()
    if digest != report['image']['sha256']:
        raise ValueError('Image does not match the saved detector report')

    # The small PNG is a display asset. The tiny chair sample is a teaching grid,
    # not a recorded neural-network activation or an exact inference tensor.
    root = Path(__file__).resolve().parents[1]
    output = root / 'docs' / 'learning' / 'images'
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
        '-i', str(args.image), '-vf', 'scale=640:360,format=gray',
        '-frames:v', '1', str(output / 'detection-lesson-scene.png'),
    ], check=True)
    raw = subprocess.check_output([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin',
        '-i', str(args.image), '-vf', 'crop=320:240:0:280,scale=6:6:flags=area,format=gray',
        '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'gray', '-',
    ])
    if len(raw) != 36:
        raise ValueError('Expected a 6 by 6 teaching sample')
    data = {
        'image': 'images/detection-lesson-scene.png',
        'sourceSha256': digest,
        'modelSha256': report['model']['prototxt_sha256'],
        'sample': list(raw),
        'sampleRegion': [0, 280, 320, 240],
        'sampleDescription': 'Area-averaged 6×6 chair-region sample, quantized to 0–9 for arithmetic.',
        'detections': report['detections'],
        'sourceSize': report['image']['size'],
    }
    (output / 'detection-lesson-data.js').write_text(
        '// Derived from the saved Pi image/report; numeric samples are teaching inputs.\n'
        'window.DETECTION_LESSON_DATA = ' + json.dumps(data, indent=2) + ';\n'
    )
    print('Generated image and teaching data:', output)


if __name__ == '__main__':
    main()
