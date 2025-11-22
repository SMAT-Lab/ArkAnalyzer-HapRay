@echo off
REM HapRay GUI 打包脚本 (Windows)
REM 包含后处理步骤：共享 Python 运行时

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."
set "DIST_DIR=%ROOT_DIR%\dist"

echo ==========================================
echo HapRay GUI 打包脚本
echo ==========================================
echo 项目根目录: %ROOT_DIR%
echo 输出目录: %DIST_DIR%
echo.

REM 检查虚拟环境
if exist "%SCRIPT_DIR%\.venv\Scripts\pyinstaller.exe" (
    set "PYINSTALLER=%SCRIPT_DIR%\.venv\Scripts\pyinstaller.exe"
) else if exist "%SCRIPT_DIR%\venv\Scripts\pyinstaller.exe" (
    set "PYINSTALLER=%SCRIPT_DIR%\venv\Scripts\pyinstaller.exe"
) else (
    set "PYINSTALLER=pyinstaller"
)

echo 使用 PyInstaller: %PYINSTALLER%
echo.

REM 进入 hapray-gui 目录
cd /d "%SCRIPT_DIR%"

REM 打包 GUI
echo 正在打包 GUI...
%PYINSTALLER% -y main.spec

REM 移动可执行文件到根目录的 dist
set "GUI_BUILD_DIR=%SCRIPT_DIR%\dist\hapray-gui"
set "GUI_EXE=%GUI_BUILD_DIR%\HapRay-GUI.exe"
set "ROOT_DIST_GUI=%DIST_DIR%\HapRay-GUI.exe"

if exist "%GUI_EXE%" (
    echo.
    echo 移动 GUI 可执行文件到根目录 dist...
    if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"
    if exist "%ROOT_DIST_GUI%" del /f /q "%ROOT_DIST_GUI%"
    move "%GUI_EXE%" "%ROOT_DIST_GUI%"
    echo ✓ 已移动: %ROOT_DIST_GUI%
) else (
    echo 警告: 未找到 GUI 可执行文件: %GUI_EXE%
)

REM 打包 CMD
echo.
echo 正在打包 CMD...
%PYINSTALLER% -y cmd.spec

REM 移动可执行文件到根目录的 dist
set "CMD_BUILD_DIR=%SCRIPT_DIR%\dist\hapray-cmd"
set "CMD_EXE=%CMD_BUILD_DIR%\hapray-cmd.exe"
set "ROOT_DIST_CMD=%DIST_DIR%\hapray-cmd.exe"

if exist "%CMD_EXE%" (
    echo.
    echo 移动 CMD 可执行文件到根目录 dist...
    if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"
    if exist "%ROOT_DIST_CMD%" del /f /q "%ROOT_DIST_CMD%"
    move "%CMD_EXE%" "%ROOT_DIST_CMD%"
    echo ✓ 已移动: %ROOT_DIST_CMD%
) else (
    echo 警告: 未找到 CMD 可执行文件: %CMD_EXE%
)

REM 运行后处理脚本：共享 Python 运行时
echo.
echo 正在共享 Python 运行时...
set "PYTHON_CMD=python"
if exist "%SCRIPT_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%SCRIPT_DIR%\.venv\Scripts\python.exe"
) else if exist "%SCRIPT_DIR%\venv\Scripts\python.exe" (
    set "PYTHON_CMD=%SCRIPT_DIR%\venv\Scripts\python.exe"
)

%PYTHON_CMD% "%SCRIPT_DIR%\share_python_runtime.py" "%DIST_DIR%"

echo.
echo ==========================================
echo ✓ 打包完成！
echo ==========================================
echo GUI 位置: %ROOT_DIST_GUI%
echo CMD 位置: %ROOT_DIST_CMD%
echo 工具目录: %DIST_DIR%\tools
echo 共享 Python 运行时: %DIST_DIR%\_shared_python\Python3.framework
echo.

endlocal

