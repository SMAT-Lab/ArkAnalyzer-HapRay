Write-Host "=== HapRay 源码模式构建验证 ===" -ForegroundColor Cyan
Write-Host ""

# 1. Python 环境
Set-Location perf_testing
$pythonCheck = uv run python -m scripts.main --help 2>$null
Set-Location ..
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ 第1步: perf_testing Python 环境" -ForegroundColor Green
} else {
    Write-Host "✗ 第1步: perf_testing Python 环境缺失" -ForegroundColor Red
    Write-Host "   执行: cd perf_testing && uv sync" -ForegroundColor Yellow
}

# 2. Web 构建（3个文件必须同时存在）
$webFiles = @(
    "web/dist/index.html",
    "perf_testing/resource/web/report_template.html",
    "perf_testing/resource/web/hiperf_report_template.html"
)
$webAllExist = $webFiles | ForEach-Object { Test-Path $_ } | Where-Object { $_ -eq $false } | Measure-Object
if ($webAllExist.Count -eq 0) {
    Write-Host "✓ 第2步: Web 构建产物（3/3）" -ForegroundColor Green
} else {
    Write-Host "✗ 第2步: Web 构建产物缺失" -ForegroundColor Red
    Write-Host "   执行: cd web && npm install && npm run build" -ForegroundColor Yellow
    foreach ($file in $webFiles) {
        if (!(Test-Path $file)) {
            Write-Host "   - 缺失: $file" -ForegroundColor Yellow
        }
    }
}

# 3. Static Analyzer
if ((Test-Path dist/tools/sa-cmd/hapray-sa-cmd.js) -or (Test-Path dist/tools/sa-cmd/hapray-sa-cmd.exe)) {
    Write-Host "✓ 第3步: static_analyzer 构建产物" -ForegroundColor Green
} else {
    Write-Host "✗ 第3步: static_analyzer 构建产物缺失" -ForegroundColor Red
    Write-Host "   执行: cd tools/static_analyzer && npm install && npm run build" -ForegroundColor Yellow
}

# 4. Trace Streamer
if (Get-ChildItem dist/tools/bin/trace_streamer_* -ErrorAction SilentlyContinue) {
    Write-Host "✓ 第4步: trace_streamer 可执行文件" -ForegroundColor Green
} else {
    Write-Host "✗ 第4步: trace_streamer 缺失" -ForegroundColor Red
    Write-Host "   执行: npm run prebuild" -ForegroundColor Yellow
}

# 5. Symbol Recovery（必选）
$srPython = "tools/symbol_recovery/.venv/Scripts/python.exe"
if ((Test-Path $srPython) -and (& $srPython tools/symbol_recovery/main.py --help 2>$null)) {
    Write-Host "✓ 第5步: symbol_recovery 虚拟环境" -ForegroundColor Green
} else {
    Write-Host "✗ 第5步: symbol_recovery 虚拟环境缺失" -ForegroundColor Red
    Write-Host "   执行: cd tools/symbol_recovery && uv venv .venv && uv sync" -ForegroundColor Yellow
}

# radare2 + 源码分析插件（建议，非硬门禁）
$r2check = Get-Command r2 -ErrorAction SilentlyContinue
if ($r2check) {
    Write-Host "○ 第5步(建议): radare2 已安装" -ForegroundColor Cyan
    $r2pmList = & r2pm list 2>$null
    if ($r2pmList -match "r2dec|r2ghidra") {
        Write-Host "○ 第5步(建议): 源码分析插件已安装 (r2dec/r2ghidra)" -ForegroundColor Cyan
    } else {
        Write-Host "○ 第5步(建议): 源码分析插件未装，可 r2pm install r2dec（装不上不阻塞 perf/update）" -ForegroundColor Yellow
    }
} else {
    Write-Host "○ 第5步(建议): radare2 未安装，可按上文安装（不阻塞 perf/update）" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== 验证完成 ===" -ForegroundColor Cyan
Write-Host "第1-4步与第5步 Python/venv 全部 OK 后方可执行 perf/update/static；radare2/插件仅为建议项" -ForegroundColor White
