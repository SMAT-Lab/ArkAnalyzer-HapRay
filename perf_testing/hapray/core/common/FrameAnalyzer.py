import os
import platform
import subprocess
import json
import sqlite3
from typing import List, Dict, Any
import sys
import codecs
import logging
from hapray.core.common.CommonUtils import CommonUtils
import sqlite3
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
# 同时设置标准输出编码
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

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

        # 获取 perf_testing 目录
        perf_testing_dir = CommonUtils.get_project_root()
        
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
        tool_path = os.path.join(perf_testing_dir, 'hapray-toolbox', 'third-party', 'trace_streamer_binary', tool_name)
        
        # 检查工具是否存在
        if not os.path.exists(tool_path):
            raise FileNotFoundError(f"Trace streamer tool not found at: {tool_path}")

        if system == 'darwin' or system == 'linux':
            os.chmod(tool_path, 0o755)
        
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
            logging.info(f"Converting htrace to db: {cmd}")
            
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
                logging.error(f"Failed to convert htrace to db: {result.stderr}")
                return False

            # 验证输出文件是否存在
            if not os.path.exists(output_db):
                logging.error(f"Output db file not found: {output_db}")
                return False

            logging.info(f"Successfully converted {htrace_file} to {output_db}")
            return True

        except Exception as e:
            logging.error(f"Error converting htrace to db: {str(e)}")
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
                logging.error(f"Error: htrace directory not found at {htrace_dir}")
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
                    logging.warning(f"No htrace file found in {step_path}")
                    continue

                # 设置db文件输出路径（与htrace文件在同一目录）
                db_file = os.path.join(step_path, 'trace.db')
                if not os.path.exists(db_file):
                    # 转换htrace为db
                    logging.info(f"Converting htrace to db for {step_dir}...")
                    if not FrameAnalyzer.convert_htrace_to_db(htrace_file, db_file):
                        logging.error(f"Failed to convert htrace to db for {step_dir}")
                        continue

                # 分析卡顿帧数据
                logging.info(f"Analyzing frame drops for {step_dir}...")
                try:
                    result = analyze_stuttered_frames(db_file)
                    all_results.append(result)
                except Exception as e:
                    logging.error(f"Error analyzing frames for {step_dir}: {str(e)}")
                    continue

            # 保存汇总结果
            if all_results:
                summary_path = os.path.join(htrace_dir, 'frame_analysis_summary.json')
                with open(summary_path, 'w', encoding='utf-8') as f:
                    json.dump(all_results, f, indent=2, ensure_ascii=False)
                logging.info(f"Summary results saved to: {summary_path}")
            else:
                logging.warning("No valid analysis results to summarize")

            return True

        except Exception as e:
            logging.error(f"Error analyzing frame drops: {str(e)}")
            return False

    @staticmethod
    def analyze_empty_frames(trace_db_path: str, perf_db_path: str, app_pids: list) -> dict:
        """
        分析空帧（flag=2, type=0）的负载情况

        参数:
        - trace_db_path: str，trace数据库文件路径
        - perf_db_path: str，perf数据库文件路径
        - app_pids: list，应用进程ID列表

        返回:
        - dict，包含分析结果
        """
        # 连接trace数据库
        trace_conn = sqlite3.connect(trace_db_path)
        perf_conn = sqlite3.connect(perf_db_path)
        
        try:
            # 检查SQLite版本是否支持WITH子句
            cursor = trace_conn.cursor()
            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]
            version_parts = [int(x) for x in version.split('.')]
            if version_parts[0] < 3 or (version_parts[0] == 3 and version_parts[1] < 8):
                raise ValueError(f"SQLite版本 {version} 不支持WITH子句，需要3.8.3或更高版本")

            # 确保所需表存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            required_tables = ['frame_slice', 'process', 'thread', 'callstack']
            if not all(table in tables for table in required_tables):
                raise ValueError(f"数据库中缺少必要的表，需要: {required_tables}")

            # 执行查询获取帧信息
            query = """
            WITH filtered_frames AS (
                -- 首先获取符合条件的帧
                SELECT fs.ts, fs.dur, fs.ipid, fs.itid, fs.callstack_id
                FROM frame_slice fs
                WHERE fs.flag = 2 
                AND fs.type = 0
            ),
            process_filtered AS (
                -- 通过process表过滤出app_pids中的帧
                SELECT ff.*, p.pid, p.name as process_name
                FROM filtered_frames ff
                JOIN process p ON ff.ipid = p.ipid
                WHERE p.pid IN ({})
            ),
            thread_info AS (
                -- 获取线程信息
                SELECT pf.*, t.tid, t.name as thread_name
                FROM process_filtered pf
                JOIN thread t ON pf.itid = t.itid
            )
            -- 最后获取调用栈信息
            SELECT ti.*, cs.name as callstack_name
            FROM thread_info ti
            JOIN callstack cs ON ti.callstack_id = cs.id
            """.format(','.join('?' * len(app_pids)))

            # 获取帧信息
            trace_df = pd.read_sql_query(query, trace_conn, params=app_pids)
            
            if trace_df.empty:
                return {
                    "status": "no_frames",
                    "message": "未找到符合条件的帧"
                }

            # 获取总负载
            total_load_query = "SELECT SUM(event_count) as total_load FROM perf_sample"
            total_load = pd.read_sql_query(total_load_query, perf_conn)['total_load'].iloc[0]
            
            # 获取所有perf样本
            perf_query = "SELECT timestamp_trace, thread_id, event_count FROM perf_sample"
            perf_df = pd.read_sql_query(perf_query, perf_conn)
            
            # 为每个帧创建时间区间
            trace_df['start_time'] = trace_df['ts']
            trace_df['end_time'] = trace_df['ts'] + trace_df['dur']
            
            # 初始化结果列表
            frame_loads = []
            total_empty_frame_load = 0
            
            # 对每个帧进行分析
            for _, frame in trace_df.iterrows():
                # 找出时间戳在帧区间内且线程ID匹配的样本
                mask = (
                    (perf_df['timestamp_trace'] >= frame['start_time']) & 
                    (perf_df['timestamp_trace'] <= frame['end_time']) & 
                    (perf_df['thread_id'] == frame['tid'])
                )
                frame_samples = perf_df[mask]
                
                if not frame_samples.empty:
                    # 计算该帧的总负载
                    frame_load = frame_samples['event_count'].sum()
                    total_empty_frame_load += frame_load
                    
                    frame_loads.append({
                        'ts': frame['ts'],
                        'dur': frame['dur'],
                        'ipid': frame['ipid'],
                        'itid': frame['itid'],
                        'pid': frame['pid'],
                        'tid': frame['tid'],
                        'callstack_id': frame['callstack_id'],
                        'process_name': frame['process_name'],
                        'thread_name': frame['thread_name'],
                        'callstack_name': frame['callstack_name'],
                        'frame_load': frame_load
                    })
            
            # 转换为DataFrame并按负载排序
            result_df = pd.DataFrame(frame_loads)
            if not result_df.empty:
                result_df = result_df.sort_values('frame_load', ascending=False).head(10)
                
                # 计算总空帧负载占比
                total_empty_frame_percentage = (total_empty_frame_load / total_load) * 100
                
                # 构建结果字典
                return {
                    "status": "success",
                    "summary": {
                        "total_load": int(total_load),
                        "total_empty_frame_load": int(total_empty_frame_load),
                        "empty_frame_load_percentage": float(total_empty_frame_percentage),
                        "total_empty_frames": len(trace_df),
                        "empty_frames_with_load": len(frame_loads)
                    },
                    "top_frames": result_df.to_dict('records')
                }
            else:
                return {
                    "status": "no_load",
                    "message": "未找到任何帧负载数据"
                }
            
        finally:
            trace_conn.close()
            perf_conn.close()

    def collect_empty_frame_loads(self, root_dir: str) -> list:
        """
        递归收集目录下所有empty_frame_analysis.json文件中的空帧负载数据

        参数:
        - root_dir: str，要搜索的根目录

        返回:
        - list，包含所有场景的空帧负载数据，格式为：
          [
              {
                  "scene": "场景名称",
                  "load_percentage": float,
                  "file_path": str
              },
              ...
          ]
        """
        results = []
        
        # 遍历目录
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                if file == 'empty_frames_analysis.json':
                    file_path = os.path.join(root, file)
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
                                load_percentage = summary.get("empty_frame_load_percentage", 0)
                                
                                results.append({
                                    "scene": scene_name,
                                    "step": step_id,
                                    "load_percentage": load_percentage,
                                    "file_path": file_path
                                })
                                
                    except Exception as e:
                        logging.error(f"Error processing {file_path}: {str(e)}")
                        continue
        
        # 按负载百分比排序
        results.sort(key=lambda x: x["load_percentage"], reverse=True)
        return results

