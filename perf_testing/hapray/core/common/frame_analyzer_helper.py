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

import json
import logging
import os
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np

from hapray.core.common.frame_analyzer import FrameAnalyzer


def test_collect_empty_frame_loads():
    """
    测试收集空帧负载数据
    """
    # 测试目录路径
    root_dir = r'D:\projects\ArkAnalyzer-HapRay\perf_testing\reports'

    try:
        print("\n=== 开始收集空帧负载数据 ===")
        results = collect_empty_frame_analysis_results(root_dir)

        # 构建输出JSON
        output = {
            "total_scenes": len(results),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": results
        }

        # 将结果保存到JSON文件
        output_file = os.path.join(root_dir, "empty_frame_loads_summary.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        # 生成可视化图表
        output_dir = os.path.join(root_dir, "empty_frame_loads_plots")
        visualize_empty_frame_loads(results, output_dir)

        print("\n=== 收集完成 ===")
        print(f"总共收集到 {len(results)} 个场景的数据")
        print(f"结果已保存到: {output_file}")
        print(f"可视化图表已保存到: {output_dir}")

    except Exception as e:
        print(f"\n收集失败: {str(e)}")
        raise


def update_empty_frame_results():
    """
    批量更新空帧分析数据
    递归获取目录中的所有ResourceUsage_PerformanceDynamic_xxx_xxxx格式的目录
    并依次调用update_empty_frame_results函数进行分析
    """
    # 测试目录路径
    root_dir = r'D:\projects\ArkAnalyzer-HapRay\perf_testing\reports\20250611161807'

    try:
        print("\n=== 开始批量更新空帧分析数据 ===")

        # 遍历目录
        for root, dirs, _ in os.walk(root_dir):
            # 过滤出符合条件的目录
            target_dirs = [d for d in dirs if
                           d.startswith('ResourceUsage_PerformanceDynamic_') and 'round' not in d.lower()]

            for target_dir in target_dirs:
                report_dir = os.path.join(root, target_dir)
                print(f"\n处理目录: {report_dir}")

                # 调用update_empty_frame_results函数
                if FrameAnalyzer.update_empty_frame_results(report_dir):
                    print(f"✓ 成功更新 {target_dir} 的空帧分析数据")
                else:
                    print(f"✗ 更新 {target_dir} 的空帧分析数据失败")

        print("\n=== 批量更新完成 ===")

    except Exception as e:
        print(f"\n更新失败: {str(e)}")
        raise


def visualize_empty_frame_loads(results: list, output_dir: str):
    """
    可视化空帧负载数据

    Args:
        results: 空帧负载数据列表
        output_dir: 输出目录
    """
    try:
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        if not results:
            logging.warning("No data to visualize")
            return None

        # 简化场景名称
        def simplify_scene_name(scene_name: str) -> str:
            # 移除 "ResourceUsage_PerformanceDynamic_" 前缀
            if scene_name.startswith("ResourceUsage_PerformanceDynamic_"):
                return scene_name[len("ResourceUsage_PerformanceDynamic_"):]
            return scene_name

        # 1. 按场景分组的空帧负载柱状图
        plt.figure(figsize=(20, 12), dpi=300)  # 增加尺寸和DPI

        # 设置负载阈值（只显示高于此值的数据）
        LOAD_THRESHOLD = 3.0  # 3%的负载阈值

        # 准备数据并过滤
        filtered_data = [(simplify_scene_name(r['scene']), r['step'], r['empty_frame_percentage'])
                         for r in results
                         if r['empty_frame_percentage'] > 0 and r['empty_frame_percentage'] >= LOAD_THRESHOLD]

        # 按负载百分比排序
        filtered_data.sort(key=lambda x: x[2], reverse=True)

        # 如果过滤后没有数据，降低阈值
        if not filtered_data:
            LOAD_THRESHOLD = 0.0
            filtered_data = [(simplify_scene_name(r['scene']), r['step'], r['empty_frame_percentage'])
                             for r in results
                             if r['empty_frame_percentage'] > 0]  # 只保留大于0的数据
            filtered_data.sort(key=lambda x: x[2], reverse=True)

        # 如果还是没有数据，返回
        if not filtered_data:
            logging.warning("No valid data to visualize after filtering")
            return None

        # 修改横坐标标签格式为 "场景_步骤"
        scenes = [f"{scene}_{step}" for scene, step, _ in filtered_data]
        loads = [load for _, _, load in filtered_data]

        # 创建柱状图
        bars = plt.bar(range(len(scenes)), loads)
        plt.title(f'Empty Frame Load by Scene and Step (Threshold: {LOAD_THRESHOLD}%)', fontsize=14)
        plt.xlabel('Scene_Step', fontsize=12)
        plt.ylabel('Empty Frame Load (%)', fontsize=12)
        plt.xticks(range(len(scenes)), scenes, rotation=45, ha='right', fontsize=10)
        plt.yticks(fontsize=10)

        # 添加数值标签
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2., height,
                     f'{height:.1f}%',
                     ha='center', va='bottom',
                     fontsize=10)

        plt.tight_layout()

        # 保存柱状图
        bar_plot_path = os.path.join(output_dir, 'empty_frame_loads_by_scene.png')
        plt.savefig(bar_plot_path, dpi=300, bbox_inches='tight')
        plt.close()

        # 2. 空帧负载箱线图
        plt.figure(figsize=(16, 10), dpi=300)  # 增加尺寸和DPI

        # 按步骤分组数据
        step_data = {}
        for result in results:
            if result['empty_frame_percentage'] > 0:  # 只保留大于0的数据
                step_key = f"{simplify_scene_name(result['scene'])}_{result['step']}"
                if step_key not in step_data:
                    step_data[step_key] = []
                step_data[step_key].append(result['empty_frame_percentage'])

        # 如果没有有效数据，返回
        if not step_data:
            logging.warning("No valid data for boxplot after filtering")
            return None

        # 计算每个步骤的平均负载，并按平均值排序
        step_means = {step: np.mean(loads) for step, loads in step_data.items()}
        sorted_steps = sorted(step_means.keys(), key=lambda x: step_means[x], reverse=True)

        # 创建箱线图
        plt.boxplot([step_data[step] for step in sorted_steps],
                    tick_labels=sorted_steps,
                    vert=True)
        plt.title('Empty Frame Load Distribution by Step', fontsize=14)
        plt.xlabel('Scene_Step', fontsize=12)
        plt.ylabel('Empty Frame Load (%)', fontsize=12)
        plt.xticks(rotation=45, ha='right', fontsize=10)
        plt.yticks(fontsize=10)

        # 添加y=3的参考线
        line = plt.axhline(y=3, color='r', linestyle='--', alpha=0.5)
        # 将线添加到图例中
        plt.legend([line], ['Threshold (3%)'], fontsize=10)

        plt.tight_layout()

        # 保存箱线图
        boxplot_path = os.path.join(output_dir, 'empty_frame_loads_boxplot.png')
        plt.savefig(boxplot_path, dpi=300, bbox_inches='tight')
        plt.close()

        return {
            "bar_plot": bar_plot_path,
            "boxplot": boxplot_path
        }

    except Exception as e:
        logging.error(f"Error generating empty frame load visualizations: {str(e)}")
        return None


