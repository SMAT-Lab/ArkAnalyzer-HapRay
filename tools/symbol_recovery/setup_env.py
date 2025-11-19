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
            command,
            cwd=working_dir,
            check=True,
            shell=platform.system() == 'Windows',
            text=True,
            capture_output=True,
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
        sys.exit(f'Error: Missing Python executable in virtual environment: {python_path}')

    return python_path, pip_path


def setup_virtual_environment() -> None:
    """Create Python virtual environment if it doesn't exist."""
    print(f'\n[1/3] Creating virtual environment: {VENV_NAME}...')
    venv_path = Path(VENV_NAME)

    if venv_path.exists():
        print(f'Virtual environment {VENV_NAME} already exists, skipping creation')
    else:
        execute_command(
            [sys.executable, '-m', 'venv', VENV_NAME],
            error_message='Failed to create virtual environment',
        )
        print(f'Successfully created virtual environment: {VENV_NAME}')

    # Upgrade pip in virtual environment
    print('\n[2/4] Upgrading pip in virtual environment...')
    python_path, pip_path = get_virtualenv_paths()
    execute_command(
        [str(python_path), '-m', 'pip', 'install', '--upgrade', 'pip'],
        error_message='Failed to upgrade pip',
    )
    print('Successfully upgraded pip')


def install_project_dependencies(pip_executable: Path) -> None:
    """Install project dependencies from requirements.txt."""
    print('\n[3/4] Installing project dependencies...')
    print(f'Using pip executable: {pip_executable}')

    requirements_file = Path('requirements.txt')
    if not requirements_file.exists():
        print(f'Warning: {requirements_file} not found, skipping dependency installation')
        return

    try:
        # Install dependencies from requirements.txt
        execute_command(
            [str(pip_executable), 'install', '-r', str(requirements_file)],
            error_message='Failed to install project dependencies',
        )
        print('Successfully installed project dependencies')
    except Exception as e:
        print(f'Error installing project dependencies: {str(e)}')
        raise

    # Install dev dependencies (ruff, tox)
    print('\n[4/4] Installing dev dependencies...')
    try:
        execute_command(
            [str(pip_executable), 'install', 'ruff', 'tox'],
            error_message='Failed to install dev dependencies',
        )
        print('Successfully installed dev dependencies')
    except Exception as e:
        print(f'Warning: Failed to install dev dependencies: {str(e)}')
        # Don't fail if dev dependencies can't be installed


def display_activation_instructions() -> None:
    """Display virtual environment activation instructions."""
    print('\nSetup complete! Next steps:')

    activate_cmd = (
        f'{VENV_NAME}\\Scripts\\activate' if platform.system() == 'Windows' else f'source {VENV_NAME}/bin/activate'
    )

    print(f'\n1. Activate virtual environment:\n   {activate_cmd}\n')
    print('2. Run symbol-recovery:\n   python3 main.py --help\n')


def main() -> None:
    """Main execution flow."""
    setup_virtual_environment()
    python_path, pip_executable = get_virtualenv_paths()
    install_project_dependencies(pip_executable)
    display_activation_instructions()


if __name__ == '__main__':
    main()
