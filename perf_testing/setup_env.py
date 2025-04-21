import os
import sys
import subprocess
import platform
from pathlib import Path
import zipfile

# 配置参数（按需修改）
VENV_NAME = ".venv"  # 虚拟环境目录名
GIT_REPO = "https://gitcode.com/sfoolish/HapRayDep.git"  # Git 仓库地址
REPO_DIR = "HapRayDep"  # 本地克隆的仓库目录名
HYPIUM_FILE = "hypium-5.0.7.200.zip"    # 需要解压安装的 ZIP 文件名
HYPIUM_DIR = "hypium-5.0.7.200"     # 解压后的目录名
HYPIUM_PERF_DIR = "hypium_perf-5.0.7.200"


def run_command(cmd, cwd=None, error_msg=""):
    """执行命令并处理错误"""
    try:
        subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            shell=(platform.system() == "Windows"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except subprocess.CalledProcessError as e:
        print(f"错误: {error_msg}")
        print(f"命令行: {e.cmd}")
        print(f"错误输出: {e.stderr}")
        sys.exit(1)

def get_packages(directory):
    packages = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.tar.gz') or f.endswith('.whl')]
    return packages

def create_virtualenv():
    """创建虚拟环境"""
    print(f"\n[1/5] 创建虚拟环境 {VENV_NAME}...")
    if Path(VENV_NAME).exists():
        print(f"警告: {VENV_NAME} 已存在，将复用现有环境")
        return

    run_command(
        [sys.executable, "-m", "venv", VENV_NAME],
        error_msg="创建虚拟环境失败，请检查 Python 环境"
    )

def activate_virtualenv():
    """激活虚拟环境并返回激活后的 Python/pip 路径"""
    if platform.system() == "Windows":
        python_path = Path(VENV_NAME) / "Scripts" / "python.exe"
        pip_path = Path(VENV_NAME) / "Scripts" / "pip.exe"
    else:
        python_path = Path(VENV_NAME) / "bin" / "python"
        pip_path = Path(VENV_NAME) / "bin" / "pip"

    if not python_path.exists():
        print(f"错误: 虚拟环境未正确创建，缺少 {python_path}")
        sys.exit(1)

    return python_path, pip_path

def clone_repository():
    """克隆 Git 仓库"""
    print(f"\n[3/5] 克隆仓库 {GIT_REPO}...")
    if Path(REPO_DIR).exists():
        print(f"警告: 目录 {REPO_DIR} 已存在，跳过克隆")
        return

    run_command(
        ["git", "clone", GIT_REPO, REPO_DIR],
        error_msg="克隆仓库失败，请检查 Git 配置和网络连接"
    )

def unzip_hypium():
    """解压 ZIP 包并安装"""
    print(f"\n[4/5] 处理 ZIP 包 {HYPIUM_FILE}...")
    
    # 构造完整路径
    zip_path = Path(REPO_DIR) / HYPIUM_FILE
    extract_path = Path(REPO_DIR) / HYPIUM_DIR
    
    # 检查 ZIP 文件是否存在
    if not zip_path.exists():
        print(f"错误: ZIP 文件 {zip_path} 不存在")
        sys.exit(1)
    
    # 解压操作（使用 Python 内置库，避免依赖外部工具）
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        print(f"解压完成 -> {extract_path}")
    except Exception as e:
        print(f"解压失败: {str(e)}")
        sys.exit(1)
    
def install_dependencies(pip_path):
    REQUIREMENTS_FILE = "requirements.txt"  # 依赖文件名（或设为 None 跳过安装）
    """安装依赖"""
    if not REQUIREMENTS_FILE:
        print("\n[5/5] 跳过依赖安装(未配置 REQUIREMENTS_FILE)")
        return

    req_path = Path(REQUIREMENTS_FILE)
    if not req_path.exists():
        print(f"\n[5/5] 警告: 依赖文件 {req_path} 不存在，跳过安装")
        return

    print(f"\n[5/5] 安装依赖文件 {REQUIREMENTS_FILE}...")
    run_command(
        [str(pip_path), "install", "-r", str(req_path)],
        error_msg="安装依赖失败，请检查 requirements.txt 文件"
    )

    for pkg in get_packages(Path(REPO_DIR) / HYPIUM_DIR) :
        run_command(
            [str(pip_path), "install",  str(pkg)],
            error_msg="安装依赖失败，请检查 pkg 文件"
        )

    for pkg in get_packages(Path(REPO_DIR) / HYPIUM_PERF_DIR):
        run_command(
            [str(pip_path), "install", str(pkg)],
            error_msg="安装依赖失败，请检查 pkg 文件"
        )


def final_instructions(python_path):
    """输出最终使用说明"""
    print(f"\n 完成！请按以下步骤操作：")

    if platform.system() == "Windows":
        activate_cmd = f"{VENV_NAME}\\Scripts\\activate"
    else:
        activate_cmd = f"source {VENV_NAME}/bin/activate"

    print(f"""
1. 激活虚拟环境:
   {activate_cmd}
    """)

if __name__ == "__main__":
    # 步骤 1: 创建虚拟环境
    create_virtualenv()

    # 步骤 2: 获取虚拟环境路径
    python_path, pip_path = activate_virtualenv()

    # 步骤 3: 克隆仓库
    clone_repository()

    # 步骤 4: unzip hypium
    unzip_hypium()

     # 步骤 5: 安装依赖
    install_dependencies(pip_path)

    # 输出使用说明
    final_instructions(python_path)