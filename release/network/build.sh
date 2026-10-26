#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
: "${ZIG_BIN:=zig}"
: "${LD64_LLD_BIN:=ld64.lld}"
: "${ZIG_GLOBAL_CACHE_DIR:=$PWD/.zig-global-cache}"
: "${ZIG_LOCAL_CACHE_DIR:=$PWD/.zig-local-cache}"
export ZIG_GLOBAL_CACHE_DIR ZIG_LOCAL_CACHE_DIR
"$ZIG_BIN" cc -target aarch64-ios.14.0 -fobjc-arc -fobjc-runtime=ios-14.0 \
  -fblocks -mno-outline-atomics -O2 -g0 -Wall -Wextra -Werror \
  -c VVProfile15.m -o VVProfile15.o
"$LD64_LLD_BIN" -dylib -arch arm64 -platform_version ios 14.0 15.5 \
  -install_name @rpath/VVProfile15.framework/VVProfile15 \
  -current_version 1.0 -compatibility_version 1.0 -headerpad 0x1000 \
  -dead_strip -adhoc_codesign -o VVProfile15 VVProfile15.o stubs/*.tbd
python3 - <<'PY'
import hashlib
from pathlib import Path
expected = "75dfac48fb9bcb6f63b9148d300a2061d4e0424c958059834151f909e3fac0e3"
actual = hashlib.sha256(Path("VVProfile15").read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit("Framework differs from G; do not replace the verified release binary: " + actual)
print("Framework matches the verified G binary:", actual)
PY
