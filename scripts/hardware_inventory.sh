#!/usr/bin/env bash
# Read-only inventory helper intended to run on the Raspberry Pi.
# Inputs: no positional arguments. Uses existing uname/vcgencmd/lsusb/v4l2-ctl
# on PATH. Outputs: system/USB/video descriptions on stdout, no saved files.
# Exit: zero after the inventory; a required failing command ends the script.
# Stop on unexpected errors, unset variables and failures inside pipelines.
set -euo pipefail

# Identify the OS/kernel before interpreting any device-specific results.
echo "== System =="
# Print the actual host information, not assumptions about this Raspberry Pi.
uname -a
# vcgencmd is optional; development machines need not provide it.
if command -v vcgencmd >/dev/null 2>&1; then
  # A failed temperature read should not prevent the remaining inventory.
  vcgencmd measure_temp || true
fi

# Use printf so the section separator is an actual newline.
printf '\n== USB devices ==\n'
# Check tool availability without installing or changing packages.
if command -v lsusb >/dev/null 2>&1; then
  # List the USB identities seen by this host.
  lsusb
else
  # Report missing capability rather than pretending no devices are attached.
  echo "lsusb is unavailable; install the package that provides it if needed."
fi

# Video nodes include codec/ISP devices as well as actual camera endpoints.
printf '\n== Video devices ==\n'
# Query only when the existing V4L2 inspection tool is installed.
if command -v v4l2-ctl >/dev/null 2>&1; then
  # List devices without selecting a format, frame rate or camera control.
  v4l2-ctl --list-devices
else
  # Leave installation and hardware configuration as explicit user decisions.
  echo "v4l2-ctl is unavailable; install v4l-utils to inspect camera modes."
fi

# Remind the reader that inventory output is not a hardware reconfiguration.
printf '\nThis script only reports information. It does not change camera settings.\n'
