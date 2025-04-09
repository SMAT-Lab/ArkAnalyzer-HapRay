#!/usr/bin/env python
# coding: utf-8

import time
import threading
from devicetest.core.test_case import Step
from hypium import BY
from aw.Utils import convert_data_to_db
import os
from hypium.model import KeyCode


def perform_dynamic_test(driver, config):
    """
    执行测试步骤
    
    Args:
        driver: 测试驱动对象
        config: 测试配置字典
    """
    # 检查 steps 是否为空
    if not config.get('test_settings', {}).get('steps'):
        print("\n[INFO] 未配置测试步骤，将执行自定义UI操作")
        print("[INFO] 请在指定时间内完成手动操作")
        
        # 获取默认采样时长
        duration = config.get('test_settings', {}).get('duration', 30)
        
        # 执行自定义步骤
        perform_custom_step(driver, config, "用户自定义操作", duration)
        return
    
    # 启动应用
    app_package = config['test_settings']['app_package']
    driver.start_app(package_name=app_package)
    driver.wait(2)  # 等待应用启动
    
    # 获取应用 PID
    pid_cmd = f"pidof {app_package}"
    pid = driver.shell(pid_cmd).strip()
    
    # 定义步骤1的动作函数：与丁真的聊天操作
    def chat_with_dingzhen():
        # 点击type为{Text}并且text为{联系人}的控件
        driver.touch(BY.type('Text').text('联系人'))
        driver.wait(1)
        
        # 点击type为{Text}并且text为{丁真}的控件
        driver.touch(BY.type('Text').text('丁真'))
        driver.wait(1)  # 等待时间改为1秒
        
        # 点击输入框
        driver.touch(BY.type('TextInput'))
        driver.wait(1)
        
        # 输入文本
        driver.input_text(BY.type('TextInput'), "你好啊")
        driver.wait(1)
        
        # 按下回车键发送消息
        driver.press_key(KeyCode.ENTER)
        driver.wait(1)

        driver.touch(BY.type('TextInput'))
        driver.wait(1)
        
        # 输入文本
        driver.input_text(BY.type('TextInput'), "最近在忙什么呢？")
        driver.wait(1)
        
        # 按下回车键发送消息
        driver.press_key(KeyCode.ENTER)
        driver.wait(1)


        driver.touch(BY.type('TextInput'))
        driver.wait(1)
        
        # 输入文本
        driver.input_text(BY.type('TextInput'), "那就好，辛苦了")
        driver.wait(1)
        
        # 按下回车键发送消息
        driver.press_key(KeyCode.ENTER)
        driver.wait(1)


        driver.touch(BY.type('TextInput'))
        driver.wait(1)
        
        # 输入文本
        driver.input_text(BY.type('TextInput'), "谢谢关心，我先去忙了")
        driver.wait(1)
        
        # 按下回车键发送消息
        driver.press_key(KeyCode.ENTER)
        driver.wait(1)

        driver.touch(BY.type('TextInput'))
        driver.wait(1)
        
        # 输入文本
        driver.input_text(BY.type('TextInput'), "好的，再见")
        driver.wait(1)

        # 按下回车键发送消息
        driver.press_key(KeyCode.ENTER)
        driver.wait(1)

        
        # 滑动返回
        driver.swipe_to_back()

        driver.wait(1)

        driver.swipe_to_back()

        # 滑动返回
        driver.swipe_to_back()
        driver.wait(1)
    
    # 定义步骤2的动作函数：扫一扫和收付款操作
    def scan_and_payment():
        driver.start_app(package_name=app_package)

        # 点击type为{Text}并且text为{微小信}的控件
        driver.touch(BY.type('Text').text('微小信'))
        driver.wait(0.5)

        # 通过相对位置点击控件
        driver.touch(BY.isAfter(BY.text('微小信')).isBefore(BY.type('List')).type('Image'))
        driver.wait(0.5)
        
        driver.touch(BY.type('Text').text('收付款'))
        driver.wait(0.5)
        
        # 滑动返回
        driver.swipe_to_back()
        driver.wait(1)
        
        driver.swipe_to_back()
        driver.wait(1)

        driver.start_app(package_name=app_package)
        driver.wait(2)  # 等待应用启动
        
        # 点击type为{Text}并且text为{丁真}的控件
        driver.touch(BY.type('Text').text('丁真'))
        driver.wait(0.5)
        # 滑动返回
        driver.swipe_to_back()
        driver.wait(1)

        driver.touch(BY.type('TextInput'))
        driver.wait(1)
        
        # 输入文本
        driver.input_text(BY.type('TextInput'), "我又来了，告辞")
        driver.wait(1)
        
        # 按下回车键发送消息
        driver.press_key(KeyCode.ENTER)
        driver.wait(1)
        # 滑动返回
        driver.swipe_to_back()
        driver.wait(1)

        # 滑动返回
        driver.swipe_to_back()
        driver.wait(1)
    
    # 定义步骤3的动作函数：发现和联系人操作
    def discover_and_contacts():
        driver.start_app(package_name=app_package)

        # 点击type为{Text}并且text为{我的}的控件
        driver.touch(BY.type('Text').text('我的'))
        driver.wait(0.5)
        
        # 点击type为{Text}并且text为{发现}的控件
        driver.touch(BY.type('Text').text('发现'))
        driver.wait(0.5)
        
        # 点击type为{Text}并且text为{联系人}的控件
        driver.touch(BY.type('Text').text('联系人'))
        driver.wait(0.5)
        
        # 点击type为{Text}并且text为{微小信}的控件
        driver.touch(BY.type('Text').text('微小信'))
        driver.wait(0.5)
        
        # 点击type为{Text}并且text为{丁真}的控件
        driver.touch(BY.type('Text').text('丁真'))
        driver.wait(0.5)
        
        # 通过相对位置点击控件
        driver.touch(BY.isAfter(BY.key('input')).type('Image'))
        driver.wait(0.5)
        
        # 点击type为{Text}并且text为{位置}的控件
        driver.touch(BY.type('Text').text('位置'))
        driver.wait(2)
        
        # 点击type为{Button}并且text为{确认}的控件
        driver.touch(BY.type('Button').text('确认'))
        driver.wait(0.5)
        
        # 从(1101, 620)滑动至(1049, 2310)
        driver.slide((1101, 620), (1049, 2310))
        driver.wait(0.5)
        
        # 从(981, 429)滑动至(989, 2024)
        driver.slide((981, 429), (989, 2024))
        driver.wait(0.5)
        
        # 从(1073, 1547)滑动至(1272, 1420)
        driver.slide((1073, 1547), (1272, 1420))
        driver.wait(0.5)
    
    # 执行步骤1：与丁真的聊天操作
    execute_step_with_perf(driver, config, pid, 1, chat_with_dingzhen)
    
    # 执行步骤2：扫一扫和收付款操作
    execute_step_with_perf(driver, config, pid, 2, scan_and_payment)
    
    # 执行步骤3：发现和联系人操作
    execute_step_with_perf(driver, config, pid, 3, discover_and_contacts)


