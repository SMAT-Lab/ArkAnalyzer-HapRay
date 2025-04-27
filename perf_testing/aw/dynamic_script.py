#!/usr/bin/env python
# coding: utf-8

import time
import threading
from hypium import BY
from aw.Utils import convert_data_to_db
import os
from aw.config.config import Config

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


def save_perf_data(driver, report_path, device_file, step_id):
    """保存性能数据"""

    # 构建完整的目录结构
    hiperf_dir = os.path.join(report_path, 'hiperf')
    step_dir = os.path.join(hiperf_dir, str(step_id))

    # 构建文件路径
    local_output_path = os.path.join(step_dir, Config.get('hiperf.data_filename', 'perf.data'))
    local_output_db_path = os.path.join(step_dir, Config.get('hiperf.db_filename', 'perf.db'))

    # 确保所有必要的目录都存在
    os.makedirs(step_dir, exist_ok=True)

    # 检查设备上的文件是否存在
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

        # 检查转换后的文件是否存在
        if not os.path.exists(local_output_db_path):
            return

    except Exception as e:
        # 尝试获取更多调试信息
        driver.shell("df -h")
        driver.shell("ls -l /data/local/tmp/")


def execute_step_with_perf(driver, report_path, pid, step_id, action_func, duration=5):
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
    output_file = f"/data/local/tmp/hiperf_step{step_id}.data"

    # 确保设备上的目标目录存在
    output_dir = os.path.dirname(output_file)
    driver.shell(f"mkdir -p {output_dir}")

    # 清理可能存在的旧文件
    driver.shell(f"rm -f {output_file}")

    # 创建并启动 hiperf 线程
    hiperf_cmd = get_hiperf_cmd(pid, output_file, duration)
    hiperf_thread = threading.Thread(target=run_hiperf, args=(driver, hiperf_cmd))
    hiperf_thread.start()

    # 执行动作
    action_func(driver)

    # 等待 hiperf 线程完成
    hiperf_thread.join()

    # 保存性能数据
    save_perf_data(driver, report_path, output_file, step_id)


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
