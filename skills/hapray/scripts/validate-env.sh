#!/bin/bash
echo "=== HapRay 源码模式构建验证 ==="
echo ""

# 1. Python 环境
cd perf_testing
if uv run python -m scripts.main --help >/dev/null 2>&1; then
    echo "✓ 第1步: perf_testing Python 环境"
else
    echo "✗ 第1步: perf_testing Python 环境缺失，执行: cd perf_testing && uv sync"
fi
cd ..

# 2. Web 构建（3个文件必须同时存在）
if [ -f web/dist/index.html ] && [ -f perf_testing/resource/web/report_template.html ] && [ -f perf_testing/resource/web/hiperf_report_template.html ]; then
    echo "✓ 第2步: Web 构建产物（3/3）"
else
    echo "✗ 第2步: Web 构建产物缺失，执行: cd web && npm install && npm run build"
    [ -f web/dist/index.html ] || echo "  - 缺失: web/dist/index.html"
    [ -f perf_testing/resource/web/report_template.html ] || echo "  - 缺失: perf_testing/resource/web/report_template.html"
    [ -f perf_testing/resource/web/hiperf_report_template.html ] || echo "  - 缺失: perf_testing/resource/web/hiperf_report_template.html"
fi

# 3. Static Analyzer
if [ -f dist/tools/sa-cmd/hapray-sa-cmd.js ] || [ -f dist/tools/sa-cmd/hapray-sa-cmd.exe ]; then
    echo "✓ 第3步: static_analyzer 构建产物"
else
    echo "✗ 第3步: static_analyzer 构建产物缺失，执行: cd tools/static_analyzer && npm install && npm run build"
fi

# 4. Trace Streamer
if ls dist/tools/bin/trace_streamer_* >/dev/null 2>&1; then
    echo "✓ 第4步: trace_streamer 可执行文件"
else
    echo "✗ 第4步: trace_streamer 缺失，执行: npm run prebuild"
fi

# 5. Symbol Recovery（必选）
if [ -f tools/symbol_recovery/.venv/bin/python ] && \
   tools/symbol_recovery/.venv/bin/python tools/symbol_recovery/main.py --help >/dev/null 2>&1; then
    echo "✓ 第5步: symbol_recovery 虚拟环境"
else
    echo "✗ 第5步: symbol_recovery 虚拟环境缺失"
    echo "   执行: cd tools/symbol_recovery && uv venv .venv && uv sync"
fi

# radare2 + 源码分析插件（建议，非硬门禁）
if command -v r2 >/dev/null 2>&1; then
    echo "○ 第5步(建议): radare2 已安装 ($(r2 -v 2>&1 | head -1))"
    if r2pm list 2>/dev/null | grep -qE "r2dec|r2ghidra"; then
        echo "○ 第5步(建议): 源码分析插件已安装 (r2dec/r2ghidra)"
    else
        echo "○ 第5步(建议): 源码分析插件未装，可执行 r2pm install r2dec（装不上不阻塞 perf/update）"
    fi
else
    echo "○ 第5步(建议): radare2 未安装，可按上文安装（不阻塞 perf/update）"
fi

echo ""
echo "=== 验证完成 ==="
echo "第1–4步与第5步 Python/venv 全部 ✓ 后方可执行 perf/update/static；radare2/插件仅为建议项"
