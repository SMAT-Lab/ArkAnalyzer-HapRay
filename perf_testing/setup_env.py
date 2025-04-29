import os
import re
import sys
import subprocess
import platform
from pathlib import Path
import zipfile

# Configuration Constants
VENV_NAME = ".venv"
PYTHON_VERSION = (3, 10)
VERSION = "5.0.7.200"

# Path Configuration
CURRENT_DIR = Path(__file__).parent
HYPIUM_ZIP_PATH = CURRENT_DIR.parent / "third-party" / "hypium" / f"hypium-{VERSION}.zip"
HYPIUM_PERF_ZIP_PATH = CURRENT_DIR.parent / "third-party" / "hypium" / f"hypium_perf-{VERSION}.zip"
HYPIUM_DIR = f"hypium-{VERSION}"
REQUIREMENTS_FILE = "requirements.txt"

# Package Installation Order
PACKAGE_INSTALL_ORDER = {
    'xdevice': 0,
    'xdevice-devicetest': 1,
    'xdevice-ohos': 2,
    'hypium': 3,
    'perf_resource': 5,
    'hypium_perf': 6,
    'perf_common': 7,
    'perf_analyzer': 8,
    'perf_collector': 9
}

def validate_python_version() -> bool:
    """Check if current Python version matches required version."""
    return sys.version_info[:2] == PYTHON_VERSION

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

def get_package_files(directory: Path) -> list[Path]:
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

def setup_virtual_environment() -> None:
    """Create Python virtual environment if it doesn't exist."""
    print(f"\n[1/4] Creating virtual environment: {VENV_NAME}...")
    venv_path = Path(VENV_NAME)
    
    if venv_path.exists():
        print(f"Warning: Virtual environment {VENV_NAME} already exists")
        return

    execute_command(
        [sys.executable, "-m", "venv", VENV_NAME],
        error_message="Failed to create virtual environment"
    )

def get_virtualenv_paths() -> tuple[Path, Path]:
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

def extract_hypium_package(zip_path: Path) -> None:
    """
    Extract Hypium package from zip archive.
    
    Args:
        zip_path: Path to the zip file
    """
    print(f"\n[3/4] Processing Hypium package: {zip_path.name}...")
    
    if not zip_path.exists():
        sys.exit(f"Error: Hypium package not found: {zip_path}")

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(HYPIUM_DIR)
        print(f"Extracted to: {HYPIUM_DIR}")
    except zipfile.BadZipFile as e:
        sys.exit(f"Error: Failed to extract {zip_path}: {str(e)}")

def install_project_dependencies(pip_executable: Path) -> None:
    """Install project dependencies from requirements file and Hypium packages."""
    # Install requirements.txt
    requirements_path = Path(REQUIREMENTS_FILE)
    if not requirements_path.exists():
        print(f"\n[4/4] Warning: Requirements file not found: {requirements_path}")
        return

    print(f"\n[4/4] Installing dependencies from {REQUIREMENTS_FILE}...")
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
    if not validate_python_version():
        sys.exit("Error: Requires Python 3.10. Please check your Python version.")
    
    setup_virtual_environment()
    python_executable, pip_executable = get_virtualenv_paths()
    
    extract_hypium_package(HYPIUM_ZIP_PATH)
    extract_hypium_package(HYPIUM_PERF_ZIP_PATH)
    
    install_project_dependencies(pip_executable)
    display_activation_instructions()

if __name__ == "__main__":
    main()
