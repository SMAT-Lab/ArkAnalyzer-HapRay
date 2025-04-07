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
    # 执行UI操作
    perform_step_1(driver, config)
    perform_step_2(driver, config)
    perform_step_3(driver, config)

def get_hiperf_cmd(pid, output_path, duration):
    """生成 hiperf 命令
    
    Args:
        pid: 进程ID
        output_path: 输出文件路径
        duration: 采集持续时间
        
    Returns:
        str: 完整的 hiperf 命令
    """
    cmd = f"hiperf record -p {pid} -o {output_path} -s dwarf --kernel-callchain --clockid monotonic -m 1024 -d {duration}"
    print(f"\n[DEBUG] Hiperf Command: {cmd}\n")  # 添加调试输出
    return cmd

def run_hiperf(driver, cmd):
    """在后台线程中运行 hiperf 命令"""
    driver.shell(cmd)


def perform_step_1(driver, config):
    """执行与丁真的聊天操作"""
    # 启动应用
    app_package = config['test_settings']['app_package']
    driver.start_app(package_name=app_package)
    driver.wait(2)  # 等待应用启动
    
    # 设置当前步骤的输出路径
    config['test_settings']['output_path'] = "/data/local/tmp/hiperf_step1.data"
    
    # 获取应用 PID
    pid_cmd = f"pidof {app_package}"
    pid = driver.shell(pid_cmd).strip()

    # 执行 hiperf 采样（异步执行）
    output_path = config['test_settings']['output_path']
    duration = config['test_settings']['duration']
    
    # 确保设备上的目标目录存在
    output_dir = os.path.dirname(output_path)
    driver.shell(f"mkdir -p {output_dir}")
    
    # 清理可能存在的旧文件
    driver.shell(f"rm -f {output_path}")
    
    # 创建并启动 hiperf 线程
    hiperf_cmd = get_hiperf_cmd(pid, output_path, duration)
    hiperf_thread = threading.Thread(target=run_hiperf, args=(driver, hiperf_cmd))
    hiperf_thread.start()
    
    # 执行UI操作
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
    
    # 等待 hiperf 线程完成
    hiperf_thread.join()
    
    # 保存性能数据
    save_perf_data(driver, config, 1)


def perform_step_2(driver, config):
    """执行扫一扫和收付款操作"""
    # 启动应用
    app_package = config['test_settings']['app_package']
    driver.start_app(package_name=app_package)
    driver.wait(2)  # 等待应用启动
    
    # 设置当前步骤的输出路径
    config['test_settings']['output_path'] = "/data/local/tmp/hiperf_step2.data"
    
    # 获取应用 PID
    pid_cmd = f"pidof {app_package}"
    pid = driver.shell(pid_cmd).strip()

    # 执行 hiperf 采样（异步执行）
    output_path = config['test_settings']['output_path']
    duration = config['test_settings']['duration']
    
    # 确保设备上的目标目录存在
    output_dir = os.path.dirname(output_path)
    driver.shell(f"mkdir -p {output_dir}")
    
    # 清理可能存在的旧文件
    driver.shell(f"rm -f {output_path}")
    
    # 创建并启动 hiperf 线程
    hiperf_cmd = get_hiperf_cmd(pid, output_path, duration)
    hiperf_thread = threading.Thread(target=run_hiperf, args=(driver, hiperf_cmd))
    hiperf_thread.start()
    
    # 执行UI操作

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
    
    # 等待 hiperf 线程完成
    hiperf_thread.join()
    
    # 保存性能数据
    save_perf_data(driver, config, 2)



def perform_step_3(driver, config):
    """执行发现和联系人操作"""
    # 启动应用
    app_package = config['test_settings']['app_package']
    driver.start_app(package_name=app_package)
    driver.wait(2)  # 等待应用启动
    
    # 设置当前步骤的输出路径
    config['test_settings']['output_path'] = "/data/local/tmp/hiperf_step3.data"
    
    # 获取应用 PID
    pid_cmd = f"pidof {app_package}"
    pid = driver.shell(pid_cmd).strip()

    # 执行 hiperf 采样（异步执行）
    output_path = config['test_settings']['output_path']
    duration = config['test_settings']['duration']
    
    # 确保设备上的目标目录存在
    output_dir = os.path.dirname(output_path)
    driver.shell(f"mkdir -p {output_dir}")
    
    # 清理可能存在的旧文件
    driver.shell(f"rm -f {output_path}")
    
    # 创建并启动 hiperf 线程
    hiperf_cmd = get_hiperf_cmd(pid, output_path, duration)
    hiperf_thread = threading.Thread(target=run_hiperf, args=(driver, hiperf_cmd))
    hiperf_thread.start()
    
    # 执行UI操作
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
    
    # 等待 hiperf 线程完成
    hiperf_thread.join()
    
    # 保存性能数据
    save_perf_data(driver, config, 3)

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



