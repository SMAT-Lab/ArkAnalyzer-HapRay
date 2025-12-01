"""
Copyright (c) 2025 Huawei Device Co., Ltd.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import platform
import subprocess
import sys
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
REQUIREMENTS_FILE = 'requirements.txt'


def execute_command(command: list, working_dir: Path = None, error_message: str = '') -> None:
    """
    Execute a shell command with error handling.

    Args:
        command: List of command arguments
        working_dir: Working directory for the command
        error_message: Custom error message for exception handling
    """
    try:
        result = subprocess.run(
            command, cwd=working_dir, check=True, shell=platform.system() == 'Windows', text=True, capture_output=True
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f'Warning: {result.stderr}')
    except subprocess.CalledProcessError as e:
        print(f'Error: {error_message}')
        print(f'Command: {" ".join(command) if isinstance(command, list) else command}')
        if e.stdout:
            print(f'Output: {e.stdout}')
        if e.stderr:
            print(f'Error output: {e.stderr}')
        sys.exit(1)


def get_virtualenv_paths() -> tuple[Path, Path]:
    """Get paths to virtual environment executables."""
    if platform.system() == 'Windows':
        python_path = Path(VENV_NAME) / 'Scripts' / 'python.exe'
        pip_path = Path(VENV_NAME) / 'Scripts' / 'pip.exe'
    else:
        python_path = Path(VENV_NAME) / 'bin' / 'python'
        pip_path = Path(VENV_NAME) / 'bin' / 'pip'

    if not python_path.exists():
        raise FileNotFoundError(f'Virtual environment Python not found at {python_path}')

    return python_path, pip_path


def create_virtual_environment():
    """Create a new virtual environment."""
    venv_path = Path(VENV_NAME)
    if venv_path.exists():
        print(f'Virtual environment already exists at {venv_path}')
        return

    print(f'Creating virtual environment at {venv_path}...')
    execute_command([sys.executable, '-m', 'venv', VENV_NAME], error_message='Failed to create virtual environment')


def install_dependencies():
    """Install Python dependencies from requirements.txt."""
    python_path, pip_path = get_virtualenv_paths()

    requirements_path = Path(REQUIREMENTS_FILE)
    if not requirements_path.exists():
        print(f'Warning: {REQUIREMENTS_FILE} not found, skipping dependency installation')
        return

    print(f'Installing dependencies from {REQUIREMENTS_FILE}...')
    # 使用 python -m pip 来避免权限问题
    execute_command(
        [str(python_path), '-m', 'pip', 'install', '--upgrade', 'pip'], error_message='Failed to upgrade pip'
    )
    execute_command(
        [str(python_path), '-m', 'pip', 'install', '-r', str(requirements_path)],
        error_message=f'Failed to install dependencies from {REQUIREMENTS_FILE}',
    )

    # Install pyinstaller for building
    print('Installing PyInstaller...')
    execute_command(
        [str(python_path), '-m', 'pip', 'install', 'pyinstaller'], error_message='Failed to install PyInstaller'
    )


def main():
    """Main setup function."""
    print('=' * 60)
    print('HapRay GUI Environment Setup')
    print('=' * 60)

    # Get current directory
    current_dir = Path(__file__).parent.resolve()
    print(f'Working directory: {current_dir}')

    # Create virtual environment
    create_virtual_environment()

    # Install dependencies
    install_dependencies()

    print('=' * 60)
    print('Setup completed successfully!')
    print('=' * 60)
    print(f'Virtual environment: {current_dir / VENV_NAME}')
    print('To activate the virtual environment:')
    if platform.system() == 'Windows':
        print(f'  {VENV_NAME}\\Scripts\\activate')
    else:
        print(f'  source {VENV_NAME}/bin/activate')
    print('To run the application:')
    print('  npm run run:venv')
    print('To build the application:')
    print('  npm run build')


if __name__ == '__main__':
    main()
