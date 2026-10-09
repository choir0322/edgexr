# Study 1: image motion, camera to browser

Read [the pipeline diagram](../PIPELINE.md) first. This path answers "how did
visible image content move?" It does not identify objects or recover camera
rotation. No IMU value is an input to the live image-shift estimator.

## Source reading route

| Order | File | Symbols to read |
|---|---|---|
| 1 | [live_preview.py](../../src/app/live_preview.py) | `main`, `camera_command`, `start_workers` |
| 2 | [live_preview.py](../../src/app/live_preview.py) | `read_frame`, nested `capture`, `State.publish_frame` |
| 3 | [live_preview.py](../../src/app/live_preview.py) | `run_motion_worker` inside `start_workers`; `analyze_latest` and its `motion_frame_ready` callback |
| 4 | [visual_motion.py](../../src/recording/visual_motion.py) | `image_shift`, `patch_shift`, nested `refine` |
| 5 | [live_preview.py](../../src/app/live_preview.py) | `State.publish_result`, `State.snapshot`, `rate`, `make_handler` |
| 6 | [preview.html](../../src/app/preview.html) | `poll`, `render`, the `dx`/`dy` arrow block |
| 7 | [live_preview.py](../../src/app/live_preview.py) | `log_errors`, `State.fail`, `stop_workers` |

## 1. Entry point and capture request

`main()` parses the mutually exclusive real `--device` and synthetic `--demo`
sources plus optional detection/IMU flags. It creates shared state and a
loopback HTTP server, starts workers, then services requests. `camera_command()`
constructs a list of FFmpeg arguments, not a shell command string. The real
camera mode is MJPEG, 1280x720, requested 30 fps. `--demo` produces synthetic
video instead. The earlier camera baseline's 120 fps default is a different
program, not the preview's setting.

`start_workers()` starts FFmpeg with `subprocess.Popen`. Its stdout pipe is raw
grayscale pixels; stderr is diagnostics. FFmpeg performs MJPEG decoding. Without
detection it also resizes to 320x180. With detection it outputs 1280x720 so
the other branch can prepare its own model input.

## 2. Byte stream becomes complete images

`read_frame(stream, size)` accepts a readable binary stream and expected byte
count; it returns immutable `bytes`, or `None` for clean end-of-stream. Pipe
reads are not guaranteed to return a whole image, so the loop gathers chunks
until it has exactly `size` bytes. End-of-stream partway through an image raises
`ValueError`, preventing misaligned pixel interpretation.

For one byte per gray pixel:

```text
320 * 180 = 57,600 bytes
1280 * 720 = 921,600 bytes
```

The nested `capture()` stamps `time.monotonic()` after a complete read. With
detection enabled it performs:

```python
gray = np.frombuffer(pixels, dtype=np.uint8).reshape(SOURCE_HEIGHT, SOURCE_WIDTH)
small = cv.resize(gray, (WIDTH, HEIGHT), interpolation=cv.INTER_AREA).tobytes()
state.publish_frame(small, received, pixels)
```

Read this line by line: interpret the bytes as unsigned 8-bit pixels without
reordering them; shape the view as 720 rows and 1280 columns; resize to 320
columns and 180 rows; convert the small image back to bytes; publish both sizes
with the same receipt timestamp. Resizing changes sample resolution, not the
camera's configured capture mode. The timestamp is before the small resize.

`State.publish_frame()` increments a sequence number and stores
`(sequence: int, timestamp: float seconds, pixels: bytes)`. `State.latest` is
one replaceable small-image slot. The condition lock protects the update and
`notify_all()` wakes interested workers. There is no application frame backlog.

## 3. Choose two frames

`analyze_latest(state)` keeps a local `previous` frame and selects the newest
unprocessed sequence from `state.latest`. It releases the lock before running
the expensive math so capture can continue. It reshapes both byte strings to
`np.uint8` arrays of shape `(180, 320)`.

The documented `motion_frame_ready()` callback now names the condition formerly
written as an anonymous lambda. It evaluates the same stop/error/new-sequence
expression when the condition asks; it does not start a separate thread.
`run_motion_worker()` simply binds this run's state to the thread entry point.
See [the shared type vocabulary](../../src/_contracts.py) for `Frame` and
`MotionShift`; [code conventions](CODE_CONVENTIONS.md) explains deferred types.

There is no deliberate frame-rate throttle here. `wait_for(..., timeout=.5)`
can wake immediately on notification; it is not a 2 Hz scheduler. If capture
outpaces analysis, intermediate sequences are replaced. For previously
processed sequence 10 and newest sequence 13, two images (11 and 12) are skipped.

The first image has no comparison partner. If the host timestamp gap exceeds
0.5 seconds, the worker also avoids computing a shift. This prevents interpreting
a long interruption as normal consecutive motion. It is distinct from the
wait timeout despite the same numerical value.

## 4. Nine-patch consensus

`image_shift(first, second)` requires two arrays of shape `(180, 320)`. It selects
nine patches at three horizontal and three vertical positions. Each patch is
56 rows by 80 columns. Each call to `patch_shift()` returns
`(dx: float pixels, dy: float pixels, quality: float)` or `None`.

