import re
import sys
import os
import subprocess
import platform
from pathlib import Path
import zipfile
from typing import List, Tuple
import shutil

# Version requirements
MIN_PYTHON_VERSION = (3, 9)
MAX_PYTHON_VERSION = (3, 12)


def check_python_version():
    """Check if the current Python version meets the requirements."""
    current_version = sys.version_info[:2]
    if not (MIN_PYTHON_VERSION <= current_version <= MAX_PYTHON_VERSION):
        print(
            f"Error: Python version must be between {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} and {MAX_PYTHON_VERSION[0]}.{MAX_PYTHON_VERSION[1]}")
        print(f"Current Python version: {current_version[0]}.{current_version[1]}")
        sys.exit(1)


# Check Python version before proceeding
check_python_version()

# Configuration Constants
VENV_NAME = ".venv"
VERSION = "5.0.7.200"

# Path Configuration
CURRENT_DIR = Path(os.path.abspath(Path(__file__).parent))
HYPIUM_ZIP_PATH = CURRENT_DIR.parent / "third-party" / f"hypium-{VERSION}.zip"
HISMARTPERF_ZIP_PATH = CURRENT_DIR.parent / "third-party" / "HiSmartPerf_20250109.zip"

HYPIUM_DIR = f"hypium-{VERSION}"
HISMARTPERF_DIR = "HiSmartPerf_20250109"
REQUIREMENTS_FILE = "requirements.txt"

# Package Installation Order
PACKAGE_INSTALL_ORDER = {
    'xdevice': 0,
    'xdevice-devicetest': 1,
    'xdevice-ohos': 2,
    'hypium': 3
}


def execute_command(command: list, working_dir: Path = None, error_message: str = "") -> None:
    """
    Execute a shell command with error handling.
    
    Args:
        command: List of command arguments
        working_dir: Working directory for the command
        error_message: Custom error message for exception handling
    """
    try:
        subprocess.run(
            command,
            cwd=working_dir,
            check=True,
            shell=platform.system() == "Windows",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Error: {error_message}")
        print(f"Command: {e.cmd}")
        print(f"Error output: {e.stderr}")
        sys.exit(1)


def get_package_files(directory: Path) -> List[Path]:
    """Get all .tar.gz and .whl files in the specified directory."""
    return [
        file for file in directory.iterdir()
        if file.suffix in ('.tar.gz', '.whl') or file.name.endswith('.tar.gz')
    ]


def extract_package_prefix(file_name: str) -> str:
    """
    Extract package name prefix from a package filename.
    
    Args:
        file_name: Name of the package file (e.g., "perf_analyzer-5.0.7.200b0-py3-none-any.whl")
    
    Returns:
        Extracted package name prefix (e.g., "perf_analyzer")
    """
    patterns = [
        r"^([a-zA-Z0-9_]+?)-\d.*\.(whl|tar\.gz)$",  # Standard package naming
        r"^([a-zA-Z0-9_-]+?)-\d+[a-zA-Z0-9.]*\.(whl|tar\.gz)$"  # Complex package names
    ]

    for pattern in patterns:
        match = re.match(pattern, file_name)
        if match:
            prefix = match.group(1)
            # Filter numeric suffixes
            if any(c.isdigit() for c in prefix.split('-')[-1]):
                return '-'.join(prefix.split('-')[:-1])
            return prefix
    return ""


def download_strat_smart_perf() -> None:
    print("downloading smart-perf")
    # 规范化目录路径
    directory = Path(CURRENT_DIR.parent).expanduser().resolve()

    # 检查目录是否存在
    if not directory.exists():
        print(f"错误: 目录 '{directory}' 不存在")

    if not directory.is_dir():
        print(f"错误: '{directory}' 不是一个目录")

    # 检查目录中是否有package.json文件
    package_json = directory / "package.json"
    if not package_json.exists():
        print(f"错误: 目录 '{directory}' 中未找到package.json文件")
    # 查找 npm 可执行文件
    npm_cmd = shutil.which('npm.cmd') if os.name == 'nt' else shutil.which('npm')
    # 构建npm命令
    if os.name == "nt":  # Windows系统
        npm_cmd = [npm_cmd, "run", "downloadHiSmartPerfPackage"]
    else:  # Linux/macOS
        npm_cmd = [npm_cmd, "run", "downloadHiSmartPerfPackage"]

    execute_command(
        npm_cmd,
        error_message="Failed to download hi_smart_perf"
    )


def start_hi_smart_perf(binary_name) -> None:
    """
    根据当前操作系统选择并执行对应的可执行文件

    参数:
        binary_name (str): 可执行文件的基础名称（不含扩展名）
    """
    # 获取当前操作系统
    current_os = platform.system()

    # 根据操作系统确定可执行文件扩展名和名称
    if current_os == "Windows":
        executable_path = f"{binary_name}.exe"
    elif current_os == "Darwin":  # macOS
        executable_path = f"{binary_name}_darwin"
    elif current_os == "Linux":
        executable_path = f"{binary_name}_linux"
    else:
        raise RuntimeError(f"不支持的操作系统: {current_os}")

    # 转换为绝对路径并验证文件存在
    executable_path = Path(CURRENT_DIR.parent / "third-party" / HISMARTPERF_DIR / executable_path).resolve()
    if not executable_path.exists():
        raise FileNotFoundError(f"找不到可执行文件: {executable_path}")

    # 确保 macOS/Linux 上的可执行文件有执行权限
    if current_os in ["Darwin", "Linux"]:
        if not os.access(executable_path, os.X_OK):
            os.chmod(executable_path, 0o755)

    # 构建命令
    cmd = [str(executable_path)]
    execute_command(
        cmd,
        error_message="Failed to start_hi_smart_perf"
    )


def setup_virtual_environment() -> None:
    """Create Python virtual environment if it doesn't exist."""
    print(f"\n[1/3] Creating virtual environment: {VENV_NAME}...")
    venv_path = Path(VENV_NAME)

    if venv_path.exists():
        print(f"Warning: Virtual environment {VENV_NAME} already exists")
        return

    execute_command(
        [sys.executable, "-m", "venv", VENV_NAME],
        error_message="Failed to create virtual environment"
    )


def get_virtualenv_paths() -> Tuple[Path, Path]:
    """Get paths to virtual environment executables."""
    if platform.system() == "Windows":
        python_path = Path(VENV_NAME) / "Scripts" / "python.exe"
        pip_path = Path(VENV_NAME) / "Scripts" / "pip.exe"
    else:
        python_path = Path(VENV_NAME) / "bin" / "python"
        pip_path = Path(VENV_NAME) / "bin" / "pip"

    if not python_path.exists():
        sys.exit(f"Error: Missing Python executable in virtual environment: {python_path}")

    return python_path, pip_path


def extract_package(zip_path: Path, extractall_dir: Path) -> None:
    """
    Extract package from zip archive.
    
    Args:
        zip_path: Path to the zip file
    """
    print(f"\n[2/3] Extract package: {zip_path.name}...")

    if not zip_path.exists():
        sys.exit(f"Error: package not found: {zip_path}")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extractall_dir)
        print(f"Extracted to: {extractall_dir}")
    except zipfile.BadZipFile as e:
        sys.exit(f"Error: Failed to extract {zip_path}: {str(e)}")


