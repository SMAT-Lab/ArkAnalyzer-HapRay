# package.py
# 使用方法:
# 前提:
# - 建议配置虚拟环境, 并且虚拟环境目录为 `perf_testing/.venv`(必须满足!)
# - 配置好python环境, 包括requirement.txt, xdevice-5.0.7.200.tar.gz, xdevice-devicetest-5.0.7.200.tar.gz, xdevice-ohos-5.0.7.200.tar.gz, hypium-5.0.7.200.tar.gz, pyinstaller
# - 在项目根目录下 完成 `npm run build`, 生成perf_testing/hapray-toolbox
# 运行:
# - 在perf_testing目录下运行 `package.py`
# 结果:
# - 会生成 `perf_testing/dist` 目录, 里面包含 `perf_testing/dist/main/`, 运行对应的可执行文件即可
import os
import subprocess
import shutil
import sys
import importlib.util


# import site # 不再直接使用 site.getsitepackages()

def run_command(command_list):
    """运行外部命令并检查错误"""
    try:
        print(f"运行命令: {' '.join(command_list)}")
        process = subprocess.run(command_list, check=True, capture_output=True, text=True)
        print(process.stdout)
        if process.stderr:
            print(f"命令 stderr:\n{process.stderr}", file=sys.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"命令执行失败: {e}", file=sys.stderr)
        print(f"Stdout:\n{e.stdout}", file=sys.stderr)
        print(f"Stderr:\n{e.stderr}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print(f"错误: 命令 '{command_list[0]}' 未找到。请确保它已安装并位于PATH中，或者脚本中调用方式正确。",
              file=sys.stderr)
        return False


def copy_item_with_overwrite(source_item_path, destination_item_path, item_type="item"):
    """复制单个文件或目录，如果目标存在则覆盖"""
    try:
        if os.path.lexists(destination_item_path):
            if os.path.isdir(destination_item_path) and not os.path.islink(destination_item_path):
                shutil.rmtree(destination_item_path)
            else:
                os.remove(destination_item_path)

        if os.path.isdir(source_item_path):
            shutil.copytree(source_item_path, destination_item_path)
        elif os.path.isfile(source_item_path):
            shutil.copy2(source_item_path, destination_item_path)
        else:
            print(f"  警告: 源 {source_item_path} 不是有效的文件或目录。跳过。", file=sys.stderr)
            return False
        print(f"已复制 ({item_type}): {source_item_path} -> {destination_item_path}")
        return True
    except Exception as e:
        print(f"复制 ({item_type}) {source_item_path} 到 {destination_item_path} 失败: {e}", file=sys.stderr)
        return False


def get_python_lib_dir(prefix_path, is_venv=False):
    """手动构造 Lib 目录路径"""
    python_version_dir = f"python{sys.version_info.major}.{sys.version_info.minor}"
    if sys.platform == "win32":
        # Windows venv 和 base Python 都通常直接在 Prefix 下有 'Lib'
        lib_dir = os.path.join(prefix_path, "Lib")
    else:  # Linux/macOS
        # venv 和 base Python 在 Linux/macOS 通常是 prefix/lib/pythonX.Y
        lib_dir = os.path.join(prefix_path, "lib", python_version_dir)
        if not os.path.isdir(lib_dir):
            # 有些系统或 Python 版本可能直接在 prefix/lib 下（不常见于 venv 或标准 python 安装）
            lib_dir_fallback = os.path.join(prefix_path, "lib")
            if os.path.isdir(lib_dir_fallback):
                print(f"  警告: 未找到特定版本的库目录 {lib_dir}, 使用备选 {lib_dir_fallback}", file=sys.stderr)
                lib_dir = lib_dir_fallback
            else:
                print(f"  错误: 无法手动构造库目录 (尝试了 {lib_dir} 和 {lib_dir_fallback})", file=sys.stderr)
                return None

    if not os.path.isdir(lib_dir):
        print(f"  错误: 手动构造的库目录 {lib_dir} 不存在或不是一个目录。", file=sys.stderr)
        return None
    return lib_dir


