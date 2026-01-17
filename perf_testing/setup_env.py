import os
import platform
import re
import subprocess
import sys
import zipfile
from pathlib import Path

# Version requirements
MIN_PYTHON_VERSION = (3, 9)
MAX_PYTHON_VERSION = (3, 12)


def check_python_version():
    """Check if the current Python version meets the requirements."""
    current_version = sys.version_info[:2]
    if not (MIN_PYTHON_VERSION <= current_version <= MAX_PYTHON_VERSION):
        print(
            f'Error: Python version must be between {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} and {MAX_PYTHON_VERSION[0]}.{MAX_PYTHON_VERSION[1]}'
        )
        print(f'Current Python version: {current_version[0]}.{current_version[1]}')
        sys.exit(1)


# Check Python version before proceeding
check_python_version()

# Configuration Constants
VENV_NAME = '.venv'
VERSION = '5.0.7.200'

# Path Configuration
CURRENT_DIR = Path(os.path.abspath(Path(__file__).parent))
HYPIUM_ZIP_PATH = CURRENT_DIR.parent / 'third-party' / f'hypium-{VERSION}.zip'

HYPIUM_DIR = f'hypium-{VERSION}'
REQUIREMENTS_FILE = 'requirements.txt'

# Phone-agent Configuration
PHONE_AGENT_REPO_URL = 'https://gitcode.com/zai-org/Open-AutoGLM.git'
PHONE_AGENT_DIR = 'Open-AutoGLM'

# Package Installation Order
PACKAGE_INSTALL_ORDER = {'xdevice': 0, 'xdevice-devicetest': 1, 'xdevice-ohos': 2, 'hypium': 3}


def execute_command(command: list, working_dir: Path = None, error_message: str = '') -> None:
    """
    Execute a shell command with error handling.

    Args:
        command: List of command arguments
        working_dir: Working directory for the command
        error_message: Custom error message for exception handling
    """
    try:
        result = subprocess.run(command, cwd=working_dir, check=True, shell=platform.system() == 'Windows', text=True)
        print(result.stdout)
        if result.stderr:
            print(f'Warning: {result.stderr}')
    except subprocess.CalledProcessError as e:
        print(f'Error: {error_message}')
        print(f'Command: {e.cmd}')
        print(f'Error output: {e.stderr}')
        sys.exit(1)


def get_package_files(directory: Path) -> list[Path]:
    """Get all .tar.gz and .whl files in the specified directory."""
    return [file for file in directory.iterdir() if file.suffix in ('.tar.gz', '.whl') or file.name.endswith('.tar.gz')]


def extract_package_prefix(file_name: str) -> str:
    """
    Extract package name prefix from a package filename.

    Args:
        file_name: Name of the package file (e.g., "perf_analyzer-5.0.7.200b0-py3-none-any.whl")

    Returns:
        Extracted package name prefix (e.g., "perf_analyzer")
    """
    patterns = [
        r'^([a-zA-Z0-9_]+?)-\d.*\.(whl|tar\.gz)$',  # Standard package naming
        r'^([a-zA-Z0-9_-]+?)-\d+[a-zA-Z0-9.]*\.(whl|tar\.gz)$',  # Complex package names
    ]

    for pattern in patterns:
        match = re.match(pattern, file_name)
        if match:
            prefix = match.group(1)
            # Filter numeric suffixes
            if any(c.isdigit() for c in prefix.split('-')[-1]):
                return '-'.join(prefix.split('-')[:-1])
            return prefix
    return ''


def setup_virtual_environment() -> None:
    """Create Python virtual environment if it doesn't exist."""
    print(f'\n[1/4] Creating virtual environment: {VENV_NAME}...')
    venv_path = Path(VENV_NAME)

    if venv_path.exists():
        print(f'Warning: Virtual environment {VENV_NAME} already exists')
        return

    execute_command([sys.executable, '-m', 'venv', VENV_NAME], error_message='Failed to create virtual environment')


def get_virtualenv_paths() -> tuple[Path, Path]:
    """Get paths to virtual environment executables."""
    if platform.system() == 'Windows':
        python_path = Path(VENV_NAME) / 'Scripts' / 'python.exe'
        pip_path = Path(VENV_NAME) / 'Scripts' / 'pip.exe'
    else:
        python_path = Path(VENV_NAME) / 'bin' / 'python'
        pip_path = Path(VENV_NAME) / 'bin' / 'pip'

    if not python_path.exists():
        sys.exit(f'Error: Missing Python executable in virtual environment: {python_path}')

    return python_path, pip_path


