#!/usr/bin/env bash
# Read-only inventory helper intended to run on the Raspberry Pi.
# Inputs: no positional arguments. Uses existing uname/vcgencmd/lsusb/v4l2-ctl
# on PATH. Outputs: system/USB/video descriptions on stdout, no saved files.
# Exit: zero after the inventory; a required failing command ends the script.
set -euo pipefail

# Identify the host and read temperature when the Pi tool is available.
# A missing tool or failed temperature read must not block device inventory.
echo "== System =="
uname -a
if command -v vcgencmd >/dev/null 2>&1; then
  vcgencmd measure_temp || true
fi

# List USB identities using the existing tool, or explain the missing capability.
# No package is installed and no device is configured by this helper.
printf '\n== USB devices ==\n'
if command -v lsusb >/dev/null 2>&1; then
  lsusb
else
  echo "lsusb is unavailable; install the package that provides it if needed."
fi

# Video nodes include codec/ISP devices as well as actual camera endpoints.
# Enumerate them without selecting a capture format, rate or exposure control.
printf '\n== Video devices ==\n'
if command -v v4l2-ctl >/dev/null 2>&1; then
  v4l2-ctl --list-devices
else
  echo "v4l2-ctl is unavailable; install v4l-utils to inspect camera modes."
fi

printf '\nThis script only reports information. It does not change camera settings.\n'