def install_project_dependencies(pip_executable: Path) -> None:
    """Install project dependencies from requirements file and Hypium packages."""
    # Install requirements.txt
    requirements_path = Path(REQUIREMENTS_FILE)
    if not requirements_path.exists():
        print(f"\n[3/3] Warning: Requirements file not found: {requirements_path}")
        return

    print(f"\n[3/3] Installing dependencies from {REQUIREMENTS_FILE}...")
    execute_command(
        [str(pip_executable), "install", "-r", str(requirements_path)],
        error_message="Failed to install requirements"
    )

    # Install Hypium packages in specific order
    packages_dir = Path(HYPIUM_DIR)
    package_files = get_package_files(packages_dir)

    package_files.sort(key=lambda p: PACKAGE_INSTALL_ORDER.get(extract_package_prefix(p.name), float('inf')))

    for package in package_files:
        print(f"Installing package: {package.name}")
        execute_command(
            [str(pip_executable), "install", str(package)],
            error_message=f"Failed to install package: {package.name}"
        )


def display_activation_instructions() -> None:
    """Display virtual environment activation instructions."""
    print("\nSetup complete! Next steps:")

    activate_cmd = (
        f"{VENV_NAME}\\Scripts\\activate" if platform.system() == "Windows"
        else f"source {VENV_NAME}/bin/activate"
    )

    print(f"\n1. Activate virtual environment:\n   {activate_cmd}\n")


def main() -> None:
    """Main execution flow."""


    setup_virtual_environment()
    _, pip_executable = get_virtualenv_paths()

    download_strat_smart_perf()
    extract_package(HISMARTPERF_ZIP_PATH, HISMARTPERF_ZIP_PATH.parent)
    extract_package(HYPIUM_ZIP_PATH, HYPIUM_DIR)

    install_project_dependencies(pip_executable)
    display_activation_instructions()

    start_hi_smart_perf('main')


if __name__ == "__main__":
    main()
