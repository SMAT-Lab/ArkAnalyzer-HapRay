import subprocess
import json
import time
import os
from datetime import datetime

from hypium import UiDriver

def get_app_version_code(driver: UiDriver, bundle: str) -> int:
    info = driver.shell('bm dump -n {} |grep versionCode'.format(bundle))
    if 'versionCode' not in info:
        return 0
    token = info.splitlines()[-1]
    code_str = token.replace('"versionCode":', '').replace(',', '').strip()
    return int(code_str)

def get_app_name(driver: UiDriver, bundle: str, config_name: str = None) -> str:
    """
    获取应用名称
    :param driver: UiDriver: UI驱动实例
    :param bundle: str: 应用包名
    :param config_name: str: 配置文件中指定的应用名称
    :return: str: 应用名称
    """
    # 如果配置文件中指定了应用名称，直接使用
    if config_name:
        print(f"Debug - Using configured app name: {config_name}")  # 添加调试输出
        return config_name
    
    # 使用 bm dump 命令获取应用信息
    cmd = f"bm dump -n {bundle}"
    result = driver.shell(cmd)
    print(f"Debug - bm dump result: {result}")  # 添加调试输出
    
    try:
        # 解析 JSON 结果
        # 移除开头的包名和冒号
        json_str = result.split(':', 1)[1].strip()
        data = json.loads(json_str)
        
        if 'applicationInfo' in data and 'label' in data['applicationInfo']:
            label = data['applicationInfo']['label']
            if label:
                print(f"Debug - Found label: {label}")  # 添加调试输出
                return label
    except json.JSONDecodeError as e:
        print(f"Debug - JSON parsing error: {e}")  # 添加调试输出
    
    print(f"Debug - No app name found for {bundle}, using package name")  # 添加调试输出
    return bundle  # 如果无法获取名称，返回包名

def get_app_version(driver: UiDriver, bundle: str) -> str:
    """
    获取应用版本号
    :param driver: UiDriver: UI驱动实例
    :param bundle: str: 应用包名
    :return: str: 应用版本号
    """
    # 使用 bm dump 命令获取版本号
    cmd = f"bm dump -n {bundle}"
    result = driver.shell(cmd)
    print(f"Debug - bm dump result: {result}")  # 添加调试输出
    
    try:
        # 解析 JSON 结果
        # 移除开头的包名和冒号
        json_str = result.split(':', 1)[1].strip()
        data = json.loads(json_str)
        
        if 'applicationInfo' in data and 'versionName' in data['applicationInfo']:
            version = data['applicationInfo']['versionName']
            if version:
                print(f"Debug - Found version: {version}")  # 添加调试输出
                return version
    except json.JSONDecodeError as e:
        print(f"Debug - JSON parsing error: {e}")  # 添加调试输出
    
    print(f"Debug - No version found for {bundle}")  # 添加调试输出
    return "Unknown Version"  # 如果无法获取版本号，返回未知版本

