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

## IMU verification checklist

First record raw accelerometer and gyroscope readings while the board is still,
then rotate it slowly about one axis at a time. Label its board orientation in a
photo or diagram stored outside Git if needed. Do not combine IMU data with
camera tracking until the raw readings, units, sample rate, and coordinate
convention are understood.
