import os
import platform
import subprocess
import json
import sqlite3
from typing import List, Dict, Any
import sys
import codecs
from xdevice import platform_logger

# 同时设置标准输出编码
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

Log = platform_logger("FrameAnalyzer")

class FrameAnalyzer:
    """卡顿帧分析器

    用于分析htrace文件中的卡顿帧数据，包括：
    1. 将htrace文件转换为db文件
    2. 分析卡顿帧数据
    3. 生成分析报告
    """

    @staticmethod
    def _get_trace_streamer_path() -> str:
        """获取对应系统的trace_streamer工具路径

        Returns:
            str: trace_streamer工具的完整路径
        """
        # 获取项目根目录
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
        
        # 根据系统类型选择对应的工具
        system = platform.system().lower()
        if system == 'windows':
            tool_name = 'trace_streamer_window.exe'
        elif system == 'darwin':  # macOS
            tool_name = 'trace_streamer_mac'
        elif system == 'linux':
            tool_name = 'trace_streamer_linux'
        else:
            raise OSError(f"Unsupported operating system: {system}")

        # 构建工具完整路径
        tool_path = os.path.join(project_root, 'third-party', 'trace_streamer_binary', tool_name)
        
        # 检查工具是否存在
        if not os.path.exists(tool_path):
            raise FileNotFoundError(f"Trace streamer tool not found at: {tool_path}")
        
        return tool_path

    @staticmethod
    def convert_htrace_to_db(htrace_file: str, output_db: str) -> bool:
        """将htrace文件转换为db文件

        使用 trace_streamer 工具将 .htrace 文件转换为 .db 文件
        命令格式: trace_streamer xxx.htrace -e xxx.db

        Args:
            htrace_file: htrace文件路径
            output_db: 输出db文件路径

        Returns:
            bool: 转换是否成功
        """
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_db)
            os.makedirs(output_dir, exist_ok=True)

            # 获取trace_streamer工具路径
            trace_streamer_path = FrameAnalyzer._get_trace_streamer_path()

            # 构建并执行转换命令
            cmd = f'"{trace_streamer_path}" "{htrace_file}" -e "{output_db}"'
            Log.info(f"Converting htrace to db: {cmd}")
            
            # 使用subprocess执行命令
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )

            # 检查命令执行结果
            if result.returncode != 0:
                Log.error(f"Failed to convert htrace to db: {result.stderr}")
                return False

            # 验证输出文件是否存在
            if not os.path.exists(output_db):
                Log.error(f"Output db file not found: {output_db}")
                return False

            Log.info(f"Successfully converted {htrace_file} to {output_db}")
            return True

        except Exception as e:
            Log.error(f"Error converting htrace to db: {str(e)}")
            return False

    @staticmethod
    def analyze_frame_drops(merge_folder_path: str) -> bool:
        """分析指定目录下的卡顿帧数据

        Args:
            merge_folder_path: 合并后的报告目录路径

        Returns:
            bool: 分析是否成功
        """
        try:
            htrace_dir = os.path.join(merge_folder_path, 'htrace')
            if not os.path.exists(htrace_dir):
                Log.error(f"Error: htrace directory not found at {htrace_dir}")
                return False

            # 用于存储所有步骤的分析结果
            all_results = []

            # 遍历所有步骤目录
            for step_dir in os.listdir(htrace_dir):
                step_path = os.path.join(htrace_dir, step_dir)
                if not os.path.isdir(step_path):
                    continue

                # 查找htrace文件
                htrace_file = os.path.join(step_path, 'trace.htrace')
                if not os.path.exists(htrace_file):
                    Log.warning(f"No htrace file found in {step_path}")
                    continue

                # 设置db文件输出路径（与htrace文件在同一目录）
                db_file = os.path.join(step_path, 'trace.db')
                
                # 转换htrace为db
                Log.info(f"Converting htrace to db for {step_dir}...")
                if not FrameAnalyzer.convert_htrace_to_db(htrace_file, db_file):
                    Log.error(f"Failed to convert htrace to db for {step_dir}")
                    continue

                # 分析卡顿帧数据
                Log.info(f"Analyzing frame drops for {step_dir}...")
                try:
                    result = analyze_stuttered_frames(db_file)
                    all_results.append(result)
                except Exception as e:
                    Log.error(f"Error analyzing frames for {step_dir}: {str(e)}")
                    continue

            # 保存汇总结果
            if all_results:
                summary_path = os.path.join(htrace_dir, 'frame_analysis_summary.json')
                with open(summary_path, 'w', encoding='utf-8') as f:
                    json.dump(all_results, f, indent=2, ensure_ascii=False)
                Log.info(f"Summary results saved to: {summary_path}")
            else:
                Log.warning("No valid analysis results to summarize")

            return True

        except Exception as e:
            Log.error(f"Error analyzing frame drops: {str(e)}")
            return False

