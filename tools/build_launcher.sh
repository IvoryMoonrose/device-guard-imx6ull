#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
arm-linux-gnueabihf-gcc -static -s -Os -Wall -Wextra -Wno-format-truncation src/fast_launcher.c -o src/device_guard_launcher
file src/device_guard_launcher
