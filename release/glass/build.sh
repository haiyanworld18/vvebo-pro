#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
: "${ZIG_BIN:=zig}"
: "${LD64_LLD_BIN:=ld64.lld}"
: "${GLASS_OUTPUT_DIR:=/tmp/vvebo-glass-native}"
mkdir -p "$GLASS_OUTPUT_DIR"
"$ZIG_BIN" cc -target aarch64-ios.14.0 -fobjc-arc -fobjc-runtime=ios-14.0 \
  -mno-outline-atomics -O2 -g0 -Wall -Wextra -Werror \
  -c VVGlass.m -o "$GLASS_OUTPUT_DIR/VVGlass.o"
"$LD64_LLD_BIN" -dylib -arch arm64 -platform_version ios 14.0 26.0 \
  -install_name @rpath/VVGlass.framework/VVGlass \
  -current_version 1.0 -compatibility_version 1.0 -headerpad 0x1000 \
  -dead_strip -adhoc_codesign -o "$GLASS_OUTPUT_DIR/VVGlass" \
  "$GLASS_OUTPUT_DIR/VVGlass.o" stubs/*.tbd