def parse_frame_slice_db(db_path: str) -> Dict[int, List[Dict[str, Any]]]:
    """
    解析数据库文件，按vsync值分组数据
    结果按vsync值（key）从小到大排序
    过滤掉flag=2的帧（未绘制的帧）

    Args:
        db_path: 数据库文件路径

    Returns:
        Dict[int, List[Dict[str, Any]]]: 按vsync值分组的帧数据
    """
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有数据
        cursor.execute("SELECT * FROM frame_slice")
        
        # 获取列名
        columns = [description[0] for description in cursor.description]
        
        # 获取所有行数据
        rows = cursor.fetchall()
        
        # 按vsync值分组
        vsync_groups: Dict[int, List[Dict[str, Any]]] = {}
        
        # 遍历所有行，将数据转换为字典并按vsync分组
        for row in rows:
            row_dict = dict(zip(columns, row))
            vsync_value = row_dict['vsync']
            
            # 跳过vsync为None的数据
            if vsync_value is None:
                continue
                
            try:
                # 确保vsync_value是整数
                vsync_value = int(vsync_value)
            except (ValueError, TypeError):
                continue
            
            # 跳过flag=2的帧（未绘制的帧）
            if row_dict.get('flag') == 2:
                continue
                
            if vsync_value not in vsync_groups:
                vsync_groups[vsync_value] = []
            
            vsync_groups[vsync_value].append(row_dict)
        
        # 关闭数据库连接
        conn.close()
        
        # 创建有序字典，按key值排序
        return dict(sorted(vsync_groups.items()))
        
    except sqlite3.Error as e:
        import traceback
        raise Exception(f"数据库操作错误: {str(e)}\n{traceback.format_exc()}")
    except Exception as e:
        import traceback
        raise Exception(f"处理过程中发生错误: {str(e)}\n{traceback.format_exc()}")

def get_frame_type(frame: dict, cursor) -> str:
    """
    判断帧的类型：UI帧 / 渲染帧

    参数:
        frame: 帧数据字典
        cursor: 数据库游标

    返回:
        str: 'UI' 或 'Render'
    """
    ipid = frame.get("ipid")
    if ipid is None:
        return "UI"

    cursor.execute("SELECT name FROM process WHERE ipid = ?", (ipid,))
    result = cursor.fetchone()
    
    if result and result[0] == "render_service":
        return "Render"
    return "UI"

