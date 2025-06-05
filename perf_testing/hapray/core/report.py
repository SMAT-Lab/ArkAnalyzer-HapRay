import json
import logging
import os
import subprocess

from hapray.core.common.CommonUtils import CommonUtils
from hapray.core.common.FrameAnalyzer import FrameAnalyzer


class Report:
    def __init__(self):
        pass

    @staticmethod
    def generate_hapray_report(scene_dirs: list[str], scene_dir: str, so_dir: str) -> bool:
        """
        执行 hapray 命令生成性能分析报告
        :param scene_dir: 场景目录路径，例如 perf_output/wechat002 或完整路径
        :return: bool 表示是否成功生成报告
        Log日志和具体case相关，生成报告时已与case无关，导致Log无法落盘，此处使用logging记录日志
        """

        if not scene_dirs:
            logging.error("Error: scene_dirs length is 0!")
            return False

        # 获取 perf_testing 目录
        perf_testing_dir = CommonUtils.get_project_root()

        # 获取项目根目录（perf_testing 的上一级目录）
        project_root = os.path.dirname(perf_testing_dir)

        # 检查是否已经是完整路径
        if os.path.isabs(scene_dir):
            # 如果是绝对路径，直接使用
            full_scene_dir = scene_dir
        else:
            # 否则，添加 perf_testing 目录前缀
            full_scene_dir = os.path.normpath(os.path.join(perf_testing_dir, scene_dir))

        # 获取 hapray-cmd.js 的绝对路径
        hapray_cmd_path = os.path.abspath(os.path.join(perf_testing_dir, 'hapray-toolbox', 'hapray-cmd.js'))

        # 检查 hapray-cmd.js 是否存在
        if not os.path.exists(hapray_cmd_path):
            logging.error(f"Error: hapray-cmd.js not found at {hapray_cmd_path}")
            return False

        # 打印调试信息
        logging.info(f"Project root: {project_root}")
        logging.info(f"Scene directory: {full_scene_dir}")
        logging.info(f"Hapray command path: {hapray_cmd_path}")
        logging.info(f"Current working directory: {os.getcwd()}")

        # 确保路径使用双反斜杠
        full_scene_dir_escaped = full_scene_dir.replace('\\', '\\\\')
        hapray_cmd_path_escaped = hapray_cmd_path.replace('\\', '\\\\')

        # 构建并执行命令 - 使用绝对路径
        cmd = [
            'node', hapray_cmd_path_escaped,
            'hapray', 'dbtools',
            '--choose', 'true',
            '-i', full_scene_dir_escaped
        ]

        # 打印完整命令
        logging.info(f"Executing command: {' '.join(cmd)}")

        # 轮次选择 信息记录在report目录下的summary_info.json中。
        if Report.exe_hapray_cmd(cmd, project_root):
            logging.info("轮次选择成功！信息记录在report目录下的summary_info.json中。")
        else:
            logging.info("轮次选择失败！")
            return False
        # hiperf分析，生成hiperf/hiperf_info.json
        if so_dir == None:
            cmd = [
                'node', hapray_cmd_path_escaped,
                'hapray', 'dbtools',
                '-i', full_scene_dir_escaped
            ]
        else:
            cmd = [
                'node', hapray_cmd_path_escaped,
                'hapray', 'dbtools',
                '-i', full_scene_dir_escaped,
                '-s', so_dir
            ]
        # 打印完整命令
        logging.info(f"Executing command: {' '.join(cmd)}")
        if Report.exe_hapray_cmd(cmd, project_root):
            logging.info("hiperf分析成功！信息记录在hiperf目录下的hiperf_info.json中。")
        else:
            logging.info("hiperf分析失败失败！")
            return False
        # 在所有报告生成完成后进行卡顿帧分析
        logging.info(f"Starting frame drops analysis for {scene_dir}...")
        if FrameAnalyzer.analyze_frame_drops(scene_dir):
            logging.info(f"Successfully analyzed frame drops for {scene_dir}")
        else:
            logging.error(f"Failed to analyze frame drops for {scene_dir}")
        perf_json_path = os.path.join(scene_dir, 'hiperf', 'hiperf_info.json')
        trace_json_path = os.path.join(scene_dir, 'htrace', 'frame_analysis_summary.json')
        html_path = os.path.join(perf_testing_dir, 'hapray-toolbox', 'res', 'report_template.html')
        output_path = os.path.join(scene_dir, 'report', 'hapray_report.html')
        Report.create_html(perf_json_path, trace_json_path, html_path, output_path)
        return True

    @staticmethod
    def exe_hapray_cmd(cmd, project_root):
        try:
            # 设置工作目录为项目根目录，并指定编码为 utf-8
            result = subprocess.run(
                cmd,
                check=True,
                cwd=project_root,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'  # 使用 replace 策略处理无法解码的字符
            )
            logging.info(f"Command output: {result.stdout}")
            if result.stderr:
                logging.error(f"Command stderr: {result.stderr}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to generate HapRay report: {str(e)}")
            if e.stdout:
                logging.error(f"Command stdout: {e.stdout}")
            if e.stderr:
                logging.error(f"Command stderr: {e.stderr}")
            return False
        except FileNotFoundError:
            logging.error(
                "Error: Node.js command not found. Please make sure Node.js is installed and in your PATH.")
            return False

    @staticmethod
    def create_html(perf_json_path: str, trace_json_path: str, html_path: str, output_path: str):
        # 注入perf信息
        Report.replace_html_with_json(perf_json_path, 'JSON_DATA_PLACEHOLDER', html_path, output_path)
        # 注入trace信息
        Report.replace_html_with_json(trace_json_path, 'FRAME_JSON_PLACEHOLDER', output_path, output_path)
        return

    @staticmethod
    def replace_html_with_json(json_path: str, replace_str: str, html_path: str, output_path: str) -> None:
        """
        读取JSON数组文件，用第一个元素替换HTML中的占位符

        Args:
            json_path: JSON文件路径
            html_path: HTML模板文件路径
            output_path: 输出文件路径
        """
        try:
            # 验证输入文件是否存在
            for file_path in [json_path, html_path]:
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"文件不存在: {file_path}")

            # 读取并解析JSON文件
            with open(json_path, 'r', encoding='utf-8') as f:
                try:
                    json_data = json.load(f)
                except json.JSONDecodeError as e:
                    raise ValueError(f"JSON解析错误: {e}")

            # 验证JSON结构
            if not isinstance(json_data, list) or len(json_data) == 0:
                raise ValueError("JSON文件必须包含非空数组")

            # 转换为格式化的JSON字符串（保留中文）
            if replace_str == 'JSON_DATA_PLACEHOLDER':
                first_obj = json.dumps(json_data[0], indent=2, ensure_ascii=False)
            else:
                first_obj = json.dumps(json_data, indent=2, ensure_ascii=False)
            # 读取HTML文件
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            new_html = html_content.replace(replace_str, first_obj)

            # 写入输出文件（自动创建目录）
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(new_html)

            logging.error(f"替换完成，结果已保存至 {output_path}")

        except FileNotFoundError as e:
            logging.error(f"错误: {e}")
        except ValueError as e:
            logging.error(f"错误: {e}")
        except PermissionError:
            logging.error(f"错误: 没有权限访问文件或目录")
        except Exception as e:
            logging.error(f"意外错误: {e}")
