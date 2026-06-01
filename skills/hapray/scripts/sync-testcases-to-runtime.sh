#!/usr/bin/env bash
# 将工作区 testcases 同步到二进制 Release 包内，供 prepare/perf 加载。
# 用法：bash skills/hapray/scripts/sync-testcases-to-runtime.sh <包名> [PROJECT_ROOT] [RUNTIME_ROOT]
set -euo pipefail

PKG="${1:?package name required}"
PROJECT_ROOT="$(cd "${2:-.}" && pwd)"
RUNTIME_ROOT="${3:-$PROJECT_ROOT/hapray-release/runtime}"

find_runtime() {
  if [[ -x "$RUNTIME_ROOT/perf-testing" ]]; then
    echo "$RUNTIME_ROOT/perf-testing"
    return
  fi
  local app="$RUNTIME_ROOT/ArkAnalyzer-HapRay.app/Contents/Resources/tools/perf-testing/perf-testing"
  if [[ -x "$app" ]]; then
    echo "$app"
    return
  fi
  echo "ERROR: perf-testing not found under $RUNTIME_ROOT" >&2
  exit 1
}

PERF_BIN="$(find_runtime)"
INTERNAL="$(dirname "$PERF_BIN")/_internal/hapray/testcases/$PKG"
SRC="$PROJECT_ROOT/testcases/$PKG"

if [[ ! -d "$SRC" ]]; then
  echo "ERROR: no testcases at $SRC" >&2
  exit 1
fi

mkdir -p "$INTERNAL"
cp -f "$SRC"/PerfLoad_* "$INTERNAL/" 2>/dev/null || cp -f "$SRC"/* "$INTERNAL/"
echo "Synced $SRC -> $INTERNAL"
