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
    def _get_app_pids(scene_dir: str, step_id: str) -> list:
        """获取应用进程ID列表
        
        Args:
            scene_dir: 场景目录路径
            step_id: 步骤ID，如'step1'或'1'
            
        Returns:
            list: 进程ID列表
        """
        try:
            # 获取hiperf_info.json文件路径
            perf_data_path = os.path.join(scene_dir, 'hiperf', 'hiperf_info.json')
            
            if not os.path.exists(perf_data_path):
                logging.warning(f"No hiperf_info.json found at {perf_data_path}")
                return []

            # 读取JSON文件
            with open(perf_data_path, 'r', encoding='utf-8') as f:
                perf_data = json.load(f)
                
            if not perf_data or not isinstance(perf_data, list) or len(perf_data) == 0:
                logging.warning("Invalid hiperf_info.json format")
                return []

            # 获取第一个item的steps
            steps = perf_data[0].get('steps', [])
            if not steps:
                logging.warning("No steps found in hiperf_info.json")
                return []

            # 处理step_id，去掉'step'前缀
            step_number = int(step_id.replace('step', ''))
            
            # 找到对应step_id的数据
            for step in steps:
                if step.get('step_id') == step_number:
                    # 收集该步骤的所有进程ID
                    pids = set()  # 使用set存储，自动去重
                    for item in step.get('data', []):
                        pid = item.get('pid')
                        if pid:
                            pids.add(pid)
                    return list(pids)  # 转换为list返回

            logging.warning(f"No data found for step {step_id} in hiperf_info.json")
            return []

        except Exception as e:
            logging.error(f"Failed to get app PIDs: {str(e)}")
            return []

    @staticmethod
    def _analyze_perf_callchain(perf_conn, callchain_id: int, callchain_cache: pd.DataFrame = None, files_cache: pd.DataFrame = None) -> list:
        """
        分析perf样本的调用链信息
        
        Args:
            perf_conn: perf数据库连接
            callchain_id: 调用链ID
            callchain_cache: 缓存的callchain数据
            files_cache: 缓存的文件数据
            
        Returns:
            list: 调用链信息列表，每个元素包含symbol和path信息
        """
        try:
            if callchain_cache is not None and files_cache is not None:
                # 从缓存中获取callchain数据
                callchain_records = callchain_cache[callchain_cache['callchain_id'] == callchain_id]
                
                if callchain_records.empty:
                    logging.warning(f"未找到callchain_id={callchain_id}的记录")
                    return []
                
                # 构建调用链信息
                callchain_info = []
                for _, record in callchain_records.iterrows():
                    # 从缓存中获取文件信息
                    file_info = files_cache[(files_cache['file_id'] == record['file_id']) & (files_cache['serial_id'] == record['symbol_id'])]
                    symbol = file_info['symbol'].iloc[0] if not file_info.empty else 'unknown'
                    path = file_info['path'].iloc[0] if not file_info.empty else 'unknown'
                    
                    callchain_info.append({
                        'depth': int(record['depth']),
                        'file_id': int(record['file_id']),
                        'path': path,
                        'symbol_id': int(record['symbol_id']),
                        'symbol': symbol
                    })
                        
                return callchain_info
            else:
                # 使用原始SQL查询
                callchain_sql = f"""
                SELECT 
                    pc.depth,
                    pc.file_id,
                    COALESCE(pf.path, 'unknown') as path,
                    pc.symbol_id,
                    COALESCE(pf.symbol, 'unknown') as symbol
                FROM perf_callchain pc
                LEFT JOIN perf_files pf ON pc.file_id = pf.file_id AND pc.symbol_id = pf.serial_id
                WHERE pc.callchain_id = {callchain_id}
                ORDER BY pc.depth
                """
                
                # 执行SQL查询
                callchain_records = pd.read_sql_query(callchain_sql, perf_conn)
                
                if callchain_records.empty:
                    logging.warning(f"未找到callchain_id={callchain_id}的记录")
                    return []
                
                # 直接使用查询结果构建调用链信息
                callchain_info = []
                for _, record in callchain_records.iterrows():
                    callchain_info.append({
                        'depth': record['depth'],
                        'file_id': record['file_id'],
                        'path': record['path'],
                        'symbol_id': record['symbol_id'],
                        'symbol': record['symbol']
                    })
                        
                return callchain_info
            
        except Exception as e:
            logging.error(f"分析调用链失败: {str(e)}")
            return []

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
                SELECT ff.*, p.pid, p.name as process_name, t.tid, t.name as thread_name, t.is_main_thread
                FROM filtered_frames ff
                JOIN process p ON ff.ipid = p.ipid
                JOIN thread t ON ff.itid = t.itid
                WHERE p.pid IN ({})
            )
            -- 最后获取调用栈信息
            SELECT pf.*, cs.name as callstack_name
            FROM process_filtered pf
            JOIN callstack cs ON pf.callstack_id = cs.id
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
            perf_query = "SELECT callchain_id, timestamp_trace, thread_id, event_count FROM perf_sample"
            perf_df = pd.read_sql_query(perf_query, perf_conn)

            # 提前查询并缓存perf_callchain和perf_files表的数据
            callchain_cache = pd.read_sql_query("""
                SELECT 
                    id,
                    callchain_id,
                    depth,
                    file_id,
                    symbol_id
                FROM perf_callchain
            """, perf_conn)
            
            files_cache = pd.read_sql_query("""
                SELECT 
                    file_id,
                    serial_id,
                    symbol,
                    path
                FROM perf_files
            """, perf_conn)

            # 为每个帧创建时间区间
            trace_df['start_time'] = trace_df['ts']
            trace_df['end_time'] = trace_df['ts'] + trace_df['dur']

            # 初始化结果列表
            frame_loads = []
            empty_frame_load = 0  # 主线程空帧总负载（即空刷主线程负载）
            background_thread_load = 0  # 后台线程空帧总负载
            
            # 对每个帧进行分析
            for _, frame in trace_df.iterrows():
                # 找出时间戳在帧区间内且线程ID匹配的样本
                mask = (
                    (perf_df['timestamp_trace'] >= frame['start_time']) & 
                    (perf_df['timestamp_trace'] <= frame['end_time']) & 
                    (perf_df['thread_id'] == frame['tid'])
                )
                frame_samples = perf_df[mask]
                
                # if len(frame_samples) >= 2:
                #     logging.info(f"发现多样本帧，perf db路径: {perf_db_path}")
                
                if not frame_samples.empty:
                    # 初始化帧负载
                    frame_load = 0
                    
                    # 分析每个样本的调用链
                    sample_callchains = []
                    for _, sample in frame_samples.iterrows():
                        if pd.notna(sample['callchain_id']):
                            try:
                                callchain_info = FrameAnalyzer._analyze_perf_callchain(
                                    perf_conn, 
                                    int(sample['callchain_id']),
                                    callchain_cache,
                                    files_cache
                                )
                                if callchain_info:
                                    # 检查是否是VSyncCallBackListener相关的调用链
                                    is_vsync_chain = False
                                    if len(callchain_info) >= 2:
                                        for i in range(len(callchain_info) - 1):
                                            current_symbol = callchain_info[i]['symbol']
                                            next_symbol = callchain_info[i+1]['symbol']
                                            event_count = sample['event_count']
                                            
                                            # 如果任一symbol为空，跳过检查
                                            if not current_symbol or not next_symbol:
                                                continue
                                                
                                            if ('OHOS::Rosen::VSyncCallBackListener::OnReadable' in current_symbol and
                                                'OHOS::Rosen::VSyncCallBackListener::HandleVsyncCallbacks' in next_symbol and
                                                event_count < 2000000):
                                                is_vsync_chain = True
                                                break
                                        
                                        if not is_vsync_chain:
                                            # 累加非VSync调用链的负载
                                            frame_load += sample['event_count']
                                            try:
                                                sample_load_percentage = (sample['event_count'] / frame_load) * 100
                                                sample_callchains.append({
                                                    'timestamp': int(sample['timestamp_trace']),
                                                    'event_count': int(sample['event_count']),
                                                    'load_percentage': float(sample_load_percentage),
                                                    'callchain': callchain_info
                                                })
                                            except Exception as e:
                                                logging.error(f"处理样本时出错: {str(e)}, sample: {sample.to_dict()}, frame_load: {frame_load}")
                                                continue
                            except Exception as e:
                                logging.error(f"分析调用链时出错: {str(e)}")
                                continue
                    
                    # 更新负载统计
                    if frame['is_main_thread'] == 1:
                        empty_frame_load += frame_load
                    else:
                        background_thread_load += frame_load
                    
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
                        'frame_load': frame_load,
                        'is_main_thread': frame['is_main_thread'],
                        'sample_callchains': sample_callchains  # 添加调用链信息
                    })
            
            # 转换为DataFrame并按负载排序
            result_df = pd.DataFrame(frame_loads)
            if not result_df.empty:
                # 分别获取主线程和后台线程的top5帧
                main_thread_frames = result_df[result_df['is_main_thread'] == 1].sort_values('frame_load', ascending=False).head(5)
                background_thread_frames = result_df[result_df['is_main_thread'] == 0].sort_values('frame_load', ascending=False).head(5)
                
                # 只统计主线程空帧负载和后台线程负载
                empty_frame_percentage = (empty_frame_load / total_load) * 100
                background_thread_percentage = (background_thread_load / total_load) * 100
                
                # 构建结果字典
                return {
                    "status": "success",
                    "summary": {
                        "total_load": int(total_load),
                        "empty_frame_load": int(empty_frame_load),
                        "empty_frame_percentage": float(empty_frame_percentage),
                        "background_thread_load": int(background_thread_load),
                        "background_thread_percentage": float(background_thread_percentage),
                        "total_empty_frames": int(len(trace_df[trace_df['is_main_thread'] == 1])),
                        "empty_frames_with_load": int(len([f for f in frame_loads if f['is_main_thread'] == 1]))
                    },
                    "top_frames": {
                        "main_thread_empty_frames": main_thread_frames.to_dict('records'),
                        "background_thread": background_thread_frames.to_dict('records')
                    }
                }
            else:
                return {
                    "status": "no_load",
                    "message": "未找到任何帧负载数据"
                }

        finally:
            trace_conn.close()
            perf_conn.close()

    @staticmethod
    def update_empty_frame_results(report_dir: str) -> bool:
        """
        更新指定目录下的空帧分析数据

        目录结构要求：
        report_dir/
        ├── htrace/
        │   ├── step1/
        │   │   └── trace.db
        │   └── step2/
        │       └── trace.db
        └── hiperf/
            ├── step1/
            │   └── perf.db
            └── step2/
                └── perf.db

        分析结果将保存在：
        report_dir/
        └── htrace/
            └── empty_frames_analysis.json

        Args:
            report_dir: 报告目录路径，该目录下应包含htrace和hiperf两个子目录

        Returns:
            bool: 更新是否成功
        """
        try:
            # 检查目录是否存在
            if not os.path.exists(report_dir):
                logging.error(f"Error: Directory not found at {report_dir}")
                return False

            # 获取htrace和hiperf目录
            htrace_dir = os.path.join(report_dir, 'htrace')
            hiperf_dir = os.path.join(report_dir, 'hiperf')
            
            if not os.path.exists(htrace_dir) or not os.path.exists(hiperf_dir):
                logging.error(f"Error: Required directories not found at {report_dir}")
                return False

            # 用于存储所有步骤的分析结果
            all_results = {}

            # 遍历所有步骤目录
            for step_dir in os.listdir(htrace_dir):
                step_path = os.path.join(htrace_dir, step_dir)
                if not os.path.isdir(step_path):
                    continue

                # 查找trace.db文件
                trace_db = os.path.join(step_path, 'trace.db')
                if not os.path.exists(trace_db):
                    logging.warning(f"Missing trace.db in {step_path}")
                    continue

                # 查找对应的perf.db文件
                perf_db = os.path.join(hiperf_dir, step_dir, 'perf.db')
                if not os.path.exists(perf_db):
                    logging.warning(f"Missing perf.db in {os.path.join(hiperf_dir, step_dir)}")
                    continue

                # 获取进程ID列表
                app_pids = FrameAnalyzer._get_app_pids(report_dir, step_dir)
                if not app_pids:
                    logging.warning(f"No app PIDs found for step {step_dir}")
                    continue

                # 分析空帧数据
                try:
                    result = FrameAnalyzer.analyze_empty_frames(trace_db, perf_db, app_pids)
                    # 将结果添加到总结果字典中
                    all_results[step_dir] = result
                    logging.info(f"Successfully analyzed empty frames for {step_dir}")
                except Exception as e:
                    logging.error(f"Error analyzing empty frames for {step_dir}: {str(e)}")
                    return False

            # 保存所有步骤的分析结果
            if all_results:
                output_file = os.path.join(htrace_dir, 'empty_frames_analysis.json')
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_results, f, indent=2, ensure_ascii=False)
                print(f"✓ 分析结果已保存到: {output_file}")
            else:
                logging.warning("No valid analysis results to save")

            return True

        except Exception as e:
            logging.error(f"Error updating empty frame analysis: {str(e)}")
            return False

def parse_frame_slice_db(db_path: str) -> Dict[int, List[Dict[str, Any]]]:
    """
    解析数据库文件，按vsync值分组数据
    结果按vsync值（key）从小到大排序
    只保留flag=0和flag=0, 1, 3的帧（实际渲染的帧）

    Args:
        db_path: 数据库文件路径

    Returns:
        Dict[int, List[Dict[str, Any]]]: 按vsync值分组的帧数据
    """
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 直接获取所有数据，不排序
        cursor.execute("SELECT * FROM frame_slice")

        # 获取列名
        columns = [description[0] for description in cursor.description]

        # 按vsync值分组
        vsync_groups: Dict[int, List[Dict[str, Any]]] = {}
        total_frames = 0

        # 遍历所有行，将数据转换为字典并按vsync分组
        for row in cursor.fetchall():
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
                if frame["type"] == 1 or frame["flag"] == 2:
                    continue
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
                if current_window["start_time"] <= frame_time < current_window["end_time"] and frame_id not in \
                        current_window["frames"]:
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