def extract_package(zip_path: Path, extractall_dir: Path) -> None:
    """
    Extract package from zip archive.

    Args:
        zip_path: Path to the zip file
    """
    print(f'\n[2/4] Extract package: {zip_path.name}...')

    if not zip_path.exists():
        sys.exit(f'Error: package not found: {zip_path}')
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extractall_dir)
        print(f'Extracted to: {extractall_dir}')
    except zipfile.BadZipFile as e:
        sys.exit(f'Error: Failed to extract {zip_path}: {str(e)}')


def install_project_dependencies(pip_executable: Path) -> None:
    """Install project dependencies from requirements file and Hypium packages."""
    # Install requirements.txt
    requirements_path = Path(REQUIREMENTS_FILE)
    if not requirements_path.exists():
        print(f'\n[3/4] Warning: Requirements file not found: {requirements_path}')
        return

    print(f'\n[3/4] Installing dependencies from {REQUIREMENTS_FILE}...')
    print(f'Using pip executable: {pip_executable}')
    print(f'Requirements file path: {requirements_path}')

    try:
        execute_command(
            [str(pip_executable), 'install', '-r', str(requirements_path)],
            error_message='Failed to install requirements',
        )
        print('Successfully installed requirements')
    except Exception as e:
        print(f'Error installing requirements: {str(e)}')
        raise

    # Install Hypium packages in specific order
    packages_dir = Path(HYPIUM_DIR)
    package_files = get_package_files(packages_dir)

    package_files.sort(key=lambda p: PACKAGE_INSTALL_ORDER.get(extract_package_prefix(p.name), float('inf')))

    for package in package_files:
        print(f'Installing package: {package.name}')
        try:
            execute_command(
                [str(pip_executable), 'install', str(package)],
                error_message=f'Failed to install package: {package.name}',
            )
            print(f'Successfully installed {package.name}')
        except Exception as e:
            print(f'Error installing {package.name}: {str(e)}')
            raise


def install_phone_agent(pip_executable: Path) -> None:
    """Install phone-agent library from git repository."""
    print('\n[4/4] Installing phone-agent library...')

    phone_agent_path = CURRENT_DIR / '..' / 'third-party' / PHONE_AGENT_DIR

    # Clone repository if it doesn't exist
    if not phone_agent_path.exists():
        print(f'Cloning repository: {PHONE_AGENT_REPO_URL}...')
        try:
            execute_command(
                ['git', 'clone', PHONE_AGENT_REPO_URL, str(phone_agent_path)],
                working_dir=CURRENT_DIR,
                error_message='Failed to clone phone-agent repository',
            )
            print(f'Successfully cloned repository to: {phone_agent_path}')
        except Exception as e:
            print(f'Error cloning repository: {str(e)}')
            raise
    else:
        print(f'Repository already exists at: {phone_agent_path}')
        print('Skipping clone step')

    # Install requirements.txt from the cloned repository
    requirements_path = phone_agent_path / 'requirements.txt'
    if requirements_path.exists():
        print(f'Installing requirements from: {requirements_path}')
        try:
            execute_command(
                [str(pip_executable), 'install', '-r', str(requirements_path)],
                error_message='Failed to install phone-agent requirements',
            )
            print('Successfully installed phone-agent requirements')
        except Exception as e:
            print(f'Error installing phone-agent requirements: {str(e)}')
            raise
    else:
        print(f'Warning: requirements.txt not found in {phone_agent_path}')

    print('Installing phone-agent...')
    try:
        execute_command(
            [str(pip_executable), 'install', str(phone_agent_path)],
            error_message='Failed to install phone-agent',
        )
        print('Successfully installed phone-agent')
    except Exception as e:
        print(f'Error installing phone-agent: {str(e)}')
        raise


def display_activation_instructions() -> None:
    """Display virtual environment activation instructions."""
    print('\nSetup complete! Next steps:')

    activate_cmd = (
        f'{VENV_NAME}\\Scripts\\activate' if platform.system() == 'Windows' else f'source {VENV_NAME}/bin/activate'
    )

    print(f'\n1. Activate virtual environment:\n   {activate_cmd}\n')


def main() -> None:
    """Main execution flow."""

    setup_virtual_environment()
    _, pip_executable = get_virtualenv_paths()

    extract_package(HYPIUM_ZIP_PATH, HYPIUM_DIR)

    install_project_dependencies(pip_executable)
    install_phone_agent(pip_executable)
    display_activation_instructions()


if __name__ == '__main__':
    main()
