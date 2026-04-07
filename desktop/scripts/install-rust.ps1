# Rust 安装脚本 - Windows
# 官方文档: https://rustup.rs/
# Windows 需额外安装: Visual Studio Build Tools (Desktop development with C++)

$arch = switch ($env:PROCESSOR_ARCHITECTURE) {
    "ARM64" { "aarch64" }
    "AMD64" { "x86_64" }
    default { "i686" }
}

$url = "https://win.rustup.rs/$arch"
$outFile = "$env:TEMP\rustup-init.exe"

Write-Host "Installing Rust (Windows) - $arch ..."
Invoke-WebRequest -Uri $url -OutFile $outFile -UseBasicParsing

Write-Host "Running rustup-init.exe ..."
Start-Process -FilePath $outFile -ArgumentList "-y" -Wait -NoNewWindow

$cargoBin = "$env:USERPROFILE\.cargo\bin"
if (Test-Path $cargoBin) {
    $env:Path = "$cargoBin;$env:Path"
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$cargoBin*") {
        [Environment]::SetEnvironmentVariable("Path", "$cargoBin;$userPath", "User")
        Write-Host "Cargo has been added to your user PATH. If the current terminal still cannot find cargo, close and reopen the terminal."
    }
}

Write-Host ""
Write-Host "Rust installed successfully!"
