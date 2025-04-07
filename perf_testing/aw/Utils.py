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
    执行 hapray-cmd.js 命令生成性能分析报告
    :param scene_dir: 场景目录路径，包含 hiperf_output 目录
    :return: bool 表示是否成功生成报告
    """
    input_dir = os.path.join(scene_dir, 'hiperf_output')
    output_dir = os.path.join(scene_dir, 'report', 'hapray_report.html')
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_dir), exist_ok=True)
    
    # 构建并执行命令
    cmd = [
        'node', 'hapray-cmd.js',
        'hapray', 'dbtools',
        '-i', input_dir,
        '-o', output_dir
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Successfully generated HapRay report at: {output_dir}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to generate HapRay report: {str(e)}")
        return False
