# Hardware record and verification guide

## Known equipment

- Raspberry Pi 4 (record RAM size, power supply, cooling, storage, and OS image
  before benchmarking).
- SunFounder AI Fusion Lab Kit (record the exact IMU board, connection method,
  and library or protocol after inspecting the kit).
- A USB industrial global-shutter camera module described by its vendor as a
  720p, 120-frame-per-second OV9281 camera. This is **not** the camera supplied
  with the SunFounder kit.

The OV9281 sensor is often offered in several board, lens, resolution, pixel
format, and USB-controller combinations. Therefore the advertised mode is a
starting hypothesis, not a project fact. The Pi must report the negotiated mode
before it appears in a benchmark or README claim.

## Camera verification checklist

On the Raspberry Pi, record the date and output of these checks in a future
hardware log or ExecPlan:

1. Identify the camera in the USB device list and note the USB port or bus.
2. List video devices; do not assume the camera is `/dev/video0`.
3. Use a Video4Linux-capable tool to list supported formats, frame sizes, frame
   rates, and controls.
4. Capture a short test at the selected mode. Record negotiated resolution,
   pixel format, measured FPS, exposure/gain settings, and whether the image is
   monochrome or color.
5. Repeat after the Pi has warmed up; note power and cooling conditions.

`scripts/hardware_inventory.sh` collects a safe starting inventory when run on
the Pi. It does not change camera controls or install packages.

## First camera observations

The user's initial Raspberry Pi 4 check reported Linux
`6.12.47+rpt-rpi-v8`, a 43.3 C temperature reading before benchmarking, and a
USB device identified as `1bcf:2cd1 Sunplus DECXIN CAMERA`. The camera was on
a 480 Mb/s USB 2.0 link behind a hub. On that run, `/dev/video0` offered image
capture while `/dev/video1` listed no capture formats. Device paths may change.

The camera advertised 1280x800 and 1280x720 MJPEG at 120 fps; 1280x720 YUYV
was advertised at 10 fps. A 1,200-frame V4L2 stream at 1280x720 MJPEG reported
about 118.6-118.8 fps after startup. A separate 10-second FFmpeg decode test
output 1,181 frames at roughly 119 fps, with 7.882 s user CPU time and a peak
resident set of 155,748 kB. These are capture/decode checks, not application
throughput or end-to-end latency measurements. FFmpeg reported repeated output
timestamps; that warning alone does not establish image duplication or loss.

An image was saved to `/tmp/edgexr-sample.png` on the Pi but has not yet been
visually reviewed. Exact sensor identity, exposure/gain settings, lighting,
power supply, cooling, and warm-state behavior remain to be verified.

## IMU verification checklist

First record raw accelerometer and gyroscope readings while the board is still,
then rotate it slowly about one axis at a time. Label its board orientation in a
photo or diagram stored outside Git if needed. Do not combine IMU data with
camera tracking until the raw readings, units, sample rate, and coordinate
convention are understood.

## First IMU observations

The separate SunFounder 10-axis IMU module is now connected through the Fusion
HAT. The Pi's I2C scan gained three sensor addresses (0x1c, 0x36, 0x76), and
the SunFounder example produced changing acceleration, gyro, magnetometer,
and pressure readings when the board moved. The board has an SH3001 motion
sensor, QMC6310 magnetometer, and SPL06_001 barometer.

The vendor calibration completed, but it saved identical bias and scale arrays
for all three sensors. Its shared mutable default arrays and six-face gyro
scaling make that output unreliable. A stationary vendor-calibrated reading
had about 3.3 g total acceleration and about 62 degrees/second on gyro Y.
Do not use the saved calibration in EdgeXR. Its file is under
/root/.config/sunfounder-imu-config.json on the tested Pi; leave it untouched
for now.

SunFounder's accel_gyro.read_raw() bypasses the saved calibration but still
converts register values to g and degrees/second. On one stationary two-face
check, Z acceleration changed from +1.269 g to -0.726 g, a nearly 2 g
difference, while gyro readings stayed near (-4.3, +15, -2.7) degrees/second.
The Z midpoint is about +0.271 g, suggesting a persistent offset, but two
faces are insufficient for full three-axis calibration. The driver's SH3001
temperature decoding appears to use the wrong byte order; temperature is
excluded from the IMU baseline until verified.

The first 10-second raw baseline on the Pi returned 98 samples (9.8 samples/s,
limited by the tool's 0.1-second interval). Acceleration mean was
(-0.519, -0.010, +1.273) g, magnitude 1.375 g with 0.003 g standard
deviation. Gyro mean was (-4.186, +15.156, -2.736) degrees/second with
standard deviations (0.184, 0.195, 0.111) degrees/second. The board was
reported stationary and flat; exact face, surface, servo state, and warm-up
time were not recorded. The low spread shows stability during this run, not
absolute accuracy.

The independent two-window check estimated stationary gyro offset
(-4.177, +15.133, -2.747) degrees/second, then measured raw gyro mean
(-4.176, +15.069, -2.717) degrees/second in a separate window. Its corrected
second-window mean was (+0.001, -0.064, +0.030) degrees/second, with standard
deviations (0.178, 0.220, 0.114) degrees/second. This supports short-term
stationary consistency over about 22 seconds. It does not validate angle
measurements during movement, long-term drift, or camera/IMU alignment. The
same run measured 1.373 g acceleration magnitude, still uncalibrated.

The IMU is now taped beside the camera on the moving head; the user confirmed
no relative shifting. Mounted opposite turns produced X/Y/Z angles
(+12.37, +94.27, -0.56) and (-12.49, -101.11, +1.33) degrees. Pan therefore
projects mainly onto Y in this mounting, with an X component. Do not assume
Y alone is an exact camera yaw axis. A 15-second turn/return test ended at
(+0.80, +0.61, +0.86) degrees, with 278 samples and 54.3 ms median spacing.
These manual tests support short-term consistency, not absolute angle accuracy.
See the IMU plan for full conditions and limitations; acceleration remains
uncalibrated. The next experiment is documented in COMBINED_CAPTURE.md.
