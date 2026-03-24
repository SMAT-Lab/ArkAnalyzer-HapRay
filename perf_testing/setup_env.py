import os
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

# Path Configuration
CURRENT_DIR = Path(os.path.abspath(Path(__file__).parent))

# Phone-agent Configuration
PHONE_AGENT_REPO_URL = 'https://gitcode.com/zai-org/Open-AutoGLM.git'
PHONE_AGENT_DIR = 'Open-AutoGLM'

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


def install_project_dependencies(pip_executable: Path) -> None:
    """Install project dependencies from pyproject.toml."""
    print('\n[2/3] Installing dependencies from pyproject.toml...')
    print(f'Using pip executable: {pip_executable}')

    try:
        execute_command(
            [str(pip_executable), 'install', '-e', '.'],
            working_dir=CURRENT_DIR,
            error_message='Failed to install project dependencies from pyproject.toml',
        )
        print('Successfully installed project dependencies')
    except Exception as e:
        print(f'Error installing project dependencies: {str(e)}')
        raise


def install_phone_agent(pip_executable: Path) -> None:
    """Install phone-agent library from git repository."""
    print('\n[3/3] Installing phone-agent library...')

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

            # Apply diff file after clone
            diff_file_path = CURRENT_DIR.parent / 'third-party' / 'Open-AutoGLM-swipe.diff'
            if diff_file_path.exists():
                print(f'Applying diff file: {diff_file_path.name}...')
                try:
                    execute_command(
                        ['git', 'apply', str(diff_file_path)],
                        working_dir=phone_agent_path,
                        error_message='Failed to apply diff file',
                    )
                    print(f'Successfully applied diff file: {diff_file_path.name}')
                except Exception as e:
                    print(f'Error applying diff file: {str(e)}')
                    raise
            else:
                print(f'Warning: Diff file not found: {diff_file_path}')
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
    install_project_dependencies(pip_executable)
    install_phone_agent(pip_executable)
    display_activation_instructions()


if __name__ == '__main__':
    main()