def parse_frame_slice_db(db_path: str) -> Dict[int, List[Dict[str, Any]]]:
    """
    解析数据库文件，按vsync值分组数据
    结果按vsync值（key）从小到大排序
    只保留flag=0和flag=1的帧（实际渲染的帧）

    Args:
        db_path: 数据库文件路径

    Returns:
        Dict[int, List[Dict[str, Any]]]: 按vsync值分组的帧数据
    """
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有数据，直接过滤type=0和flag in (0,1)的帧
        cursor.execute("""
            WITH RankedFrames AS (
                SELECT *,
                    ROW_NUMBER() OVER (PARTITION BY vsync ORDER BY ts) as rn
                FROM frame_slice 
                WHERE type = 0 AND flag IN (0, 1, 3)
            )
            SELECT * FROM RankedFrames 
            WHERE rn = 1
            ORDER BY vsync, ts
        """)
        
        # 获取列名
        columns = [description[0] for description in cursor.description]
        
        # 获取所有行数据
        rows = cursor.fetchall()
        
        # 按vsync值分组
        vsync_groups: Dict[int, List[Dict[str, Any]]] = {}
        total_frames = 0
        
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
                
            if vsync_value not in vsync_groups:
                vsync_groups[vsync_value] = []
            
            vsync_groups[vsync_value].append(row_dict)
            total_frames += 1
        
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
    获取帧的类型（进程名）

    参数:
        frame: 帧数据字典
        cursor: 数据库游标

    返回:
        str: 'ui'/'render'/'sceneboard'
    """
    ipid = frame.get("ipid")
    if ipid is None:
        return "ui"

    cursor.execute("SELECT name FROM process WHERE ipid = ?", (ipid,))
    result = cursor.fetchone()
    
    if not result:
        return "ui"
        
    process_name = result[0]
    if process_name == "render_service":
        return "render"
    elif process_name == "ohos.sceneboard":
        return "sceneboard"
    return "ui"

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
        try:
            cursor.execute("SELECT value FROM meta WHERE name = 'runtime'")
            runtime_result = cursor.fetchone()
            runtime = runtime_result[0] if runtime_result else None
        except sqlite3.DatabaseError:
            logging.warning("Failed to get runtime from database, setting to None")
            runtime = None
        
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
            "frame_stats": {
                "ui": {
                    "total": 0,
                    "stutter": 0
                },
                "render": {
                    "total": 0,
                    "stutter": 0
                },
                "sceneboard": {
                    "total": 0,
                    "stutter": 0
                }
            },
            "stutter_levels": {
                "level_1": 0,
                "level_2": 0,
                "level_3": 0
            },
            "stutter_details": {
                "ui_stutter": [],
                "render_stutter": [],
                "sceneboard_stutter": []
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
            "frames": set()  # 使用集合来跟踪已处理的帧
        }

        vsync_keys = sorted(data.keys())

        for vsync_key in vsync_keys:
            for frame in data[vsync_key]:
                frame_time = frame["ts"]
                frame_id = f"{vsync_key}_{frame_time}"  # 创建唯一帧标识符

                # 获取帧类型并统计总帧数
                frame_type = get_frame_type(frame, cursor)
                stats["frame_stats"][frame_type]["total"] += 1
                stats["total_frames"] += 1

                # 初始化窗口
                if current_window["start_time"] is None:
                    current_window["start_time"] = frame_time
                    current_window["end_time"] = frame_time + WINDOW_SIZE_MS * NS_TO_MS
                    first_frame_time = frame_time

                # 处理跨多个窗口的情况
                while frame_time >= current_window["end_time"]:
                    # 计算当前窗口的fps
                    window_duration_ms = max((current_window["end_time"] - current_window["start_time"]) / NS_TO_MS, 1)
                    window_fps = (current_window["frame_count"] / window_duration_ms) * 1000
                    if window_fps < LOW_FPS_THRESHOLD:
                        stats["fps_stats"]["low_fps_window_count"] += 1

                    # 计算相对于第一帧的偏移时间（秒）
                    start_offset = (current_window["start_time"] - first_frame_time) / NS_TO_MS / 1000  # 转换为秒
                    end_offset = (current_window["end_time"] - first_frame_time) / NS_TO_MS / 1000  # 转换为秒

                    # 保存当前窗口的fps数据
                    fps_windows.append({
                        "start_time": start_offset,
                        "end_time": end_offset,
                        "start_time_ts": current_window["start_time"],
                        "end_time_ts": current_window["end_time"],
                        "frame_count": current_window["frame_count"],
                        "fps": window_fps
                    })

                    # 新窗口推进 - 使用固定窗口大小
                    current_window["start_time"] = current_window["end_time"]
                    current_window["end_time"] = current_window["start_time"] + WINDOW_SIZE_MS * NS_TO_MS
                    current_window["frame_count"] = 0
                    current_window["frames"] = set()

                # 当前窗口更新 - 只计算时间戳在窗口范围内的帧
                if current_window["start_time"] <= frame_time < current_window["end_time"] and frame_id not in current_window["frames"]:
                    current_window["frame_count"] += 1
                    current_window["frames"].add(frame_id)

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

                        # 统计卡顿帧数
                        stats["frame_stats"][frame_type]["stutter"] += 1

                        # 根据进程类型分类卡顿详情
                        stutter_type = f"{frame_type}_stutter"
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

        # 处理最后一个窗口
        if current_window["frame_count"] > 0:
            window_duration_ms = max((current_window["end_time"] - current_window["start_time"]) / NS_TO_MS, 1)
            window_fps = (current_window["frame_count"] / window_duration_ms) * 1000
            if window_fps < LOW_FPS_THRESHOLD:
                stats["fps_stats"]["low_fps_window_count"] += 1

            # 计算最后一个窗口的偏移时间
            start_offset = (current_window["start_time"] - first_frame_time) / NS_TO_MS / 1000
            end_offset = (current_window["end_time"] - first_frame_time) / NS_TO_MS / 1000

            fps_windows.append({
                "start_time": start_offset,
                "end_time": end_offset,
                "start_time_ts": current_window["start_time"],
                "end_time_ts": current_window["end_time"],
                "frame_count": current_window["frame_count"],
                "fps": window_fps
            })

        # 计算 FPS 概览
        if fps_windows:
            fps_values = [w["fps"] for w in fps_windows]
            stats["fps_stats"]["fps_windows"] = fps_windows
            stats["fps_stats"]["average_fps"] = sum(fps_values) / len(fps_values)
            stats["fps_stats"]["min_fps"] = min(fps_values)
            stats["fps_stats"]["max_fps"] = max(fps_values)
            stats["fps_stats"]["low_fps_window_count"] = stats["fps_stats"]["low_fps_window_count"]
            del stats["fps_stats"]["low_fps_window_count"]
            del stats["fps_stats"]["low_fps_threshold"]

        # 计算各进程的卡顿率
        for process_type in stats["frame_stats"]:
            total = stats["frame_stats"][process_type]["total"]
            stutter = stats["frame_stats"][process_type]["stutter"]
            if total > 0:
                stats["frame_stats"][process_type]["stutter_rate"] = round(stutter / total, 4)
            else:
                stats["frame_stats"][process_type]["stutter_rate"] = 0

        # 计算总卡顿率
        total_stutter = sum(stats["frame_stats"][p]["stutter"] for p in stats["frame_stats"])
        stats["total_stutter_frames"] = total_stutter
        stats["stutter_rate"] = round(total_stutter / stats["total_frames"], 4)

        result = {
            "runtime": runtime,
            "statistics": {
                "total_frames": stats["total_frames"],
                "frame_stats": stats["frame_stats"],
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
        plt.figure(figsize=(15, 8))
        
        # 设置负载阈值（只显示高于此值的数据）
        LOAD_THRESHOLD = 3.0  # 3%的负载阈值
        
        # 准备数据并过滤
        filtered_data = [(simplify_scene_name(r['scene']), r['step'], r['load_percentage']) 
                        for r in results 
                        if r['load_percentage'] >= LOAD_THRESHOLD]
        
        # 按负载百分比排序
        filtered_data.sort(key=lambda x: x[2], reverse=True)
        
        # 如果过滤后没有数据，降低阈值
        if not filtered_data:
            LOAD_THRESHOLD = 0.0
            filtered_data = [(simplify_scene_name(r['scene']), r['step'], r['load_percentage']) 
                           for r in results]
            filtered_data.sort(key=lambda x: x[2], reverse=True)
        
        # 修改横坐标标签格式为 "场景_步骤"
        scenes = [f"{scene}_{step}" for scene, step, _ in filtered_data]
        loads = [load for _, _, load in filtered_data]

        # 创建柱状图
        bars = plt.bar(range(len(scenes)), loads)
        plt.title(f'Empty Frame Load by Scene and Step (Threshold: {LOAD_THRESHOLD}%)')
        plt.xlabel('Scene_Step')
        plt.ylabel('Empty Frame Load (%)')
        plt.xticks(range(len(scenes)), scenes, rotation=45, ha='right')
        
        # 添加数值标签
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}%',
                    ha='center', va='bottom')

        plt.tight_layout()
        
        # 保存柱状图
        bar_plot_path = os.path.join(output_dir, 'empty_frame_loads_by_scene.png')
        plt.savefig(bar_plot_path)
        plt.close()

        # 2. 空帧负载箱线图
        plt.figure(figsize=(12, 6))
        
        # 按步骤分组数据
        step_data = {}
        for result in results:
            step_key = f"{simplify_scene_name(result['scene'])}_{result['step']}"
            if step_key not in step_data:
                step_data[step_key] = []
            step_data[step_key].append(result['load_percentage'])

        # 计算每个步骤的平均负载，并按平均值排序
        step_means = {step: np.mean(loads) for step, loads in step_data.items()}
        sorted_steps = sorted(step_means.keys(), key=lambda x: step_means[x], reverse=True)

        # 创建箱线图
        plt.boxplot([step_data[step] for step in sorted_steps],
                   labels=sorted_steps,
                   vert=True)
        plt.title('Empty Frame Load Distribution by Step')
        plt.xlabel('Scene_Step')
        plt.ylabel('Empty Frame Load (%)')
        plt.xticks(rotation=45, ha='right')
        
        plt.tight_layout()
        
        # 保存箱线图
        boxplot_path = os.path.join(output_dir, 'empty_frame_loads_boxplot.png')
        plt.savefig(boxplot_path)
        plt.close()

        return {
            "bar_plot": bar_plot_path,
            "boxplot": boxplot_path
        }

    except Exception as e:
        logging.error(f"Error generating empty frame load visualizations: {str(e)}")
        return None

def test_collect_empty_frame_loads():
    """
    测试收集空帧负载数据
    """
    # 测试目录路径
    root_dir = r'D:\projects\ArkAnalyzer-HapRay\perf_testing\reports\20250611101243\ResourceUsage_PerformanceDynamic_zhifubao_1000'
    
    try:
        print("\n=== 开始收集空帧负载数据 ===")
        analyzer = FrameAnalyzer()
        results = analyzer.collect_empty_frame_loads(root_dir)
        
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
            
        print(f"\n=== 收集完成 ===")
        print(f"总共收集到 {len(results)} 个场景的数据")
        print(f"结果已保存到: {output_file}")
        print(f"可视化图表已保存到: {output_dir}")
        
    except Exception as e:
        print(f"\n收集失败: {str(e)}")
        raise

def main():
    """测试卡顿帧分析功能的主函数"""
    # 设置要分析的报告目录路径
    path = r'D:\projects\ArkAnalyzer-HapRay\perf_testing\reports\20250611101243\ResourceUsage_PerformanceDynamic_zhifubao_1000'

    # 检查路径是否存在
    if not os.path.exists(path):
        logging.error(f"Error: Directory not found at {path}")
        return

    # 开始分析
    logging.info(f"Starting frame drops analysis for directory: {path}")
    if FrameAnalyzer.analyze_frame_drops(path):
        logging.info("Frame drops analysis completed successfully")
    else:
        logging.error("Frame drops analysis failed")


if __name__ == "__main__":
    # main()
    # test_collect_empty_frame_loads()
    test_collect_empty_frame_loads()