With at least four valid patches, `image_shift()` computes a median displacement,
keeps matches within 1.5 pixels of that median and requires at least four
agreeing matches. Its output is `(dx, dy, agreeing_count, median_quality)` or
`None`. Median/consensus reduce sensitivity to a local moving object, but do not
guarantee the background wins. Parallax, poor texture and multiple moving
regions can still mislead it.

Inside `patch_shift()`, follow these operations in order:

1. Check matching 2D shapes, minimum dimensions and finite numbers.
2. Convert integer pixel values to floating point for arithmetic.
3. Reject patches with intensity standard deviation below 3: flat areas have
   too little pattern to locate a meaningful shift.
4. Subtract each patch mean and apply a Hann window to soften artificial edges.
5. Transform both patches with `np.fft.fft2`. Multiply the second transform by
   the complex conjugate of the first to compare displacement-related phase.
6. Divide by the spectrum magnitude with a small floor to avoid division by zero.
7. Inverse-transform to a correlation surface; its strongest peak indicates shift.
8. Exclude the wrapped 5x5 peak neighbourhood when measuring background variation.
9. Calculate peak quality relative to the background; this is not a probability.
10. `refine(index, values)` fits the local peak neighbourhood for a subpixel
    offset, and unwraps large indices into signed displacements.
11. Reject quality below 8 or displacement larger than one quarter of a patch
    dimension. Return positive dx for rightward and positive dy for downward
    movement of image content from first image to second image.

Fourier math is provided by NumPy, not MobileNet or OpenCV's detector. The live
output is displacement per processed pair, not pixels/second or degrees/second.

## 5. Publish values and measure work

`State.publish_result()` keeps the analyzed pixels, sequence, displacement,
quality and elapsed estimator milliseconds. Pixel bytes are Base64 encoded so
they can travel in JSON; this encoding is not JPEG compression. It increments
the motion skipped counter from sequence gaps and keeps recent completion times.

`rate(times)` calculates `(count - 1) / (last - first)`. `snapshot()` filters
recent timestamps to a two-second window. Capture receipts and completed
analyses therefore have separate rate measurements. Estimator time surrounds
array preparation/shift estimation in the worker, not camera exposure, decoding,
serialization or browser drawing. Result age starts at host frame receipt.

`snapshot()` marks old/error results and removes usable dx/dy from them. The
HTTP handler turns the snapshot into JSON for `/api/frame`. Separate detector
and IMU snapshots are added here, but do not modify the motion estimate.

## 6. Browser renders the image and arrow

`preview.html`'s `poll()` fetches `/api/frame`, calls `render()`, then waits 200 ms
before the next request. Fetch/render time adds to that wait. Thus the browser
shows fewer updates than the motion worker computes.

`render()` decodes Base64, copies gray intensity into browser R/G/B channels
and sets alpha to 255. The image canvas contains 320x180 source pixels; CSS may
make it look larger. The arrow canvas is 640x360 for overlay drawing, not a
higher-resolution estimator. After stale/quality checks, displacement direction
is normalized and arrow length exaggerated/clamped for visibility. Very small
movement below 0.15 pixels has no arrow. Do not integrate the arrow endpoints to
estimate camera position: it is only a visual indicator.

## 7. Failure and shutdown paths

Partial frames, FFmpeg exit and analysis exceptions set a camera error. The
diagnostic thread drains stderr into a short recent-message buffer. HTTP only
serves known routes and rejects unsuitable hosts/cross-site requests. Network
failure clears browser overlays. `stop_workers()` sets the stop event, wakes
waiters, terminates FFmpeg (kills only after timeout), joins workers and closes
pipes. The preview does not write raw images or recordings.

## Separate historical measurement path

- [capture_baseline.py](../../src/camera/capture_baseline.py): `main`,
  `frame_timestamps`, `summarize` request a mode and measure decoded timestamps
  and wall throughput. This was the initial camera-only test.
- [combined_capture.py](../../src/recording/combined_capture.py): `record`,
  `camera_command`, `parse_frame`, `read_row` save MJPEG video plus frame/IMU logs.
- [visual_motion.py](../../src/recording/visual_motion.py): `inspect_recording`
  validates saved video/log pairing, reuses `image_shift`, and pairs visual
  velocity with interpolated gyro values using `gyro_at`. Offline dx/dt uses
  camera PTS intervals; live arrow dx does not. Host pairing is approximate.
- [plot_visual_motion.py](../../src/recording/plot_visual_motion.py):
  `plot_comparisons` visualizes already calculated comparison results.

## Tests and study exercises

Read [test_visual_motion.py](../../tests/unit/test_visual_motion.py) for known
shift sign, low texture rejection, outlier consensus and time pairing. Read
[test_live_preview.py](../../tests/unit/test_live_preview.py) for partial reads,
latest-frame replacement, skipped counts, stale state and HTTP restrictions.

Before moving on, explain: why a pipe read may be short; why `(180,320)` and
`(320,180)` both occur; why 30 received fps can coexist with 25 analyzed fps and
fewer than 5 browser updates/s; and why scene displacement is not camera pose.
Trace a synthetic two-pixel rightward shift through the relevant unit test.