def get_hiperf_cmd(pid, output_path, duration):
    """生成 hiperf 命令
    
    Args:
        pid: 进程ID
        output_path: 输出文件路径
        duration: 采集持续时间
        
    Returns:
        str: 完整的 hiperf 命令
    """
    cmd = f"hiperf record -p {pid} -o {output_path} -s dwarf --kernel-callchain -f 1000 -e raw-instruction-retired --clockid monotonic -m 1024 -d {duration}"
    print(f"\n[DEBUG] Hiperf Command: {cmd}\n")  # 添加调试输出
    return cmd


def run_hiperf(driver, cmd):
    """在后台线程中运行 hiperf 命令"""
    driver.shell(cmd)


def save_perf_data(driver, config, step_id):
    """保存性能数据"""
    # 构建本地输出路径
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = config['test_settings']['output_dir']
    scene = config['test_settings']['scene']
    
    # 构建完整的目录结构
    scene_dir = os.path.normpath(os.path.join(project_root, output_dir, scene))
    hiperf_dir = os.path.join(scene_dir, 'hiperf')
    step_dir = os.path.join(hiperf_dir, str(step_id))
    
    # 构建文件路径
    local_output_path = os.path.join(step_dir, config['test_settings']['data_filename'])
    local_output_db_path = os.path.join(step_dir, config['test_settings']['db_filename'])
    
    # 确保所有必要的目录都存在
    os.makedirs(step_dir, exist_ok=True)
    
    # 检查设备上的文件是否存在
    device_file = config['test_settings']['output_path']
    try:
        # 使用 ls 命令检查文件是否存在
        result = driver.shell(f"ls -l {device_file}")
        
        if "No such file" in result:
            # 尝试列出目录内容以进行调试
            dir_path = os.path.dirname(device_file)
            driver.shell(f"ls -l {dir_path}")
            return
            
        # 如果文件存在，尝试拉取
        driver.pull_file(device_file, local_output_path)
        
        # 检查本地文件是否成功拉取
        if not os.path.exists(local_output_path):
            return
            
        # 将 .data 文件转换为 .db 文件
        convert_data_to_db(config['test_settings']['trace_streamer'], local_output_path, local_output_db_path)
        
        # 检查转换后的文件是否存在
        if not os.path.exists(local_output_db_path):
            return
            
    except Exception as e:
        # 尝试获取更多调试信息
        driver.shell("df -h")
        driver.shell("ls -l /data/local/tmp/")

