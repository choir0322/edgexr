# Intended architecture

The first implementation should remain a pipeline of small, visible pieces:

```text
USB camera -> frame capture -> object detector -> tracker -> display + metrics
IMU        -> motion/orientation ----------------------------^ 
```

`frame capture` acquires timestamped images. The `object detector` identifies
objects in individual frames; it may initially be replaced by recorded test
data. The `tracker` gives detections stable identifiers across nearby frames.
The IMU stream is kept separate so the learner can first inspect its values and
then decide how it should influence tracking. The display and metrics layer
shows what the system believes and how expensive that belief was to compute.

## Design principles

- Keep hardware access behind small modules so logic can be tested without a Pi.
- Timestamp camera frames and IMU samples at acquisition time.
- Make each component's input and output inspectable in logs or a debug view.
- Start with a baseline and change one performance variable at a time.
- Record uncertainty; hardware behavior and camera modes must be measured rather
  than inferred from product listings.

## Planned source ownership

When implementation begins, create only the module that the current milestone
needs: `src/camera/` for capture, `src/imu/` for sensor reads, `src/vision/` for
detection and tracking, `src/runtime/` for orchestration and metrics, and
`src/visualization/` for the live view. Keep shared data structures small and
documented. No module is required until it has a tested purpose.
