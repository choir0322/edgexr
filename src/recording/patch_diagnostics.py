"""Explain rejected image-motion pairs in an existing saved analysis.

This is an offline-only report. It reuses patch_shift's exact gates without
changing what the live motion worker accepts. No camera or IMU is accessed.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import shutil
import subprocess

import numpy as np

from .visual_motion import (
    HEIGHT,
    WIDTH,
    PATCH_HEIGHT,
    PATCH_WIDTH,
    PATCH_ORIGINS,
    image_shift,
    patch_shift,
)


def diagnose_pair(first: np.ndarray, second: np.ndarray) -> dict[str, object]:
    """Record each patch's candidate and the full pair's rejection stage.

    Args:
        first (np.ndarray): Earlier 320×180 grayscale image.
        second (np.ndarray): Later 320×180 grayscale image.

    Returns:
        dict[str, object]: Nine patch records, valid/inlier counts and pair status.
    """
    if first.shape != (HEIGHT, WIDTH) or second.shape != first.shape:
        raise ValueError("Expected two 320x180 grayscale images")
    patches = []
    valid = []
    for patch_index, (x, y) in enumerate(PATCH_ORIGINS):
        detail: dict[str, object] = {}
        match = patch_shift(
            first[y : y + PATCH_HEIGHT, x : x + PATCH_WIDTH],
            second[y : y + PATCH_HEIGHT, x : x + PATCH_WIDTH],
            diagnostics=detail,
        )
        patches.append(dict(patch_index=patch_index, x=x, y=y, **detail))
        if match is not None:
            valid.append(match)

    inlier_count = 0
    if len(valid) >= 4:
        candidates = np.asarray(valid)
        center = np.median(candidates[:, :2], axis=0)
        inlier_count = int(
            np.count_nonzero(np.linalg.norm(candidates[:, :2] - center, axis=1) <= 1.5)
        )
    pair_status = (
        "too_few_valid_patches"
        if len(valid) < 4
        else "patches_disagree"
        if inlier_count < 4
        else "accepted"
    )
    return dict(
        pair_status=pair_status,
        valid_patches=len(valid),
        agreeing_patches=inlier_count,
        patches=patches,
    )


def rejected_rows(analysis: Path, video_name: str) -> list[dict[str, str]]:
    """Read visually rejected frame rows and verify their recording identity.

    Args:
        analysis (Path): Existing visual_motion output directory.
        video_name (str): Input video stem expected by its summary.

    Returns:
        list[dict[str, str]]: Rejected visual rows, ordered by frame index.
    """
    summary = json.loads((analysis / "summary.json").read_text())
    if summary["recording"] != video_name or summary["analysis_resolution"] != [WIDTH, HEIGHT]:
        raise ValueError("Analysis summary does not match video or 320x180 mode")
    with (analysis / "motion.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("Empty motion.csv")
    selected = []
    previous = -1
    for row in rows:
        index = int(row["frame_index"])
        camera_pts = float(row["camera_pts_s"])
        if index <= previous or not math.isfinite(camera_pts):
            raise ValueError("Nonincreasing frame index or invalid camera PTS")
        previous = index
        if row["dx_pixels"] == "":
            selected.append(row)
    if len(rows) != summary["compared_pairs"]:
        raise ValueError("motion.csv row count differs from its summary")
    return selected


def recording_name_for_video(video: Path) -> str:
    """Identify both an SCP-renamed video and an original capture directory.

    Args:
        video (Path): Either ``<run>/camera.mkv`` or a copied ``<run>.mkv``.

    Returns:
        str: Recording name expected by visual_motion's summary.
    """
    return video.parent.name if video.name == "camera.mkv" else video.stem


def decode_video(video: Path) -> tuple[list[float], np.ndarray]:
    """Decode a bounded saved video and return PTS plus 320×180 gray images.

    Args:
        video (Path): Existing MJPEG recording; never written by this tool.

    Returns:
        tuple[list[float], np.ndarray]: Per-frame presentation seconds and images.
    """
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(video),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    times = [
        float(frame["best_effort_timestamp_time"])
        for frame in json.loads(probe.stdout)["frames"]
    ]
    if not 3 <= len(times) <= 3000 or any(not math.isfinite(t) for t in times):
        raise ValueError("Video needs 3–3000 frames with finite PTS")
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("Video PTS must increase")
    decoded = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-nostdin", "-i", str(video),
            "-map", "0:v:0", "-vf", f"scale={WIDTH}:{HEIGHT}", "-pix_fmt", "gray",
            "-frames:v", str(len(times) + 1), "-fps_mode", "passthrough",
            "-f", "rawvideo", "-",
        ],
        capture_output=True,
        check=True,
        timeout=120,
    )
    if len(decoded.stdout) != len(times) * WIDTH * HEIGHT:
        raise ValueError("Decoded video byte count disagrees with ffprobe")
    return times, np.frombuffer(decoded.stdout, dtype=np.uint8).reshape(-1, HEIGHT, WIDTH)


def inspect(video: Path, analysis: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Diagnose every visually rejected pair and verify it remains rejected.

    Args:
        video (Path): Recording matching visual_motion's summary name.
        analysis (Path): Existing visual_motion output for that recording.

    Returns:
        tuple[dict[str, object], list[dict[str, object]]]: Aggregate and pair records.
    """
    recording_name = recording_name_for_video(video)
    rows = rejected_rows(analysis, recording_name)
    times, images = decode_video(video)
    pairs = []
    checks: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    for row in rows:
        index = int(row["frame_index"])
        if not 1 <= index < len(images) or abs(times[index] - float(row["camera_pts_s"])) > 0.002:
            raise ValueError("Analysis frame index/PTS does not match video")
        detail = diagnose_pair(images[index - 1], images[index])
        if (
            detail["pair_status"] == "accepted"
            or image_shift(images[index - 1], images[index]) is not None
        ):
            raise ValueError(f"Frame {index} no longer reproduces its visual rejection")
        for patch in detail["patches"]:
            checks.update(patch["failed_checks"])
        statuses[detail["pair_status"]] += 1
        pairs.append(
            dict(
                frame_index=index,
                host_after_cue_s=float(row["host_after_cue_s"]),
                camera_pts_s=times[index],
                gyro_y_dps=float(row["gy_dps"]) if row["gy_dps"] else None,
                **detail,
            )
        )
    summary = dict(
        recording=recording_name,
        analysis=analysis.name,
        visually_rejected_pairs=len(pairs),
        pair_status_counts=dict(statuses),
        patch_failed_check_counts=dict(checks),
        patch_count_per_pair=len(PATCH_ORIGINS),
        limits=dict(min_texture_std=3, min_peak_quality=8, max_abs_dx_pixels=20,
                    max_abs_dy_pixels=14, min_valid_or_agreeing_patches=4,
                    max_consensus_distance_pixels=1.5),
        limits_note="Checks can overlap; counts do not prove blur or any other physical cause.",
    )
    return summary, pairs


def main() -> None:
    """Write diagnostic JSON for existing visual rejections, without overwriting.

    Args:
        None.

    Returns:
        None: CLI errors are reported without modifying the input video or CSV.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or not args.output.resolve().is_relative_to(
        Path("recordings").resolve()
    ):
        parser.error("choose a new output directory under recordings/, from repo root")
    if not all(shutil.which(name) for name in ("ffmpeg", "ffprobe")):
        parser.error("existing ffmpeg and ffprobe are required")
    try:
        summary, pairs = inspect(args.video, args.analysis)
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / "summary.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n"
        )
        with (args.output / "pairs.jsonl").open("w") as handle:
            for pair in pairs:
                handle.write(json.dumps(pair, allow_nan=False) + "\n")
        print(json.dumps(summary, indent=2, allow_nan=False))
        print(f"Saved {len(pairs)} rejected-pair records to {args.output}")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Patch diagnosis failed: {error}\n")


if __name__ == "__main__":
    main()
