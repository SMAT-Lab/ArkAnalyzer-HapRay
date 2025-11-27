#!/usr/bin/env python3
"""
统一的Python环境设置脚本
支持增量安装：即使.venv已存在，也会检查并安装缺失的依赖
"""

import platform
import subprocess
import sys
from pathlib import Path

# Version requirements
MIN_PYTHON_VERSION = (3, 9)
MAX_PYTHON_VERSION = (3, 12)

# Configuration
VENV_NAME = '.venv'
REQUIREMENTS_FILE = 'requirements.txt'


def check_python_version():
    """Check if the current Python version meets the requirements."""
    current_version = sys.version_info[:2]
    if not (MIN_PYTHON_VERSION <= current_version <= MAX_PYTHON_VERSION):
        print(
            f'Error: Python version must be between {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} '
            f'and {MAX_PYTHON_VERSION[0]}.{MAX_PYTHON_VERSION[1]}'
        )
        print(f'Current Python version: {current_version[0]}.{current_version[1]}')
        sys.exit(1)


def execute_command(command: list, error_message: str = '') -> None:
    """Execute a shell command with error handling."""
    try:
        result = subprocess.run(
            command,
            check=True,
            shell=platform.system() == 'Windows',
            text=True,
            capture_output=True
        )
        if result.stdout:
            print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f'Error: {error_message}')
        print(f'Command: {" ".join(command)}')
        if e.stdout:
            print(f'Output: {e.stdout}')
        if e.stderr:
            print(f'Error output: {e.stderr}')
        sys.exit(1)


def get_virtualenv_paths() -> tuple:
    """Get paths to virtual environment executables."""
    if platform.system() == 'Windows':
        python_path = Path(VENV_NAME) / 'Scripts' / 'python.exe'
        pip_path = Path(VENV_NAME) / 'Scripts' / 'pip.exe'
    else:
        python_path = Path(VENV_NAME) / 'bin' / 'python'
        pip_path = Path(VENV_NAME) / 'bin' / 'pip'

    if not python_path.exists():
        print(f'Error: Virtual environment Python not found at {python_path}')
        sys.exit(1)

    return python_path, pip_path


def create_virtual_environment():
    """Create a virtual environment if it doesn't exist."""
    venv_path = Path(VENV_NAME)
    if venv_path.exists():
        print(f'Virtual environment already exists at {venv_path}')
        return False  # 返回False表示没有创建新环境
    
    print(f'Creating virtual environment at {venv_path}...')
    execute_command(
        [sys.executable, '-m', 'venv', VENV_NAME],
        error_message='Failed to create virtual environment'
    )
    print(f'Successfully created virtual environment')
    return True  # 返回True表示创建了新环境


