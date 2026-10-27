# Live IMU polling and visual-return A/B

## Purpose / big picture

Determine whether the live camera-head orientation return mismatch becomes
smaller when IMU polling pauses 10 ms rather than 50 ms after each read. The
same attended ±20° pan/tilt program supplies motion in both cases. Save
small before/after camera-view checkpoints so qualitative visual return can
be inspected separately from the quaternion. This directly advances the
bounded vision/spatial-awareness application; detailed AP optimization remains
deferred.

## Context and orientation

The Raspberry Pi 4 runs Bookworm aarch64, the OV9281 USB camera at requested
1280×720 MJPEG/30 fps, and the camera-head SH3001 IMU. `imu.live_reader.poll_imu`
already accepts a post-read pause but `app.live_preview` currently uses its
50 ms default. `spatial.servo_orientation_demo` commands the already-confirmed
safe channels pan 2 and tilt 3, and logs host-observed orientation from the
preview. Previous [returns](../../LIVE_ORIENTATION_SERVO_RESULTS.md) visually
reached the starting view but retained estimated rotation. The camera does not
provide an exposure-synchronized image/IMU join.

## Progress

- [x] 2026-10-28: User approved the 50 ms versus 10 ms live polling comparison
  and before/after image checkpoints.
- [x] Inspect live polling, preview JSON and servo schedule; avoid another
  camera owner or new image dependency.
- [x] Expose a bounded, reported `--imu-sleep-ms` option with 50 ms default.
- [x] Save before-pan, settled-after-pan and settled-after-tilt grayscale
  checkpoints plus timestamps under ignored `recordings/`.
- [x] Add hardware-free tests for configuration and checkpoint validation.
- [x] Review/update `docs/PIPELINE.md` and `docs/learning/IMU.md` for shapes,
  units, scheduling, freshness, failure behavior and source links.
- [x] 2026-10-28: First 50 ms run exposed a duplicate `after_pan` checkpoint
  at the intermediate 0° crossing. Select the terminal pan command by its
  schedule identity; add a regression test. Original `50a` is invalid for A/B.
- [x] 2026-10-28: Four corrected, complete Pi runs transferred and analyzed;
  [results](../../LIVE_IMU_POLLING_AB_RESULTS.md) record actual IMU rates,
  checkpoint-relative quaternions and small-image checks. User physical-return
  confirmation and AP cost measurement remain pending.

## Plan of work

1. Keep 50 ms behavior unchanged by default. Limit the new CLI selector to
   50 or 10 ms, pass it only to the existing IMU worker, and show the selected
   post-read pause in telemetry so trial metadata is self-describing.
2. At safe still points in the existing attended servo schedule, fetch the
   preview's 320×180 grayscale bytes and write small portable-graymap images
   and host times. Never write imagery to Git. Do not use a second camera
   capture process or let an HTTP failure command unexpected motor movement.
3. Test pure logic and fake HTTP snapshots on the development machine. The
   motor path remains explicitly armed and does not run in tests.
4. On the Pi, use a fresh preview startup still reference for each trial,
   the same scene/light/mount/cooling, and new output folders. Compare
   quaternion-relative orientation before/after pan and tilt, the saved
   views, actual IMU rate, status/errors and camera/motion rates. Do not treat
   visible return or servo commands as measured shaft angle.

## Concrete steps

After code review and push, run the documented preview at 50 ms for one
trial and at 10 ms for another; repeat each once. Use
`docs/LIVE_ORIENTATION_SERVO_TEST.md` for the exact Pi/Mac commands and unique
`recordings/` names. Keep the hardware attended and clear throughout ±20°.
An interrupted run remains partial; never overwrite a prior output folder.

## Validation and acceptance

All hardware-free unit tests pass; invalid or stale image payloads fail
explicitly rather than producing a misleading checkpoint. The unchanged
default still requests a 50 ms post-read sleep, while 10 ms is opt-in and
reported. A Pi trial is usable only with a complete command log, ready
orientation through the settled return, all three image checkpoints, and
an actual IMU rate. Accept or reject faster polling only after comparing
repeated start-to-return results, not one metadata final angle.

## Surprises and discoveries

The preview already exposes display-size grayscale pixels on `/api/frame`;
the image checkpoint needs no OpenCV, PNG encoder, or second V4L2 reader.
The pan schedule crosses 0° twice. Checking only `axis=pan, angle=0` took a
checkpoint and inserted a pause in the middle of the sweep. The correction
changes the checkpoint trigger, not the live data route, so the pipeline
diagram was reviewed and does not need a topology update.

## Decision log

- 2026-10-28: Use 320×180 PGM checkpoints because they are sufficient for a
  coarse visual-return check and introduce no dependency. They are not a
  calibrated optical-angle measurement. Keep the 50 ms default and bound the
  comparison to one other value, 10 ms.

## Outcomes and retrospective

Implementation is complete and hardware-free tests pass. The live pipeline
diagram distinguishes the 50/10 ms post-read wait and the servo process's
three ignored 320×180 PGM checkpoints. Two valid runs per setting show much
smaller estimated return residual at 10 ms, but do not prove physical return,
absolute accuracy, a unique sampling cause, or AP savings. The invalid first
50 ms trial is retained outside Git rather than silently reused.
