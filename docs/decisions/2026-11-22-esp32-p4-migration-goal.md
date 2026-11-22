# Add a fourth goal: migrate a reduced EdgeXR to the ESP32-P4-Nano

## User direction

On 2026-11-22 the user added a new goal: migrate the spatial-vision program from
the Raspberry Pi 4 to an ESP32-P4-Nano board (ESP32-P4: dual RISC-V cores up to
400 MHz, 768 KB SRAM, 32 MB PSRAM, MIPI-CSI camera input with ISP, hardware JPEG
codec, USB 2.0 high-speed host; datasheet values to verify on the board), using
the Tang Primer 20K where it helps.

The user explicitly asked that **nothing in the existing plan be changed or
removed**: the Pi version of EdgeXR, the reading plan, the RISC-V CPU on the FPGA,
the accelerator, the user-written kernel driver and the C rewriting all stay as
scheduled. The migration is **added after them**, starting after June 2027, with
one optional small probe in March that does not displace any planned work.

## Scope

A reduced "EdgeXR-lite" rewritten in C/C++ on ESP-IDF (FreeRTOS), not a copy of
the Python/OpenCV program: gyro orientation, bearings, object memory, servo
control, low-resolution image motion, a lighter feature matcher and an 8-bit
quantized detector. No Linux on the P4, so the kernel-driver work remains on the
Pi. Estimated 3–4 months (July–October 2027) at the current weekly pace; this is
an estimate, and ports usually take longer than planned.

## Constraints

- Hardware changes (wiring the IMU and servos directly to the P4, a new camera if
  the OV9281 cannot be read over the P4's USB host) need a reviewed procedure.
- Downloading models or toolchains and buying parts need explicit approval.
- Pi results remain the reference; P4 claims need their own measurements.

Roadmap: [SYSTEMS_AND_AP_EXTENSIONS.md](../SYSTEMS_AND_AP_EXTENSIONS.md#added-goal-reduced-edgexr-on-the-esp32-p4-nano).
