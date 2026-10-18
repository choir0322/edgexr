# Read why saved image-motion pairs were rejected

`recording.patch_diagnostics` is an offline, read-only explanation tool for an
existing `recording.visual_motion` analysis. It decodes the saved video again
at 320×180 grayscale, validates frame index/PTS against the analysis CSV,
and reports the nine patch checks for **visually rejected** frame pairs. It
does not read hardware, change the live estimator's thresholds, or turn a
rejection into a camera-motion estimate.

From the repository root, with the copied fast clip and analysis already in
ignored `recordings/`:

```bash
PYTHONPATH=src python3 -m recording.patch_diagnostics \
  --video recordings/quality-fast-01.mkv \
  --analysis recordings/quality-analysis-fast-01 \
  --output recordings/quality-patch-diagnostics-fast-01
```

Use a **new** output name for a retry. Existing ffmpeg, ffprobe and NumPy are
required; the tool installs nothing. It decodes up to 3000 frames into memory.
The output is `summary.json` and one `pairs.jsonl` row per visually rejected
pair. Both stay Git-ignored. A missing IMU reading alone does not qualify as a
visual rejection; the tool selects rows where `dx_pixels` is blank. The video
must match the analysis summary name and camera PTS within 2 ms.

For each patch, `std_first` and `std_second` measure texture before FFT.
`candidate_dx_pixels`, `candidate_dy_pixels` and `peak_quality` are available
only when there is enough texture to run correlation. `failed_checks` can
contain more than one item:

- `low_texture`: either patch's intensity standard deviation is below 3.
- `weak_peak`: correlation quality is below 8. This score is not a probability.
- `large_horizontal_shift`: candidate |dx| exceeds 20 analysis pixels.
- `large_vertical_shift`: candidate |dy| exceeds 14 analysis pixels.

A candidate from a weak peak is **not a reliable movement measurement**, even
when it also exceeds a displacement limit. `too_few_valid_patches` means fewer
than four of nine patches passed all individual checks. `patches_disagree`
means at least four passed individually, but fewer than four were within
1.5 pixels of the median candidate. Thus a pair may fail without any patch
having a low-texture or over-limit flag. The output stores all nine positions
and counts so you can inspect the spatial pattern, not just a single verdict.

## What this run established and what follows

On the user's repeated-fast-turn clip, 24 of 28 rejected pairs had fewer than
four valid patches; the other four had enough individually valid patches but
not enough agreement. Of 252 patch checks, 219 had weak peaks, 16 had an
over-limit horizontal candidate, five had an over-limit vertical candidate,
and none failed for low texture. Flags can overlap. See the concise
[result note](../benchmarks/results/motion-quality-2026-10-19.md).

The next experiment is a **controlled turn-speed test**, not immediate
threshold tuning. Use the same textured scene, light, camera mode and mounting
at several progressively faster but safe turn rates; record the intended and
observed speed bands and precise action intervals if possible. Analyze each
run with the same thresholds, then compare visual coverage, patch-failure
mix, blur/occlusion seen in video, and gyro rates. Change one algorithm
setting only after a repeatable failure boundary is evident. IMU rates and
host video receipts are not exposure-synchronized, so do not infer exact
degrees per frame from them.