def perform_custom_step(driver, config, step_name, duration):
    """
    执行自定义步骤，让用户手动操作UI，同时收集性能数据
    
    Args:
        driver: 测试驱动对象
        config: 测试配置字典
        step_name: 步骤名称，用于日志记录
        duration: 操作持续时间（秒）
    """
    print(f"\n[INFO] 开始执行自定义步骤: {step_name}")
    print(f"[INFO] 请在 {duration} 秒内完成手动UI操作")
    print("[INFO] 操作完成后，请等待系统自动继续...")
    
    # 启动应用
    app_package = config['test_settings']['app_package']
    driver.start_app(package_name=app_package)
    driver.wait(2)  # 等待应用启动
    
    # 获取应用 PID
    pid_cmd = f"pidof {app_package}"
    pid = driver.shell(pid_cmd).strip()
    
    # 执行 hiperf 采样（异步执行）
    output_path = config['test_settings']['output_path']
    
    # 确保设备上的目标目录存在
    output_dir = os.path.dirname(output_path)
    driver.shell(f"mkdir -p {output_dir}")
    
    # 清理可能存在的旧文件
    driver.shell(f"rm -f {output_path}")
    
    # 创建并启动 hiperf 线程
    hiperf_cmd = get_hiperf_cmd(pid, output_path, duration)
    hiperf_thread = threading.Thread(target=run_hiperf, args=(driver, hiperf_cmd))
    hiperf_thread.start()
    
    # 等待用户完成操作
    time.sleep(duration)
    
    # 等待 hiperf 线程完成
    hiperf_thread.join()
    
    # 保存性能数据 - 将自定义步骤保存为第一步
    save_perf_data(driver, config, 1)
    
    print(f"[INFO] 自定义步骤 {step_name} 执行完成")

def execute_step_with_perf(driver, config, pid, step_id, action_func, duration=5):
    """
    执行一个步骤并收集性能数据
    
    Args:
        driver: 测试驱动对象
        config: 测试配置字典
        pid: 应用进程ID
        step_id: 步骤ID
        action_func: 要执行的动作函数
        duration: 性能数据采集持续时间（秒）
    """
    # 设置当前步骤的输出路径
    config['test_settings']['output_path'] = f"/data/local/tmp/hiperf_step{step_id}.data"
    
    # 确保设备上的目标目录存在
    output_dir = os.path.dirname(config['test_settings']['output_path'])
    driver.shell(f"mkdir -p {output_dir}")
    
    # 清理可能存在的旧文件
    driver.shell(f"rm -f {config['test_settings']['output_path']}")
    
    # 创建并启动 hiperf 线程
    hiperf_cmd = get_hiperf_cmd(pid, config['test_settings']['output_path'], duration)
    hiperf_thread = threading.Thread(target=run_hiperf, args=(driver, hiperf_cmd))
    hiperf_thread.start()
    
    # 执行动作
    action_func()
    
    # 等待 hiperf 线程完成
    hiperf_thread.join()
    
    # 保存性能数据
    save_perf_data(driver, config, step_id)


