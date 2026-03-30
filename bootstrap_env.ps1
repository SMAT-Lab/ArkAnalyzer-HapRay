[CmdletBinding()]
param(
    [string]$NodeVersion = "24",
    [string]$PythonVersion = "3.11",
    [string]$ProjectRoot = "",
    [switch]$ForceUpdateVersionFiles,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message"
}

function Run-Cmd([string]$Command) {
    Write-Host "`$ $Command"
    if ($DryRun) { return }
    Invoke-Expression $Command
}

# winget/choco 安装 nvm-windows 后只更新注册表中的 Path，当前会话不会立刻看到 nvm
function Refresh-SessionPathFromRegistry {
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $segments = @()
    if ($machine) { $segments += $machine }
    if ($user) { $segments += $user }
    $env:Path = ($segments -join ";")
    foreach ($scope in @("Machine", "User")) {
        $nvmHome = [System.Environment]::GetEnvironmentVariable("NVM_HOME", $scope)
        if ($nvmHome) {
            $env:NVM_HOME = $nvmHome
            break
        }
    }
}

function Get-NvmExePath {
    $cmd = Get-Command nvm -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    Refresh-SessionPathFromRegistry
    $cmd = Get-Command nvm -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        $(if ($env:NVM_HOME) { Join-Path $env:NVM_HOME "nvm.exe" }),
        $(Join-Path $env:ProgramFiles "nvm\nvm.exe"),
        (Join-Path $env:APPDATA "nvm\nvm.exe")
    ) | Where-Object { $_ }
    foreach ($p in $candidates) {
        if ($p -and (Test-Path -LiteralPath $p)) { return $p }
    }
    return $null
}

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path $PSScriptRoot).Path
} else {
    $ProjectRoot = (Resolve-Path $ProjectRoot).Path
}

$nvmrcPath = Join-Path $ProjectRoot ".nvmrc"
$pyverPath = Join-Path $ProjectRoot ".python-version"

if (-not $ForceUpdateVersionFiles) {
    if (Test-Path $nvmrcPath) {
        $NodeVersion = (Get-Content $nvmrcPath -Raw).Trim()
    }
    if (Test-Path $pyverPath) {
        $PythonVersion = (Get-Content $pyverPath -Raw).Trim()
    }
}

Write-Host "Bootstrapping:"
Write-Host "- Project root: $ProjectRoot"
Write-Host "- Node.js: $NodeVersion"
Write-Host "- Python: $PythonVersion"
Write-Host "- Dry run: $DryRun"

Step "Working directory: $ProjectRoot"
Set-Location $ProjectRoot

function Write-VersionFile([string]$Path, [string]$Value) {
    if ($DryRun) {
        Write-Host "[dry-run] Would update $Path -> $Value"
        return
    }
    Set-Content -Path $Path -Value ($Value + "`n") -NoNewline:$false
    Write-Host "Updated $Path"
}

if ($ForceUpdateVersionFiles) {
    Write-VersionFile $nvmrcPath $NodeVersion
    Write-VersionFile $pyverPath $PythonVersion
} else {
    if (Test-Path $nvmrcPath) {
        Write-Host "Using project-managed .nvmrc: $NodeVersion"
    } else {
        Write-VersionFile $nvmrcPath $NodeVersion
    }
    if (Test-Path $pyverPath) {
        Write-Host "Using project-managed .python-version: $PythonVersion"
    } else {
        Write-VersionFile $pyverPath $PythonVersion
    }
}

Step "Checking uv"
$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCmd) {
    Step "Installing uv"
    Run-Cmd "powershell -NoProfile -ExecutionPolicy Bypass -Command `"irm https://astral.sh/uv/install.ps1 | iex`""
    if (-not $DryRun) {
        $env:Path = "$HOME\.local\bin;$env:Path"
    }
} else {
    Write-Host "uv found: $($uvCmd.Source)"
}

Step "Checking nvm (Windows)"
$nvmCmd = Get-Command nvm -ErrorAction SilentlyContinue
if (-not $nvmCmd) {
    Step "Installing nvm-windows"
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Run-Cmd "winget install --id CoreyButler.NVMforWindows -e --source winget --accept-source-agreements --accept-package-agreements"
    } elseif (Get-Command choco -ErrorAction SilentlyContinue) {
        Run-Cmd "choco install nvm -y"
    } elseif (Get-Command scoop -ErrorAction SilentlyContinue) {
        Run-Cmd "scoop install nvm"
    } else {
        throw "No supported package manager found. Please install nvm-windows manually."
    }
    if (-not $DryRun) {
        Refresh-SessionPathFromRegistry
    }
}

Step "Installing Node.js $NodeVersion"
if ($DryRun) {
    Write-Host "`$ nvm install $NodeVersion"
    Write-Host "`$ nvm use $NodeVersion"
} else {
    Refresh-SessionPathFromRegistry
    $nvmExe = Get-NvmExePath
    if (-not $nvmExe) {
        throw "nvm.exe not found after install. Close this window, open a new PowerShell, then run bootstrap_env.ps1 again (or add nvm to PATH)."
    }
    Write-Host "`$ nvm install $NodeVersion"
    & $nvmExe install $NodeVersion
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "`$ nvm use $NodeVersion"
    & $nvmExe use $NodeVersion
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    # 刷新 PATH，使当前会话内可立即使用 node/npm（nvm-windows 会更新 nodejs 目录）
    Refresh-SessionPathFromRegistry
}

Step "Installing Python $PythonVersion via uv"
Run-Cmd "uv python install $PythonVersion"

Step "Creating .venv"
Run-Cmd "uv venv --python $PythonVersion"

Step "Bootstrap completed"
Write-Host "Next steps:"
Write-Host "- This session already ran nvm use; try: node -v"
Write-Host "- In a new terminal, nvm-windows uses your default alias; or run: nvm use $NodeVersion"
