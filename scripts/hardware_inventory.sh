#!/usr/bin/env bash
# Read-only inventory helper intended to run on the Raspberry Pi.
set -euo pipefail

echo "== System =="
uname -a
if command -v vcgencmd >/dev/null 2>&1; then
  vcgencmd measure_temp || true
fi

printf '\n== USB devices ==\n'
if command -v lsusb >/dev/null 2>&1; then
  lsusb
else
  echo "lsusb is unavailable; install the package that provides it if needed."
fi

printf '\n== Video devices ==\n'
if command -v v4l2-ctl >/dev/null 2>&1; then
  v4l2-ctl --list-devices
else
  echo "v4l2-ctl is unavailable; install v4l-utils to inspect camera modes."
fi

printf '\nThis script only reports information. It does not change camera settings.\n'