def check_package_installed(python_path: Path, package_name: str) -> bool:
    """Check if a package is installed in the virtual environment."""
    try:
        # 将包名中的-替换为_用于import
        import_name = package_name.replace('-', '_').split('[')[0].split('>=')[0].split('==')[0].split('~=')[0]
        cmd = [str(python_path), '-c', f'import {import_name}']
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def get_required_packages() -> list:
    """Get list of required packages from requirements.txt."""
    requirements_path = Path(REQUIREMENTS_FILE)
    if not requirements_path.exists():
        return []
    
    packages = []
    with open(requirements_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 跳过空行和注释
            if line and not line.startswith('#'):
                # 提取包名（去掉版本号）
                pkg_name = line.split('>=')[0].split('==')[0].split('~=')[0].split('[')[0].strip()
                packages.append(pkg_name)
    return packages


def verify_dependencies(python_path: Path) -> tuple:
    """
    Verify if all required dependencies are installed.
    Returns: (all_installed: bool, missing_packages: list)
    """
    required = get_required_packages()
    if not required:
        return True, []
    
    missing = []
    for pkg in required:
        if not check_package_installed(python_path, pkg):
            missing.append(pkg)
    
    return len(missing) == 0, missing


def install_hypium_packages(python_path: Path):
    """Install local hypium packages if available."""
    hypium_dir = Path('hypium-5.0.7.200')

    if not hypium_dir.exists():
        print('Note: hypium-5.0.7.200 directory not found, skipping hypium installation')
        return

    # Check if hypium is already installed
    try:
        subprocess.run(
            [str(python_path), '-c', 'import hypium'],
            check=True,
            capture_output=True
        )
        print('Hypium packages already installed')
        return
    except subprocess.CalledProcessError:
        pass  # hypium not installed, proceed with installation

    # Install hypium packages in order
    packages = [
        'xdevice-5.0.7.200.tar.gz',
        'xdevice-devicetest-5.0.7.200.tar.gz',
        'xdevice-ohos-5.0.7.200.tar.gz',
        'hypium-5.0.7.200.tar.gz',
    ]

    print('Installing hypium packages...')
    for pkg in packages:
        pkg_path = hypium_dir / pkg
        if not pkg_path.exists():
            print(f'  Warning: {pkg} not found, skipping')
            continue

        print(f'  Installing {pkg}...')
        execute_command(
            [str(python_path), '-m', 'pip', 'install', str(pkg_path)],
            error_message=f'Failed to install {pkg}'
        )

    print('Successfully installed hypium packages')


def install_dependencies():
    """Install Python dependencies from requirements.txt or pyproject.toml."""
    python_path, pip_path = get_virtualenv_paths()

    requirements_path = Path(REQUIREMENTS_FILE)
    pyproject_path = Path('pyproject.toml')

    # 先检查依赖是否已完整安装
    all_installed, missing = verify_dependencies(python_path)

    # 升级pip（无论是否需要安装依赖）
    print('Upgrading pip...')
    execute_command(
        [str(python_path), '-m', 'pip', 'install', '--upgrade', 'pip'],
        error_message='Failed to upgrade pip'
    )

    # Install hypium packages first (perf_testing specific)
    install_hypium_packages(python_path)

    if all_installed:
        print('All dependencies are already installed, skipping installation')
        return

    print(f'Missing packages: {", ".join(missing)}')
    print('Installing dependencies...')

    # Try requirements.txt first
    if requirements_path.exists():
        print(f'Installing from {REQUIREMENTS_FILE}...')
        execute_command(
            [str(python_path), '-m', 'pip', 'install', '-r', str(requirements_path)],
            error_message=f'Failed to install from {REQUIREMENTS_FILE}'
        )
        print('Successfully installed dependencies from requirements.txt')
        return

    # Try pyproject.toml as fallback
    if pyproject_path.exists() and _has_project_dependencies(pyproject_path):
        print(f'Installing from pyproject.toml...')
        execute_command(
            [str(python_path), '-m', 'pip', 'install', '-e', '.'],
            error_message='Failed to install from pyproject.toml'
        )
        print('Successfully installed dependencies from pyproject.toml')
        return

    # Fatal error if no dependency file found
    print(f'ERROR: No dependency file found!')
    print(f'   Expected: {REQUIREMENTS_FILE} or pyproject.toml with [project.dependencies]')
    print(f'   Current directory: {Path.cwd()}')
    sys.exit(1)


def _has_project_dependencies(pyproject_path: Path) -> bool:
    """Check if pyproject.toml has [project] section with dependencies."""
    try:
        content = pyproject_path.read_text(encoding='utf-8')
        return '[project]' in content and 'dependencies' in content
    except Exception:
        return False


def main():
    """Main setup function."""
    check_python_version()
    
    print('=' * 60)
    print('Python Environment Setup')
    print('=' * 60)
    print(f'Working directory: {Path.cwd()}')
    print()

    # Create or verify virtual environment
    is_new_env = create_virtual_environment()
    
    # Install or verify dependencies
    install_dependencies()

    print('=' * 60)
    print('Setup completed successfully!')
    print('=' * 60)
    
    # Show activation instructions
    if platform.system() == 'Windows':
        print(f'Activate: {VENV_NAME}\\Scripts\\activate')
    else:
        print(f'Activate: source {VENV_NAME}/bin/activate')
    print()


if __name__ == '__main__':
    main()

