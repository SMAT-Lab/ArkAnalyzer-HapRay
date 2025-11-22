#!/usr/bin/env python3
"""
共享 Python 运行时后处理脚本
将所有工具的 Python3.framework (macOS) 或 python*.dll (Windows) 共享到统一目录，避免重复
"""

import os
import platform
import shutil
import sys
from pathlib import Path


def share_python_runtime(dist_dir: Path):
    """
    共享 Python 运行时
    
    Args:
        dist_dir: dist 目录路径
    """
    dist_dir = Path(dist_dir).resolve()
    
    if not dist_dir.exists():
        print(f'错误: dist 目录不存在: {dist_dir}')
        return False
    
    # 查找所有工具的 _internal 目录
    tools_dir = dist_dir / 'tools'
    if not tools_dir.exists():
        print(f'警告: tools 目录不存在: {tools_dir}')
        return True  # 如果没有 tools 目录，不需要处理
    
    # 根据平台处理不同的 Python 运行时
    if platform.system() == 'Darwin':  # macOS
        return share_python_framework_macos(dist_dir, tools_dir)
    elif platform.system() == 'Windows':  # Windows
        return share_python_dll_windows(dist_dir, tools_dir)
    else:
        print(f'当前平台 {platform.system()} 不需要共享 Python 运行时')
        return True


def share_python_framework_macos(dist_dir: Path, tools_dir: Path):
    """在 macOS 上共享 Python3.framework"""
    # 共享运行时目录
    shared_runtime_dir = dist_dir / '_shared_python'
    shared_framework = shared_runtime_dir / 'Python3.framework'
    
    # 收集所有包含 Python3.framework 的 _internal 目录
    internal_dirs = []
    for tool_dir in tools_dir.iterdir():
        if not tool_dir.is_dir():
            continue
        internal_dir = tool_dir / '_internal'
        if internal_dir.exists():
            framework = internal_dir / 'Python3.framework'
            if framework.exists():
                internal_dirs.append((tool_dir.name, internal_dir, framework))
    
    if not internal_dirs:
        print('未找到任何包含 Python3.framework 的工具')
        return True
    
    print(f'找到 {len(internal_dirs)} 个工具包含 Python3.framework')
    
    # 创建共享运行时目录
    shared_runtime_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制第一个工具的 Python3.framework 到共享目录
    first_tool_name, first_internal_dir, first_framework = internal_dirs[0]
    print(f'从 {first_tool_name} 复制 Python3.framework 到共享目录...')
    
    if shared_framework.exists():
        print(f'共享目录已存在 Python3.framework，删除旧版本...')
        shutil.rmtree(shared_framework)
    
    shutil.copytree(first_framework, shared_framework)
    print(f'✓ 已复制到 {shared_framework}')
    
    # 处理其他工具：删除 Python3.framework 并创建符号链接
    for tool_name, internal_dir, framework in internal_dirs[1:]:
        print(f'处理 {tool_name}...')
        
        # 删除原有的 Python3.framework
        if framework.exists():
            shutil.rmtree(framework)
            print(f'  ✓ 已删除 {tool_name}/_internal/Python3.framework')
        
        # 创建符号链接
        # 计算相对路径
        relative_path = os.path.relpath(shared_framework, internal_dir)
        try:
            os.symlink(relative_path, framework)
            print(f'  ✓ 已创建符号链接: {tool_name}/_internal/Python3.framework -> {relative_path}')
        except OSError as e:
            print(f'  ✗ 创建符号链接失败: {e}')
            # 如果符号链接失败，尝试复制（作为备选方案）
            print(f'  尝试复制作为备选方案...')
            shutil.copytree(shared_framework, framework)
            print(f'  ✓ 已复制 Python3.framework 到 {tool_name}')
    
    # 处理第一个工具：也创建符号链接以保持一致性
    print(f'处理 {first_tool_name}（创建符号链接以保持一致性）...')
    if first_framework.exists():
        shutil.rmtree(first_framework)
        print(f'  ✓ 已删除 {first_tool_name}/_internal/Python3.framework')
    
    relative_path = os.path.relpath(shared_framework, first_internal_dir)
    try:
        os.symlink(relative_path, first_framework)
        print(f'  ✓ 已创建符号链接: {first_tool_name}/_internal/Python3.framework -> {relative_path}')
    except OSError as e:
        print(f'  ✗ 创建符号链接失败: {e}')
        shutil.copytree(shared_framework, first_framework)
        print(f'  ✓ 已复制 Python3.framework 到 {first_tool_name}')
    
    print(f'\n✓ 完成！所有工具现在共享 Python3.framework')
    print(f'  共享位置: {shared_framework}')
    return True


