"""Build compact teaching assets from previously decoded Pi camera frames.

Run on a development computer with NumPy and FFmpeg/FFprobe installed. The
recommended input is the original local camera.mkv; an existing NPZ containing
`images` (uint8, N×180×320) and `times` (camera PTS seconds) also works. No
video is copied into the repository; review the generated stills before Git.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from recording.visual_motion import image_shift, patch_shift

OUTPUT = ROOT / "docs" / "learning" / "images"
PATCH_XY = (117, 119)
PATCH_WH = (80, 56)


def write_gray_png(path: Path, image: np.ndarray) -> None:
    """Write an eight-bit grayscale PNG using the Python standard library.

    Args:
        path (Path): Specific derived teaching-image destination.
        image (np.ndarray): Two-dimensional uint8 pixels.

    Returns:
        None: writes one small PNG with lossless pixel values.
    """
    if image.ndim != 2 or image.dtype != np.uint8:
        raise ValueError("PNG input must be a two-dimensional uint8 image")

    def chunk(label: bytes, payload: bytes) -> bytes:
        """Encode one length-prefixed PNG chunk with its CRC."""
        return (
            struct.pack(">I", len(payload))
            + label
            + payload
            + struct.pack(">I", zlib.crc32(label + payload) & 0xFFFFFFFF)
        )

    height, width = image.shape
    raw = b"".join(b"\0" + row.tobytes() for row in image)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, level=9))
        + chunk(b"IEND", b"")
    )


def rounded(values: np.ndarray, places: int) -> list[float]:
    """Flatten a derived display array with enough precision for inspection.

    Args:
        values (np.ndarray): Numeric image or Fourier map.
        places (int): Decimal places to retain in the teaching asset.

    Returns:
        list[float]: JSON-ready values in row-major order.
    """
    return np.round(values, places).ravel().tolist()


def pair_data(first: np.ndarray, second: np.ndarray, pts: list[float]) -> dict:
    """Derive exactly the math and nine-patch decisions for one recorded pair.

    Args:
        first (np.ndarray): Earlier 320×180 grayscale frame.
        second (np.ndarray): Later 320×180 grayscale frame.
        pts (list[float]): Camera presentation timestamps for those frames.

    Returns:
        dict: Small images, Fourier maps and replayed estimator decisions.
    """
    x0, y0 = PATCH_XY
    width, height = PATCH_WH
    pa = first[y0 : y0 + height, x0 : x0 + width]
    pb = second[y0 : y0 + height, x0 : x0 + width]
    a, b = pa.astype(float), pb.astype(float)
    window = np.outer(np.hanning(height), np.hanning(width))
    fa = np.fft.fft2((a - a.mean()) * window)
    fb = np.fft.fft2((b - b.mean()) * window)
    cross = fb * np.conj(fa)
    normalized = cross / np.maximum(np.abs(cross), 1e-9)
    surface = np.fft.ifft2(normalized).real
    peak_y, peak_x = np.unravel_index(np.argmax(surface), surface.shape)
    chosen = patch_shift(pa, pb)
    if chosen is None:
        raise ValueError("The selected recorded patch must pass for this lesson")

    # Apply the real image_shift selection rule to every fixed sample region.
    patches = []
    valid = []
    for y in (5, 62, 119):
        for x in (5, 117, 229):
            match = patch_shift(first[y : y + 56, x : x + 80], second[y : y + 56, x : x + 80])
            if match is not None:
                valid.append(match)
            patches.append({"x": x, "y": y, "match": list(match) if match else None})
    center = np.median(np.asarray(valid)[:, :2], axis=0)
    for patch in patches:
        if patch["match"] is not None:
            patch["distance"] = float(np.linalg.norm(np.asarray(patch["match"][:2]) - center))
            patch["agrees"] = patch["distance"] <= 1.5
        else:
            patch["distance"] = None
            patch["agrees"] = False
    whole = image_shift(first, second)
    assert (sum(p["agrees"] for p in patches) >= 4) == (whole is not None)

    return {
        "pts": pts,
        "a": pa.ravel().tolist(),
        "b": pb.ravel().tolist(),
        "meanA": float(a.mean()),
        "meanB": float(b.mean()),
        "stdA": float(a.std()),
        "stdB": float(b.std()),
        "spectrumA": rounded(np.log1p(np.abs(np.fft.fftshift(fa))), 4),
        "spectrumB": rounded(np.log1p(np.abs(np.fft.fftshift(fb))), 4),
        "phase": rounded(np.angle(np.fft.fftshift(normalized)), 4),
        "surface": rounded(surface, 8),
        "peak": [int(peak_x), int(peak_y)],
        "patchResult": list(chosen),
        "patches": patches,
        "medianBeforeAgreement": center.tolist(),
        "wholeResult": list(whole) if whole else None,
    }


def decode_video(video: Path) -> tuple[np.ndarray, np.ndarray]:
    """Decode grayscale teaching frames and their camera presentation times.

    Args:
        video (Path): Local MJPEG camera.mkv recording; never copied to Git.

    Returns:
        tuple[np.ndarray, np.ndarray]: 320×180 uint8 frames and PTS seconds.
    """
    if not video.is_file():
        raise FileNotFoundError(video)

    # FFprobe reports presentation times in frame order; FFmpeg decodes the
    # same stream without dropping or duplicating frames for the lesson.
    timestamps = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "frame=best_effort_timestamp_time", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True,
    )
    times = np.asarray([float(line) for line in timestamps.stdout.splitlines() if line.strip()])
    decoded = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i",
         str(video), "-vf", "scale=320:180,format=gray", "-fps_mode",
         "passthrough", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True, check=True,
    )
    pixels_per_frame = 320 * 180
    if len(decoded.stdout) % pixels_per_frame:
        raise ValueError("Decoded bytes do not contain complete 320×180 frames")
    frames = np.frombuffer(decoded.stdout, dtype=np.uint8).reshape((-1, 180, 320))
    if len(frames) != len(times):
        raise ValueError("Decoded frames and presentation timestamps differ")
    return frames, times


def main() -> None:
    """Read local decoded frames and write the fixed offline lesson artifacts.

    Args:
        None: parses `--video` or `--frames-npz` from the command line.

    Returns:
        None: prints output paths and two nine-patch results.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--video", type=Path, help="local camera.mkv recording")
    source.add_argument("--frames-npz", type=Path, help="previously decoded images/times archive")
    args = parser.parse_args()
    if args.video:
        frames, times = decode_video(args.video)
    else:
        with np.load(args.frames_npz) as archive:
            frames, times = archive["images"], archive["times"]
    if frames.ndim != 3 or frames.shape[1:] != (180, 320) or frames.dtype != np.uint8:
        raise ValueError("Expected uint8 images shaped (N, 180, 320)")
    if len(frames) <= 316 or len(times) != len(frames):
        raise ValueError("Missing one of the documented frame indices or PTS")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    for index in (313, 314, 316):
        write_gray_png(OUTPUT / f"hann-frame-{index}.png", frames[index])
        x, y = PATCH_XY
        write_gray_png(OUTPUT / f"hann-patch-{index}.png", frames[index, y : y + 56, x : x + 80])
    data = {
        "source": "combined-motion-02/camera.mkv",
        "preparation": "FFmpeg scale=320:180, gray, fps_mode passthrough",
        "framePaths": {str(i): f"images/hann-frame-{i}.png" for i in (313, 314, 316)},
        "patchPaths": {str(i): f"images/hann-patch-{i}.png" for i in (313, 314, 316)},
        "pairs": {
            "adjacent": pair_data(frames[313], frames[314], [float(times[313]), float(times[314])]),
            "walkthrough": pair_data(frames[313], frames[316], [float(times[313]), float(times[316])]),
        },
    }
    path = OUTPUT / "hann-fft-data.js"
    path.write_text(
        "// Derived teaching arrays from the recorded Pi video; no raw footage.\n"
        + "window.HANN_FFT_LESSON_DATA = "
        + json.dumps(data, separators=(",", ":"), allow_nan=False)
        + ";\n"
    )
    print(path, path.stat().st_size, "bytes")
    for name, pair in data["pairs"].items():
        print(name, "patch", pair["patchResult"], "whole", pair["wholeResult"])


if __name__ == "__main__":
    main()
