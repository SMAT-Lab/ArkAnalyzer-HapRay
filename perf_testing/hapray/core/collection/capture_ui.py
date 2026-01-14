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

import os
import re
import zipfile

from hypium import UiDriver
from hypium.uidriver.uitree import UiTree
from xdevice import platform_logger

Log = platform_logger('CaptureUI')


class CaptureUI:
    """UI数据抓取类，负责截屏和dump element树"""

    def __init__(self, driver: UiDriver):
        """
        初始化CaptureUI

        Args:
            driver: 设备驱动对象（需要有shell方法和pull_file方法）
        """
        self.driver: UiDriver = driver
        self.uitree = UiTree(self.driver)

    def capture_ui(self, step_id: int, report_path: str, label_name: str = None):
        """
        抓取UI相关数据，包括截屏和dump element树

        Args:
            step_id: 测试步骤ID
            report_path: 报告保存路径
            label_name: 标记UI
        """
        Log.info(f'开始抓取UI数据 - Step {step_id}')

        # 创建UI数据保存目录
        ui_step_dir = os.path.join(report_path, 'ui', f'step{step_id}')
        os.makedirs(ui_step_dir, exist_ok=True)

        # 如果提供了uitree，则dump inspector JSON
        self.uitree.dump_to_file(os.path.join(ui_step_dir, f'inspector_{label_name}.json'))

        # 1. 截屏
        self._capture_screenshot(ui_step_dir, f'{label_name}_1')

        # 2. dump element树
        self._dump_element_tree(ui_step_dir, f'{label_name}_1')

        # 3. 第2次截屏
        self._capture_screenshot(ui_step_dir, f'{label_name}_2')

        # 4. 第2次dump element树
        self._dump_element_tree(ui_step_dir, f'{label_name}_2')

        Log.info(f'UI数据抓取完成 - Step {step_id}')

    def _capture_screenshot(self, ui_step_dir: str, label_name: str = None):
        """
        执行截屏并保存到本地

        Args:
            ui_step_dir: UI数据保存目录
            label_name: 测试步骤名称
        """
        try:
            Log.info('开始执行截屏...')

            # 执行hdc shell uitest screenCap命令
            result = self.driver.shell('uitest screenCap')
            Log.info(f'截屏命令输出: {result}')

            # 解析截屏文件路径
            if 'ScreenCap saved to' in result:
                # 提取文件路径
                match = re.search(r'ScreenCap saved to (.+\.png)', result)
                if match:
                    remote_screenshot_path = match.group(1)
                    Log.info(f'截屏文件路径: {remote_screenshot_path}')

                    # 生成本地保存路径
                    local_filename = f'screenshot_{label_name}.png' if label_name else 'screenshot.png'
                    local_screenshot_path = os.path.join(ui_step_dir, local_filename)

                    # 使用hdc file recv保存到本地
                    # 检查driver是否有pull_file方法（hypium driver）
                    if hasattr(self.driver, 'pull_file'):
                        self.driver.pull_file(remote_screenshot_path, local_screenshot_path)
                    else:
                        # 使用hdc命令直接传输
                        recv_cmd = f'hdc file recv {remote_screenshot_path} {local_screenshot_path}'
                        Log.info(f'执行文件传输命令: {recv_cmd}')
                        os.system(recv_cmd)

                    # 验证文件是否成功保存
                    if os.path.exists(local_screenshot_path):
                        Log.info(f'截屏保存成功: {local_screenshot_path}')
                    else:
                        Log.error(f'截屏保存失败: {local_screenshot_path}')
                else:
                    Log.error('无法从截屏命令输出中解析文件路径')
            else:
                Log.error('截屏命令执行失败或输出格式不正确')

        except Exception as e:
            Log.error(f'截屏过程中发生错误: {e}')

    def _dump_element_tree(self, ui_step_dir: str, label_name: str = None):
        """
        执行dump element树操作

        Args:
            ui_step_dir: UI数据保存目录
            label_name: 测试步骤名称
        """
        try:
            Log.info('开始dump element树...')

            # 1. 获取Focus window id
            focus_window_id = self._get_focus_window_id()
            if not focus_window_id:
                Log.error('无法获取Focus window id')
                return

            Log.info(f'获取到Focus window id: {focus_window_id}')

            # 2. 执行hidumper命令获取element树
            self._execute_hidumper_dump(ui_step_dir, label_name, focus_window_id)

        except Exception as e:
            Log.error(f'dump element树过程中发生错误: {e}')

    def _get_focus_window_id(self) -> str:
        """
        从hidumper命令输出中解析Focus window id

        Returns:
            Focus window id字符串，如果解析失败返回None
        """
        try:
            # 执行hidumper命令获取Focus window信息
            result = self.driver.shell("hidumper -s WindowManagerService -a '-a'")
            Log.info(f'hidumper命令输出: {result}')

            # 解析Focus window id
            # 查找 "Focus window: " 后面的数字
            match = re.search(r'Focus window:\s*(\d+)', result)
            if match:
                focus_window_id = match.group(1)
                Log.info(f'解析到Focus window id: {focus_window_id}')
                return focus_window_id
            Log.error('无法从hidumper输出中解析Focus window id')
            return None

        except Exception as e:
            Log.error(f'获取Focus window id时发生错误: {e}')
            return None

    def _execute_hidumper_dump(self, ui_step_dir: str, label_name: str, window_id: str):
        """
        执行hidumper dump命令并保存输出到文件

        Args:
            ui_step_dir: UI数据保存目录
            label_name: 测试步骤名称
            window_id: Focus window id
        """
        try:
            # 生成输出文件名
            dump_filename = f'element_tree_{label_name}.txt' if label_name else 'element_tree.txt'
            local_dump_path = os.path.join(ui_step_dir, dump_filename)

            # 执行hidumper dump命令（增加--zip参数）
            dump_cmd = f"hidumper -s WindowManagerService -a '-w {window_id} -default' --zip"
            Log.info(f'执行hidumper dump命令: {dump_cmd}')

            # 执行命令并获取结果
            result = self.driver.shell(dump_cmd)
            Log.info(f'hidumper命令输出: {result}')

            # 从结果中解析zip文件路径
            # 格式：The result is:/data/log/hidumper/20260112-114308-970.zip
            match = re.search(r'The result is:(.+\.zip)', result)
            if match:
                remote_zip_path = match.group(1).strip()
                Log.info(f'解析到hidumper zip文件路径: {remote_zip_path}')

                # 生成本地保存路径
                dump_filename = f'element_tree_{label_name}.zip' if label_name else 'element_tree.zip'
                local_zip_path = os.path.join(ui_step_dir, dump_filename)

                self.driver.pull_file(remote_zip_path, local_zip_path)
                # 验证文件是否成功保存
                if os.path.exists(local_zip_path):
                    Log.info(f'Element树dump zip文件保存成功: {local_zip_path}')

                    # 从zip文件中提取log.txt并保存到local_dump_path
                    try:
                        with zipfile.ZipFile(local_zip_path, 'r') as zip_ref:
                            # 检查zip文件中是否存在log.txt
                            if 'log.txt' in zip_ref.namelist():
                                # 读取log.txt内容
                                log_content = zip_ref.read('log.txt')
                                # 将内容写入local_dump_path文件
                                with open(local_dump_path, 'wb') as f:
                                    f.write(log_content)
                                Log.info(f'Element树dump log.txt提取成功: {local_dump_path}')
                            else:
                                # 列出zip文件中的文件列表以便调试
                                file_list = zip_ref.namelist()
                                Log.error(f'zip文件中未找到log.txt文件，文件列表: {file_list}')
                    except Exception as e:
                        Log.error(f'从zip文件中提取log.txt失败: {e}')
                else:
                    Log.error(f'Element树dump保存失败: {local_zip_path}')
            else:
                Log.error('无法从hidumper输出中解析zip文件路径')

        except Exception as e:
            Log.error(f'执行hidumper dump时发生错误: {e}')
