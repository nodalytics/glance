#!/usr/bin/env bash
# install_deps.sh — idempotent host setup for building glance.
#
# glance links the distro's prebuilt OpenCV (libopencv-dev: 4.x on
# Debian/Ubuntu) and uses FetchContent only for the tiny single-header deps
# (nlohmann/json, cpp-httplib). Host requirements: a C++20 toolchain,
# CMake >= 3.24, libopencv-dev, and (optionally) tesseract-ocr for the OCR
# numeric reads. This script installs exactly what is missing and verifies
# what is present, so it is the one command to bootstrap a fresh machine.
# Re-running it is always safe: apt-get install is idempotent and the version
# checks re-run each time.
#
# Usage (Debian/Ubuntu only):
#   bash research/scripts/install_deps.sh                  # install (may prompt for sudo)
#   SUDO_PASSWORD='xxx' bash research/scripts/install_deps.sh   # non-interactive sudo
#   bash research/scripts/install_deps.sh --check          # report only, install nothing
#
# Notes:
# - tesseract-ocr is optional; without it glance builds fine and reports OCR
#   disabled (numeric fields are simply omitted).
# - glance's CMake build itself is small: it compiles glance's ~10 source
#   files plus the two single-header FetchContent deps. No OpenCV is built.

set -euo pipefail

CHECK_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    -h|--help) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $arg (try --help)" >&2; exit 2 ;;
  esac
done

if ! command -v apt-get >/dev/null 2>&1; then
  echo "error: this script uses apt (Debian/Ubuntu only)" >&2
  exit 1
fi

# sudo strategy: passwordless sudo if the policy allows it, then SUDO_PASSWORD,
# then an interactive prompt.
run_sudo() {
  if [ "$(id -u)" = "0" ]; then
    "$@"
  elif sudo -n true 2>/dev/null; then
    sudo -n "$@"
  elif [ -n "${SUDO_PASSWORD:-}" ]; then
    printf '%s\n' "$SUDO_PASSWORD" | sudo -S -- "$@"
  else
    sudo -- "$@"
  fi
}

have() { command -v "$1" >/dev/null 2>&1; }

pkgs=""
add_pkg() { pkgs="$pkgs $1"; }

# --- C++20 compiler + make -------------------------------------------------
if ! have g++ || ! have make; then
  add_pkg build-essential
fi

# --- CMake >= 3.24 -----------------------------------------------------------
cmake_ok=0
if have cmake; then
  ver=$(cmake --version | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
  major=${ver%%.*}
  minor=${ver#*.}
  minor=${minor%%.*}
  if [ "${major:-0}" -gt 3 ] || { [ "${major:-0}" -eq 3 ] && [ "${minor:-0}" -ge 24 ]; }; then
    cmake_ok=1
  fi
fi
[ "$cmake_ok" -eq 1 ] || add_pkg cmake

# --- git (FetchContent pulls cpp-httplib by git URL) ------------------------
have git || add_pkg git

# --- xz (FetchContent unpacks json.tar.xz) ----------------------------------
have xz || add_pkg xz-utils

# --- libopencv-dev (prebuilt OpenCV 4.x; glance links, never builds, it) ----
have opencv4 || add_pkg libopencv-dev

# --- tesseract-ocr (optional OCR for pot/stack/bet numbers) ------------------
have tesseract || add_pkg tesseract-ocr

# --- report -------------------------------------------------------------------
if [ -z "$pkgs" ]; then
  echo "install_deps: all required tooling present (g++/make, cmake>=3.24, git, xz, tesseract)."
else
  echo "install_deps: missing:$pkgs"
  if [ "$CHECK_ONLY" -eq 1 ]; then
    echo "install_deps: --check mode, nothing installed."
    exit 0
  fi
  DEBIAN_FRONTEND=noninteractive run_sudo apt-get update -qq
  DEBIAN_FRONTEND=noninteractive run_sudo apt-get install -y -qq --no-install-recommends $pkgs
fi

# --- verify --------------------------------------------------------------------
echo "--- verification ---"
g++ --version 2>/dev/null | head -1 || echo "g++: MISSING"
cmake --version 2>/dev/null | head -1 || echo "cmake: MISSING"
pkg-config --modversion opencv4 2>/dev/null | sed 's/^/OpenCV (system): /' || echo "OpenCV (system): MISSING (install: apt-get install libopencv-dev)"
tesseract --version 2>&1 | head -1 || echo "tesseract: not installed (glance will build with OCR disabled)"
echo "install_deps: done. Next: cmake -B build ... (see the repo README)."