def perform_alipay_test(driver, config):
    """
    执行支付宝特定的测试步骤
    
    Args:
        driver: 测试驱动对象
        config: 测试配置字典
    """
    # 获取应用 PID
    app_package = config['test_settings']['app_package']
    pid_cmd = f"pidof {app_package}"
    pid = driver.shell(pid_cmd).strip()
    
    # 定义步骤1的动作函数：启动支付宝
    def start_alipay():
        # 启动应用
        driver.start_app(package_name=app_package)
        driver.wait(2)  # 等待应用启动
    
    # 定义步骤2的动作函数：上滑三次
    def slide_up_three_times():
        for _ in range(3):
            driver.slide((981, 2024), (981, 429))  # 从下往上滑
            driver.wait(1)
    
    # 定义步骤3的动作函数：下滑三次
    def slide_down_three_times():
        for _ in range(3):
            driver.slide((981, 429), (981, 2024))  # 从上往下滑
            driver.wait(1)
    
    # 定义步骤4的动作函数：点击"更多"文本
    def click_more():
        driver.touch(BY.type('Text').text('更多'))
        driver.wait(2)  # 等待两秒
    
    # 定义步骤5的动作函数：上滑两次
    def slide_up_two_times():
        for _ in range(2):
            driver.slide((981, 2024), (981, 429))  # 从下往上滑
            driver.wait(1)
    
    # 定义步骤6的动作函数：下滑两次
    def slide_down_two_times():
        for _ in range(2):
            driver.slide((981, 429), (981, 2024))  # 从上往下滑
            driver.wait(1)
    
    # 定义步骤7的动作函数：返回上一个页面
    def go_back():
        driver.swipe_to_back()
        driver.wait(1)
    
    # 定义步骤8的动作函数：点击"蚂蚁森林"文本
    def click_ant_forest():
        driver.touch(BY.type('Text').text('蚂蚁森林'))
        driver.wait(10)  # 等待10秒
    
    # 定义步骤9的动作函数：返回上一个页面
    def go_back_again():
        driver.swipe_to_back()
        driver.wait(1)
    
    # 定义步骤10的动作函数：返回桌面
    def go_back_to_desktop():
        driver.swipe_to_back()
        driver.wait(1)
    
    # 执行步骤1：启动支付宝
    execute_step_with_perf(driver, config, pid, 1, start_alipay)
    
    # 执行步骤2：上滑三次
    execute_step_with_perf(driver, config, pid, 2, slide_up_three_times)
    
    # 执行步骤3：下滑三次
    execute_step_with_perf(driver, config, pid, 3, slide_down_three_times)
    
    # 执行步骤4：点击"更多"文本
    execute_step_with_perf(driver, config, pid, 4, click_more)
    
    # 执行步骤5：上滑两次
    execute_step_with_perf(driver, config, pid, 5, slide_up_two_times)
    
    # 执行步骤6：下滑两次
    execute_step_with_perf(driver, config, pid, 6, slide_down_two_times)
    
    # 执行步骤7：返回上一个页面
    execute_step_with_perf(driver, config, pid, 7, go_back)
    
    # 执行步骤8：点击"蚂蚁森林"文本
    execute_step_with_perf(driver, config, pid, 8, click_ant_forest)
    
    # 执行步骤9：返回上一个页面
    execute_step_with_perf(driver, config, pid, 9, go_back_again)
    
    # 执行步骤10：返回桌面
    execute_step_with_perf(driver, config, pid, 10, go_back_to_desktop)