def share_python_dll_windows(dist_dir: Path, tools_dir: Path):
    """在 Windows 上共享 Python DLL 文件"""
    # 共享运行时目录
    shared_runtime_dir = dist_dir / '_shared_python'
    shared_runtime_dir.mkdir(parents=True, exist_ok=True)
    
    # 收集所有包含 Python DLL 的 _internal 目录
    internal_dirs = []
    python_dlls = set()  # 收集所有 Python DLL 文件名
    
    for tool_dir in tools_dir.iterdir():
        if not tool_dir.is_dir():
            continue
        internal_dir = tool_dir / '_internal'
        if internal_dir.exists():
            # 查找 Python DLL 文件（python*.dll, python*.pyd）
            dll_files = []
            for dll_file in internal_dir.glob('python*.dll'):
                dll_files.append(dll_file)
                python_dlls.add(dll_file.name)
            for pyd_file in internal_dir.glob('python*.pyd'):
                dll_files.append(pyd_file)
                python_dlls.add(pyd_file.name)
            
            if dll_files:
                internal_dirs.append((tool_dir.name, internal_dir, dll_files))
    
    if not internal_dirs:
        print('未找到任何包含 Python DLL 的工具')
        return True
    
    print(f'找到 {len(internal_dirs)} 个工具包含 Python DLL')
    
    # 从第一个工具复制所有 Python DLL 到共享目录
    first_tool_name, first_internal_dir, first_dlls = internal_dirs[0]
    print(f'从 {first_tool_name} 复制 Python DLL 到共享目录...')
    
    for dll_file in first_dlls:
        shared_dll = shared_runtime_dir / dll_file.name
        if shared_dll.exists():
            shared_dll.unlink()
        shutil.copy2(dll_file, shared_dll)
        print(f'  ✓ 已复制: {dll_file.name}')
    
    # 处理其他工具：删除 Python DLL 并创建符号链接（或复制）
    for tool_name, internal_dir, dll_files in internal_dirs[1:]:
        print(f'处理 {tool_name}...')
        for dll_file in dll_files:
            shared_dll = shared_runtime_dir / dll_file.name
            if dll_file.exists():
                dll_file.unlink()
            
            # 计算相对路径
            relative_path = os.path.relpath(shared_dll, internal_dir)
            try:
                # Windows 上尝试创建符号链接
                os.symlink(relative_path, dll_file)
                print(f'  ✓ 已创建符号链接: {dll_file.name}')
            except OSError:
                # 如果符号链接失败，复制文件
                shutil.copy2(shared_dll, dll_file)
                print(f'  ✓ 已复制: {dll_file.name}')
    
    # 处理第一个工具：也创建符号链接以保持一致性
    print(f'处理 {first_tool_name}（创建符号链接以保持一致性）...')
    for dll_file in first_dlls:
        shared_dll = shared_runtime_dir / dll_file.name
        if dll_file.exists():
            dll_file.unlink()
        
        relative_path = os.path.relpath(shared_dll, first_internal_dir)
        try:
            os.symlink(relative_path, dll_file)
            print(f'  ✓ 已创建符号链接: {dll_file.name}')
        except OSError:
            shutil.copy2(shared_dll, dll_file)
            print(f'  ✓ 已复制: {dll_file.name}')
    
    print(f'\n✓ 完成！所有工具现在共享 Python DLL')
    print(f'  共享位置: {shared_runtime_dir}')
    return True


def main():
    """主函数"""
    if len(sys.argv) > 1:
        dist_dir = Path(sys.argv[1])
    else:
        # 默认使用脚本所在目录的父目录的 dist
        script_dir = Path(__file__).parent
        dist_dir = script_dir.parent / 'dist'
    
    print(f'处理 dist 目录: {dist_dir}')
    success = share_python_runtime(dist_dir)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

