#!/usr/bin/env bash
# 初始化 HapRay 工作区目录，并将 macOS 工具默认落盘重定向到 <PROJECT_ROOT>。
# 用法：bash skills/hapray/scripts/ensure-workspace-layout.sh [PROJECT_ROOT]
set -euo pipefail

PROJECT_ROOT="$(cd "${1:-.}" && pwd)"

mkdir -p \
  "$PROJECT_ROOT/hapray-release" \
  "$PROJECT_ROOT/reports" \
  "$PROJECT_ROOT/testcases" \
  "$PROJECT_ROOT/logs" \
  "$PROJECT_ROOT/.hapray/runtime" \
  "$PROJECT_ROOT/.hapray/prepare" \
  "$PROJECT_ROOT/.hapray/haptest_reports" \
  "$PROJECT_ROOT/.hapray/gui_agent" \
  "$PROJECT_ROOT/.hapray/hilog" \
  "$PROJECT_ROOT/.hapray/static-output" \
  "$PROJECT_ROOT/.hapray/compare"

if [[ "$(uname -s)" == "Darwin" ]]; then
  mkdir -p "$HOME/ArkAnalyzer-HapRay"
  ln -sfn "$PROJECT_ROOT/reports" "$HOME/ArkAnalyzer-HapRay/reports"
  ln -sfn "$PROJECT_ROOT/logs" "$HOME/ArkAnalyzer-HapRay/logs"
  ln -sfn "$PROJECT_ROOT/.hapray/runtime" "$HOME/ArkAnalyzer-HapRay/runtime"
  ln -sfn "$PROJECT_ROOT/.hapray/prepare" "$HOME/ArkAnalyzer-HapRay/prepare"
  ln -sfn "$PROJECT_ROOT/.hapray/haptest_reports" "$HOME/ArkAnalyzer-HapRay/haptest_reports"
  ln -sfn "$PROJECT_ROOT/.hapray/gui_agent" "$HOME/ArkAnalyzer-HapRay/gui_agent"
  ln -sfn "$PROJECT_ROOT/.hapray/hilog" "$HOME/ArkAnalyzer-HapRay/hilog"
  ln -sfn "$PROJECT_ROOT/.hapray/static-output" "$HOME/ArkAnalyzer-HapRay/static-output"
  ln -sfn "$PROJECT_ROOT/.hapray/compare" "$HOME/ArkAnalyzer-HapRay/compare"
fi

echo "HapRay workspace ready: $PROJECT_ROOT"
echo "  reports/          -> perf/update 采集与 HTML 报告"
echo "  hapray-release/   -> Release 下载与 RUNTIME_ROOT"
echo "  testcases/        -> PerfLoad 用例脚本"
echo "  logs/             -> 会话 CLI 日志"
echo "  hapray-tool-result.json -> CLI 成功且带 --result-file 时写入（本脚本不预创建）"