def analyze_stuttered_frames(db_path: str) -> dict:
    """
    分析卡顿帧数据并计算FPS

    Args:
        db_path: 数据库文件路径

    Returns:
        dict: 分析结果数据
    """
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取runtime时间
        cursor.execute("SELECT value FROM meta WHERE name = 'runtime'")
        runtime_result = cursor.fetchone()
        runtime = runtime_result[0] if runtime_result else None
        
        data = parse_frame_slice_db(db_path)

        FRAME_DURATION = 16.67  # 毫秒，60fps基准帧时长
        STUTTER_LEVEL_1_FRAMES = 2  # 1级卡顿阈值：0-2帧
        STUTTER_LEVEL_2_FRAMES = 6  # 2级卡顿阈值：2-6帧
        NS_TO_MS = 1_000_000
        WINDOW_SIZE_MS = 1000  # fps窗口大小：1s
        LOW_FPS_THRESHOLD = 45  # 低FPS阈值

        # 初始化第一帧时间戳
        first_frame_time = None

        stats = {
            "total_frames": 0,
            "ui_stutter_frames": 0,
            "render_stutter_frames": 0,
            "total_stutter_frames": 0,
            "stutter_levels": {
                "level_1": 0,
                "level_2": 0,
                "level_3": 0
            },
            "stutter_details": {
                "ui_stutter": [],
                "render_stutter": []
            },
            "fps_stats": {
                "average_fps": 0,
                "min_fps": 0,
                "max_fps": 0,
                "low_fps_window_count": 0,
                "low_fps_threshold": LOW_FPS_THRESHOLD,
                "fps_windows": []
            }
        }

        fps_windows = []
        current_window = {
            "start_time": None,
            "end_time": None,
            "frame_count": 0,
            "frames": []
        }

        vsync_keys = sorted(data.keys())

        for vsync_key in vsync_keys:
            for frame in data[vsync_key]:
                if frame["type"] != 0:
                    continue

                frame_time = frame["ts"]
                stats["total_frames"] += 1

                # 初始化窗口
                if current_window["start_time"] is None:
                    current_window["start_time"] = frame_time
                    current_window["end_time"] = frame_time + WINDOW_SIZE_MS * NS_TO_MS

                # 处理跨多个窗口的情况
                while frame_time >= current_window["end_time"]:
                    window_duration_ms = max((current_window["end_time"] - current_window["start_time"]) / NS_TO_MS, 1)
                    window_fps = (current_window["frame_count"] / window_duration_ms) * 1000
                    if window_fps < LOW_FPS_THRESHOLD:
                        stats["fps_stats"]["low_fps_window_count"] += 1

                    # 计算相对于第一帧的偏移时间（秒）
                    start_offset = (current_window["start_time"] - first_frame_time) / NS_TO_MS / 1000  # 转换为秒
                    end_offset = (current_window["end_time"] - first_frame_time) / NS_TO_MS / 1000  # 转换为秒

                    fps_windows.append({
                        "start_time": start_offset,
                        "end_time": end_offset,
                        "start_time_ts": current_window["start_time"],
                        "end_time_ts": current_window["end_time"],
                        "frame_count": current_window["frame_count"],
                        "fps": window_fps
                    })

                    # 新窗口推进
                    current_window["start_time"] = current_window["end_time"]
                    current_window["end_time"] += WINDOW_SIZE_MS * NS_TO_MS
                    current_window["frame_count"] = 0
                    current_window["frames"] = []

                # 当前窗口更新
                current_window["frame_count"] += 1
                current_window["frames"].append(frame)

                # 记录第一帧的时间戳
                if first_frame_time is None:
                    first_frame_time = frame_time

                # 卡顿判断
                if frame.get("flag") == 1:  # 表示这一帧比预期帧慢
                    # 在同一个vsync组中找type=1的期待帧
                    expected_frame = next((f for f in data[vsync_key] if f["type"] == 1), None)
                    if expected_frame:
                        # 计算实际帧与预期帧的时长差
                        exceed_time_ns = frame["dur"] - expected_frame["dur"]
                        exceed_time = exceed_time_ns / NS_TO_MS
                        exceed_frames = exceed_time / FRAME_DURATION

                        # 判定等级
                        # flag=3 至少是1级卡顿
                        # 0-2帧：1级卡顿
                        # 2-6帧：2级卡顿
                        # 6帧及以上：3级严重卡顿
                        if frame.get("flag") == 3 or exceed_frames < STUTTER_LEVEL_1_FRAMES:
                            stutter_level = 1
                            level_desc = "轻微卡顿"
                            stats["stutter_levels"]["level_1"] += 1
                        elif exceed_frames < STUTTER_LEVEL_2_FRAMES:
                            stutter_level = 2
                            level_desc = "中度卡顿"
                            stats["stutter_levels"]["level_2"] += 1
                        else:
                            stutter_level = 3
                            level_desc = "严重卡顿"
                            stats["stutter_levels"]["level_3"] += 1

                        # 区分 UI 帧 vs 渲染帧
                        frame_type = get_frame_type(frame, cursor)
                        if frame_type == "Render":
                            stutter_type = "render_stutter"
                            stats["render_stutter_frames"] += 1
                        else:
                            stutter_type = "ui_stutter"
                            stats["ui_stutter_frames"] += 1

                        stats["stutter_details"][stutter_type].append({
                            "vsync": vsync_key,
                            "timestamp": frame["ts"],
                            "actual_duration": frame["dur"],
                            "expected_duration": expected_frame["dur"],
                            "exceed_time": exceed_time,
                            "exceed_frames": exceed_frames,
                            "stutter_level": stutter_level,
                            "level_description": level_desc,
                            "src": frame.get("src"),
                            "dst": frame.get("dst")
                        })

        # 关闭数据库连接
        conn.close()

        # 处理最后一个窗口
        if current_window["frame_count"] > 0:
            actual_end_time = current_window["frames"][-1]["ts"]
            window_duration_ms = (actual_end_time - current_window["start_time"]) / NS_TO_MS

            if window_duration_ms >= WINDOW_SIZE_MS:
                window_fps = (current_window["frame_count"] / window_duration_ms) * 1000
                if window_fps < LOW_FPS_THRESHOLD:
                    stats["fps_stats"]["low_fps_window_count"] += 1

                # 计算最后一个窗口的偏移时间
                start_offset = (current_window["start_time"] - first_frame_time) / NS_TO_MS / 1000
                end_offset = (actual_end_time - first_frame_time) / NS_TO_MS / 1000

                fps_windows.append({
                    "start_time": start_offset,
                    "end_time": end_offset,
                    "start_time_ts": current_window["start_time"],
                    "end_time_ts": actual_end_time,
                    "frame_count": current_window["frame_count"],
                    "fps": window_fps
                })
            else:
                print(f"[跳过短窗口FPS计算] 帧数: {current_window['frame_count']}, "
                      f"窗口时长: {window_duration_ms:.2f}ms，不参与FPS统计。")

        # 计算 FPS 概览
        if fps_windows:
            fps_values = [w["fps"] for w in fps_windows]
            stats["fps_stats"]["fps_windows"] = fps_windows
            stats["fps_stats"]["average_fps"] = sum(fps_values) / len(fps_values)
            stats["fps_stats"]["min_fps"] = min(fps_values)
            stats["fps_stats"]["max_fps"] = max(fps_values)
            stats["fps_stats"][f"low_fps_window_count ({LOW_FPS_THRESHOLD})"] = stats["fps_stats"]["low_fps_window_count"]
            del stats["fps_stats"]["low_fps_window_count"]
            del stats["fps_stats"]["low_fps_threshold"]

        stats["total_stutter_frames"] = stats["ui_stutter_frames"] + stats["render_stutter_frames"]
        stats["stutter_rate"] = round(stats["total_stutter_frames"] / stats["total_frames"] * 100, 2)

        result = {
            "runtime": runtime,
            "statistics": {
                "total_frames": stats["total_frames"],
                "ui_stutter_frames": stats["ui_stutter_frames"],
                "render_stutter_frames": stats["render_stutter_frames"],
                "total_stutter_frames": stats["total_stutter_frames"],
                "stutter_rate": stats["stutter_rate"],
                "stutter_levels": stats["stutter_levels"]
            },
            "stutter_details": stats["stutter_details"],
            "fps_stats": stats["fps_stats"]
        }

        return result

    except Exception as e:
        import traceback
        raise Exception(f"处理过程中发生错误: {str(e)}\n{traceback.format_exc()}")

def main():
    """测试卡顿帧分析功能的主函数"""
    # 设置要分析的报告目录路径
    path = r'D:\projects\ArkAnalyzer-HapRay\perf_testing\reports\20250528154741\ResourceUsage_PerformanceDynamic_jingdong_0020'

    # 检查路径是否存在
    if not os.path.exists(path):
        Log.error(f"Error: Directory not found at {path}")
        return

    # 开始分析
    Log.info(f"Starting frame drops analysis for directory: {path}")
    if FrameAnalyzer.analyze_frame_drops(path):
        Log.info("Frame drops analysis completed successfully")
    else:
        Log.error("Frame drops analysis failed")

if __name__ == "__main__":
    main()