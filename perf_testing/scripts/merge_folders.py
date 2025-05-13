import os
import json
import shutil
import argparse
from hapray.core.PerfTestCase import Log
from typing import List, Dict, Any, Optional


def merge_folders(source_folders, target_folder, overwrite=False, dry_run=False):
    """
    将多个源文件夹中的内容递归合并到目标文件夹

    参数:
        source_folders (list): 源文件夹路径列表
        target_folder (str): 目标文件夹路径
        overwrite (bool): 是否覆盖已存在的文件
        dry_run (bool): 是否只进行模拟操作，不实际移动文件
    """
    # 创建目标文件夹（如果不存在）
    if not dry_run:
        os.makedirs(target_folder, exist_ok=True)

    # 遍历每个源文件夹
    for source in source_folders:
        if not os.path.exists(source):
            print(f"警告: 源文件夹 '{source}' 不存在，跳过")
            continue

        # 获取源文件夹的基本名称，用于日志
        source_basename = os.path.basename(os.path.normpath(source))

        # 递归遍历源文件夹中的所有内容
        for root, dirs, files in os.walk(source):
            # 计算相对路径，用于构建目标路径
            relative_path = os.path.relpath(root, source)
            target_subfolder = os.path.join(target_folder, relative_path)

            # 创建目标子文件夹（如果不存在）
            if not os.path.exists(target_subfolder):
                print(f"创建文件夹: {os.path.relpath(target_subfolder, target_folder)}")
                if not dry_run:
                    os.makedirs(target_subfolder, exist_ok=True)

            # 处理文件
            for file in files:
                source_file_path = os.path.join(root, file)
                target_file_path = os.path.join(target_subfolder, file)

                # 检查目标文件是否已存在
                if os.path.exists(target_file_path):
                    # 文件已存在，检查是否需要覆盖
                    if overwrite:
                        print(f"覆盖文件: {os.path.relpath(target_file_path, target_folder)}")
                        if not dry_run:
                            shutil.copy2(source_file_path, target_file_path)
                    else:
                        print(f"跳过已存在的文件: {os.path.relpath(target_file_path, target_folder)}")
                else:
                    # 文件不存在，直接复制
                    print(
                        f"复制文件: {os.path.relpath(source_file_path, source)} -> {os.path.relpath(target_file_path, target_folder)}")
                    if not dry_run:
                        shutil.copy2(source_file_path, target_file_path)


def read_json_arrays_from_dir(
        directory: str,
        filename_pattern: str = "rounds_info.json",
        encoding: str = "utf-8"
) -> List[Dict[str, Any]]:
    """
    读取指定目录下所有匹配的 JSON 文件并解析其中的 JSON 数组

    参数:
        directory: 目标目录路径
        filename_pattern: 文件名模式，默认为 "xxx.json"
        encoding: 文件编码，默认为 "utf-8"

    返回:
        包含所有 JSON 对象的列表
    """
    all_objects = []

    # 检查目录是否存在
    if not os.path.exists(directory):
        raise FileNotFoundError(f"目录不存在: {directory}")

    # 遍历目录中的所有文件
    for filename in os.listdir(directory):
        # 检查文件是否匹配模式且为文件类型
        if filename.endswith(filename_pattern) and os.path.isfile(os.path.join(directory, filename)):
            file_path = os.path.join(directory, filename)

            try:
                # 读取文件内容
                with open(file_path, "r", encoding=encoding) as f:
                    # 解析 JSON 数组
                    data = json.load(f)

                    # 验证是否为数组类型
                    if isinstance(data, list):
                        all_objects.extend(data)
                        print(f"成功读取 {len(data)} 个对象 from {filename}")
                    else:
                        print(f"警告: 文件 {filename} 不包含 JSON 数组，跳过")

            except json.JSONDecodeError as e:
                print(f"错误: 无法解析文件 {filename}: {e}")
            except Exception as e:
                print(f"错误: 读取文件 {filename} 时发生意外错误: {e}")

    return all_objects


def main():
    parser = argparse.ArgumentParser(description='将多个文件夹中的内容合并到一个目标文件夹')
    parser.add_argument('--source', nargs='+', required=True, help='源文件夹路径列表，用空格分隔')
    parser.add_argument('--target', required=True, help='目标文件夹路径')
    parser.add_argument('--overwrite', action='store_true', help='覆盖已存在的文件')
    parser.add_argument('--dry-run', action='store_true', help='模拟执行，不实际移动文件')

    args = parser.parse_args()

    # 检查所有源文件夹是否存在
    for source in args.source:
        if not os.path.exists(source):
            print(f"错误: 源文件夹 '{source}' 不存在")
            return

    # 执行合并操作
    print(f"开始合并文件夹...")
    print(f"源文件夹: {', '.join(args.source)}")
    print(f"目标文件夹: {args.target}")
    print(f"覆盖模式: {args.overwrite}")
    print(f"模拟执行: {args.dry_run}")
    print("-" * 50)

    merge_folders(args.source, args.target, args.overwrite, args.dry_run)

    print("-" * 50)
    print("合并完成!")


if __name__ == "__main__":
    main()
