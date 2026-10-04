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