def main():
    current_dir = os.getcwd()
    print(f"当前工作目录: {current_dir}")

    # --- 动态确定 spec 文件名 ---
    if sys.platform == "win32":
        spec_filename = "package_windows.spec"
    elif sys.platform.startswith("linux"):  # "linux", "linux2", etc.
        spec_filename = "package_linux.spec"
    elif sys.platform == "darwin":  # macOS
        spec_filename = "package_mac.spec"
    else:
        print(f"错误: 不支持的操作系统 '{sys.platform}' 用于确定 spec 文件。", file=sys.stderr)
        sys.exit(1)

    spec_file = os.path.join(current_dir, spec_filename)
    print(f"将使用的 Spec 文件: {spec_file}")
    # --- 结束动态确定 spec 文件名 ---

    dist_dir = os.path.join(current_dir, "dist")
    dist_main_dir = os.path.join(dist_dir, "main")
    dist_internal_dir = os.path.join(dist_main_dir, "_internal")

    # --- 虚拟环境路径检测 (手动构造) ---
    venv_dir = os.path.join(current_dir, ".venv")
    if not os.path.isdir(venv_dir):
        print(f"错误: 虚拟环境目录 {venv_dir} 未找到。", file=sys.stderr)
        sys.exit(1)

    venv_lib_dir = get_python_lib_dir(venv_dir, is_venv=True)
    if not venv_lib_dir:
        print(f"无法确定虚拟环境的 Lib 目录。退出。", file=sys.stderr)
        sys.exit(1)
    venv_site_packages_dir = os.path.join(venv_lib_dir, "site-packages")
    print(f"手动构造的虚拟环境 site-packages 目录: {venv_site_packages_dir}")
    if not os.path.isdir(venv_site_packages_dir):
        print(f"警告: 手动构造的虚拟环境 site-packages 目录 {venv_site_packages_dir} 不存在。", file=sys.stderr)
        # 脚本后续会检查其内容，如果为空会打印警告

    print("\n步骤 1: 检查 PyInstaller 是否已安装...")
    try:
        importlib.import_module("PyInstaller")
        print("PyInstaller 已安装。")
    except ImportError:
        print("PyInstaller 未找到，尝试安装...")
        if not run_command([sys.executable, "-m", "pip", "install", "pyinstaller"]):
            print("PyInstaller 安装失败。请手动安装后重试。", file=sys.stderr)
            sys.exit(1)
        print("PyInstaller 安装成功。")

    print(f"\n步骤 2: 运行 PyInstaller (使用 {spec_file})...")
    if not os.path.exists(spec_file):
        print(f"错误: PyInstaller spec 文件 {spec_file} 未找到!", file=sys.stderr)
        # 提示信息已包含在 spec_filename 确定逻辑中或此处
        sys.exit(1)

    if os.path.exists(dist_dir):
        print(f"删除旧的 PyInstaller 输出目录: {dist_dir}")
        try:
            shutil.rmtree(dist_dir)
        except OSError as e:
            print(f"删除目录 {dist_dir} 失败: {e}", file=sys.stderr)

    if not run_command([sys.executable, "-m", "PyInstaller", spec_file]):
        print("PyInstaller 打包失败。", file=sys.stderr)
        sys.exit(1)
    print("PyInstaller 打包完成。")

    print(f"\n步骤 3: 验证打包输出并确保 _internal 目录存在...")
    main_executable_name = "main" if sys.platform != "win32" else "main.exe"
    main_executable_path = os.path.join(dist_main_dir, main_executable_name)

    if not os.path.exists(main_executable_path):
        print(f"错误: {main_executable_path} 未找到。PyInstaller 可能未成功生成可执行文件。", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(dist_internal_dir):
        print(f"信息: 目录 {dist_internal_dir} 未找到。将创建它。")
        try:
            os.makedirs(dist_internal_dir)
            print(f"已创建目录: {dist_internal_dir}")
        except OSError as e:
            print(f"创建目录 {dist_internal_dir} 失败: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"目录 {dist_internal_dir} 已存在。")
    print("打包输出验证通过。")

    # --- 步骤 4: 复制 .venv site-packages 内容 ---
    print(f"\n步骤 4: 从 {venv_site_packages_dir} 复制内容到 {dist_internal_dir} (覆盖)...")
    if not os.path.exists(venv_site_packages_dir):
        print(f"错误: 源目录 (venv site-packages) {venv_site_packages_dir} 不存在。", file=sys.stderr)
    elif not os.listdir(venv_site_packages_dir):
        print(f"警告: 源目录 {venv_site_packages_dir} 为空。", file=sys.stderr)

    copied_venv_sp_count = 0
    errors_venv_sp_count = 0
    if os.path.exists(venv_site_packages_dir):
        for item_name in os.listdir(venv_site_packages_dir):
            source_item_path = os.path.join(venv_site_packages_dir, item_name)
            destination_item_path = os.path.join(dist_internal_dir, item_name)
            if copy_item_with_overwrite(source_item_path, destination_item_path, "venv site-packages"):
                copied_venv_sp_count += 1
            else:
                errors_venv_sp_count += 1

    if errors_venv_sp_count > 0:
        print(f"复制 (venv site-packages) 过程中发生 {errors_venv_sp_count} 个错误。", file=sys.stderr)
    elif copied_venv_sp_count > 0 or (
            os.path.exists(venv_site_packages_dir) and not os.listdir(venv_site_packages_dir)):
        print(f"成功复制 {copied_venv_sp_count} 个项目 (from venv site-packages)。")

    # --- 步骤 5: 确定基础 Python 环境路径 (手动构造) ---
    print(f"\n步骤 5: 确定基础 Python 环境路径...")
    base_python_prefix = getattr(sys, 'base_prefix', sys.prefix)
    print(f"  基础 Python Prefix: {base_python_prefix}")

    base_python_lib_dir = get_python_lib_dir(base_python_prefix, is_venv=False)
    if not base_python_lib_dir:
        print(f"无法确定基础 Python 的 Lib 目录。退出。", file=sys.stderr)
        sys.exit(1)
    print(f"  手动构造的基础 Python Lib 目录: {base_python_lib_dir}")

    base_python_site_packages_dir = os.path.join(base_python_lib_dir, "site-packages")
    print(f"  手动构造的基础 Python site-packages 目录: {base_python_site_packages_dir}")
    if not os.path.isdir(base_python_site_packages_dir):
        print(f"  警告: 手动构造的基础 Python site-packages 目录 {base_python_site_packages_dir} 不存在。",
              file=sys.stderr)

    # --- 步骤 6: 复制 telnetlib.py 从基础 Python Lib (非必要)---
    print(f"\n步骤 6: 从基础 Python Lib 复制 telnetlib.py...")
    source_telnetlib = os.path.join(base_python_lib_dir, "telnetlib.py")
    dest_telnetlib = os.path.join(dist_internal_dir, "telnetlib.py")
    if os.path.exists(source_telnetlib):
        if not copy_item_with_overwrite(source_telnetlib, dest_telnetlib, "base telnetlib.py"):
            print(f"  复制基础 telnetlib.py 失败。")
    else:
        print(f"  错误: 源文件 {source_telnetlib} 未找到。", file=sys.stderr)

    # --- 步骤 7: 复制 yaml 文件夹从基础 Python site-packages ---
    print(f"\n步骤 7: 从基础 Python site-packages 复制 yaml 文件夹...")
    source_yaml_dir = os.path.join(base_python_site_packages_dir, "yaml")
    dest_yaml_dir = os.path.join(dist_internal_dir, "yaml")
    if os.path.isdir(source_yaml_dir):
        if not copy_item_with_overwrite(source_yaml_dir, dest_yaml_dir, "base yaml dir"):
            print(f"  复制基础 yaml 文件夹失败。")
    else:
        print(f"  错误: 手动构造的源目录 {source_yaml_dir} 未找到或不是一个目录。", file=sys.stderr)
        print(
            f"  提示: 请确保 'yaml' 文件夹确实存在于基础 Python 的 site-packages 目录中，路径为: {base_python_site_packages_dir}")

    print("\n所有操作完成。")


if __name__ == "__main__":
    main()