def collect_empty_frame_analysis_results(root_dir: str) -> list:
    """
    递归收集目录下所有empty_frame_analysis.json文件中的空帧负载数据

    参数:
    - root_dir: str，要搜索的根目录

    返回:
    - list，包含所有场景的空帧负载数据，格式为：
      [
          {
              "scene": "场景名称",
              "step": "步骤ID",
              "empty_frame_percentage": float,
              "file_path": str
          },
          ...
      ]
    """
    results = []

    # 遍历目录
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file == 'empty_frames_analysis.json':
                file_path = os.path.join(root, file)
                # 跳过包含'step'的路径
                if 'step' in file_path.lower():
                    continue
                try:
                    # 读取JSON文件
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # 获取场景名称（最近的包含ResourceUsage_PerformanceDynamic的目录）
                    current_dir = os.path.dirname(file_path)
                    scene_name = None
                    while current_dir != root_dir:
                        if 'ResourceUsage_PerformanceDynamic' in os.path.basename(current_dir):
                            scene_name = os.path.basename(current_dir)
                            break
                        current_dir = os.path.dirname(current_dir)

                    # 如果没找到，使用默认值
                    if not scene_name:
                        scene_name = f"Unknown_Scene_{os.path.basename(os.path.dirname(file_path))}"
                        logging.warning(f"Using default scene name for {file_path}: {scene_name}")

                    # 遍历每个步骤的数据
                    for step_id, step_data in data.items():
                        if step_data.get("status") == "success":
                            summary = step_data.get("summary", {})
                            load_percentage = summary.get("empty_frame_percentage", 0)

                            results.append({
                                "scene": scene_name,
                                "step": step_id,
                                "empty_frame_percentage": load_percentage,
                                "file_path": file_path
                            })

                except Exception as e:
                    logging.error(f"Error processing {file_path}: {str(e)}")
                    continue

    # 按负载百分比排序
    results.sort(key=lambda x: x["empty_frame_percentage"], reverse=True)
    return results


if __name__ == "__main__":
    update_empty_frame_results()
    # root_dir = r'D:\projects\ArkAnalyzer-HapRay\perf_testing\reports'
    # collect_empty_frame_analysis_results(root_dir)
