#!/usr/bin/env bash
# install_opencv.sh — one-time host setup: install the distro's prebuilt OpenCV.
#
# glance links the distro's prebuilt OpenCV (libopencv-dev) and NEVER builds
# it from source: the from-source 5.1.0 build was broken on AVX-512 + g++ 13
# (impossible matchTemplate scores, heap corruption; Nov 2026). The distro
# package is Canonical/maintainer-built and works everywhere, so this is the
# OpenCV setup for any machine (lab, CI, laptop).
#
# Run ON the machine to be set up (Debian/Ubuntu only):
#   bash research/scripts/install_opencv.sh            # sudo prompts interactively
#   SUDO_PASSWORD='xxx' bash research/scripts/install_opencv.sh   # non-interactive
#
# Idempotent: safe to re-run; apt-get install is a no-op when satisfied.

set -euo pipefail

if [ -n "${SUDO_PASSWORD:-}" ]; then
  run() { printf '%s\n' "$SUDO_PASSWORD" | sudo -S "$@"; }
else
  run() { sudo "$@"; }
fi

run apt-get update -qq
run apt-get install -y -qq libopencv-dev

echo "OpenCV (system): $(pkg-config --modversion opencv4 2>/dev/null || echo MISSING)"
echo "install_opencv: done."
