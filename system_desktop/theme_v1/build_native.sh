#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p payload/bin
for name in navd desktop_entry; do
 arm-linux-gnueabihf-gcc -static -s -Os -Wall -Wextra -Wno-format-truncation "runtime_src/$name.c" -o "payload/bin/$name"
done