def convert_data_to_db(tool, input, output):
    """
    调用 trace_streamer 工具将 .data 文件转为 .db 文件
    :param tool: trace_streamer 可执行文件路径
    :param input: 输入 .data 文件路径
    :param output: 输出 .db 文件路径
    :return: True 表示转换成功，False 表示失败
    """
    cmd = [tool, input, '-e', output]
    print(cmd)
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def get_test_info(output_dir):
    """
    从指定目录读取testInfo.json文件
    :param output_dir: 输出目录路径
    :return: 测试信息字典，如果文件不存在则返回None
    """
    test_info_path = os.path.join(output_dir, 'testInfo.json')
    if os.path.exists(test_info_path):
        with open(test_info_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def generate_test_info(driver: UiDriver, app_id: str, scene: str, output_dir: str):
    """
    生成测试信息并保存到testInfo.json
    :param driver: UI驱动实例
    :param app_id: 应用包名
    :param scene: 测试场景
    :param output_dir: 输出目录
    :return: 生成的测试信息字典
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 动态获取应用信息
    app_name = get_app_name(driver, app_id)
    app_version = get_app_version(driver, app_id)
    
    # 生成测试信息
    test_info = {
        "app_id": app_id,
        "app_name": app_name,
        "app_version": app_version,
        "scene": scene,
        "timestamp": int(time.time() * 1000),  # 毫秒级时间戳
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 保存到文件
    test_info_path = os.path.join(output_dir, 'testInfo.json')
    with open(test_info_path, 'w', encoding='utf-8') as f:
        json.dump(test_info, f, indent=4, ensure_ascii=False)
    
    return test_info

def save_testInfo(driver: UiDriver, app_id: str, scene: str, output_dir: str, success: bool = True, config: dict = None):
    """
    生成并保存测试信息到testInfo.json
    :param driver: UI驱动实例
    :param app_id: 应用包名
    :param scene: 测试场景
    :param output_dir: 输出目录
    :param success: 测试是否成功
    :param config: 配置字典，包含app_name等配置信息
    :return: 保存的结果字典
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 从配置中获取应用名称，如果没有配置则自动获取
    config_name = config.get('test_settings', {}).get('app_name') if config else None
    app_name = get_app_name(driver, app_id, config_name)
    app_version = get_app_version(driver, app_id)
    
    # 准备结果信息
    result = {
        "app_id": app_id,
        "app_name": app_name,
        "app_version": app_version,
        "scene": scene,
        "timestamp": int(time.time() * 1000)  # 毫秒级时间戳
    }
    
    # 保存到文件
    result_path = os.path.join(output_dir, 'testInfo.json')
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    
    return result

def generate_hapray_report(scene_dir: str) -> bool:
    """
    执行 hapray 命令生成性能分析报告
    :param scene_dir: 场景目录路径，例如 perf_output/wechat002 或完整路径
    :return: bool 表示是否成功生成报告
    """
    # 获取 perf_testing 目录
    perf_testing_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 获取项目根目录（perf_testing 的上一级目录）
    project_root = os.path.dirname(perf_testing_dir)
    
    # 检查是否已经是完整路径
    if os.path.isabs(scene_dir):
        # 如果是绝对路径，直接使用
        full_scene_dir = scene_dir
    else:
        # 否则，添加 perf_testing 目录前缀
        full_scene_dir = os.path.normpath(os.path.join(perf_testing_dir, scene_dir))
    
    # 检查目录是否存在
    if not os.path.exists(full_scene_dir):
        print(f"Error: Scene directory does not exist: {full_scene_dir}")
        return False
    
    # 检查 hiperf 目录是否存在
    hiperf_dir = os.path.join(full_scene_dir, 'hiperf')
    if not os.path.exists(hiperf_dir):
        print(f"Error: hiperf directory does not exist: {hiperf_dir}")
        return False
    
    # 检查 hiperf 目录中是否有文件
    hiperf_files = os.listdir(hiperf_dir)
    if not hiperf_files:
        print(f"Error: hiperf directory is empty: {hiperf_dir}")
        return False
    
    print(f"Found {len(hiperf_files)} files in hiperf directory")
    
    # 构建输出路径 - 直接输出到场景目录的 report 文件夹
    output_dir = os.path.join(full_scene_dir, 'report')
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取 hapray-cmd.js 的绝对路径
    hapray_cmd_path = os.path.abspath(os.path.join(project_root, 'toolbox', 'hapray-cmd.js'))
    
    # 检查 hapray-cmd.js 是否存在
    if not os.path.exists(hapray_cmd_path):
        print(f"Error: hapray-cmd.js not found at {hapray_cmd_path}")
        return False
    
    # 打印调试信息
    print(f"Project root: {project_root}")
    print(f"Scene directory: {full_scene_dir}")
    print(f"Hiperf directory: {hiperf_dir}")
    print(f"Hapray command path: {hapray_cmd_path}")
    print(f"Current working directory: {os.getcwd()}")
    
    # 确保路径使用双反斜杠
    full_scene_dir_escaped = full_scene_dir.replace('\\', '\\\\')
    hapray_cmd_path_escaped = hapray_cmd_path.replace('\\', '\\\\')
    
    # 构建并执行命令 - 使用绝对路径
    cmd = [
        'node', hapray_cmd_path_escaped,
        'hapray', 'dbtools',
        '-i', full_scene_dir_escaped
    ]
    
    # 打印完整命令
    print(f"Executing command: {' '.join(cmd)}")
    
    try:
        # 设置工作目录为项目根目录
        result = subprocess.run(cmd, check=True, cwd=project_root, capture_output=True, text=True)
        print(f"Command output: {result.stdout}")
        if result.stderr:
            print(f"Command stderr: {result.stderr}")
        
        # 检查输出目录中是否有文件
        report_files = os.listdir(output_dir)
        if not report_files:
            print(f"Warning: No files found in report directory: {output_dir}")
            return False
        
        print(f"Found {len(report_files)} files in report directory")
        print(f"Successfully generated HapRay report in: {output_dir}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to generate HapRay report: {str(e)}")
        if e.stdout:
            print(f"Command stdout: {e.stdout}")
        if e.stderr:
            print(f"Command stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        print("Error: Node.js command not found. Please make sure Node.js is installed and in your PATH.")
        return False
