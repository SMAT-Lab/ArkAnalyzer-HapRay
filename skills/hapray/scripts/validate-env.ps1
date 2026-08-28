Write-Host "=== HapRay 源码模式构建验证 ===" -ForegroundColor Cyan
Write-Host ""

# 1. Python 环境
Set-Location perf_testing
$pythonCheck = uv run python -m scripts.main --help 2>$null
Set-Location ..
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Step 1: perf_testing Python" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Step 1: perf_testing Python missing" -ForegroundColor Red
    Write-Host "   Run: cd perf_testing; uv sync" -ForegroundColor Yellow
}

# 2. Web 构建产物（3个文件必须同时存在）
$webFiles = @(
    "web/dist/index.html",
    "perf_testing/resource/web/report_template.html",
    "perf_testing/resource/web/hiperf_report_template.html"
)
$webAllExist = $true
foreach ($f in $webFiles) {
    if (-not (Test-Path $f)) { $webAllExist = $false }
}
if ($webAllExist) {
    Write-Host "[OK] Step 2: Web build (3/3)" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Step 2: Web build missing" -ForegroundColor Red
    Write-Host "   Run: cd web; npm install; npm run build" -ForegroundColor Yellow
    foreach ($file in $webFiles) {
        if (-not (Test-Path $file)) {
            Write-Host "   - Missing: $file" -ForegroundColor Yellow
        }
    }
}

# 3. Static Analyzer
if ((Test-Path dist/tools/sa-cmd/hapray-sa-cmd.js) -or (Test-Path dist/tools/sa-cmd/hapray-sa-cmd.exe)) {
    Write-Host "[OK] Step 3: static_analyzer" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Step 3: static_analyzer missing" -ForegroundColor Red
    Write-Host "   Run: cd tools/static_analyzer; npm install; npm run build" -ForegroundColor Yellow
}

# 4. Trace Streamer
$tsFiles = Get-ChildItem dist/tools/bin/trace_streamer_* -ErrorAction SilentlyContinue
if ($tsFiles) {
    Write-Host "[OK] Step 4: trace_streamer" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Step 4: trace_streamer missing" -ForegroundColor Red
    Write-Host "   Run: npm run prebuild" -ForegroundColor Yellow
}

# 5. Symbol Recovery venv（必选）
$srPython = "tools/symbol_recovery/.venv/Scripts/python.exe"
$srOk = $false
if (Test-Path $srPython) {
    $srHelp = & $srPython tools/symbol_recovery/main.py --help 2>$null
    if ($LASTEXITCODE -eq 0) { $srOk = $true }
}
if ($srOk) {
    Write-Host "[OK] Step 5: symbol_recovery venv" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Step 5: symbol_recovery venv missing" -ForegroundColor Red
    Write-Host "   Run: cd tools/symbol_recovery; uv venv .venv; uv sync" -ForegroundColor Yellow
}

# radare2 + plugins（建议，非硬门禁）
$r2check = Get-Command r2 -ErrorAction SilentlyContinue
if ($r2check) {
    Write-Host "[INFO] Step 5 (optional): radare2 installed" -ForegroundColor Cyan
    $r2pmList = & r2pm list 2>$null
    if ($r2pmList -match "r2dec|r2ghidra") {
        Write-Host "[INFO] Step 5 (optional): decompiler plugins found (r2dec/r2ghidra)" -ForegroundColor Cyan
    } else {
        Write-Host "[INFO] Step 5 (optional): no decompiler plugins; r2pm install r2dec (non-blocking)" -ForegroundColor Yellow
    }
} else {
    Write-Host "[INFO] Step 5 (optional): radare2 not installed (non-blocking)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Verification complete ===" -ForegroundColor Cyan
Write-Host "Steps 1-4 + Step 5 venv must pass before perf/update/static; radare2 is optional" -ForegroundColor White
