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

# coding: utf-8
import re
from typing import Tuple

from hypium import UiDriver

from hapray.core.common.exe_utils import ExeUtils


class CoordinateAdapter:
    """坐标自适应工具类，用于处理不同设备间的坐标转换"""

    @staticmethod
    def get_device_screen_size(driver: UiDriver, source_width: int, source_height: int) -> Tuple[int, int]:
        """获取当前设备的屏幕尺寸

        Args:
            driver: UiDriver实例
            source_width: 采集坐标时的设备屏幕宽度
            source_height: 采集坐标时的设备屏幕高度

        Returns:
            tuple: (width, height)，如果获取失败则返回source_width和source_height
        """
        try:
            # 使用hidumper命令获取屏幕尺寸
            cmd = f'hdc -t {driver.device_sn} shell hidumper -s RenderService -a screen'
            result = ExeUtils.execute_command_check_output(cmd)

            # 将字节类型转换为字符串
            result_str = result.decode('utf-8') if isinstance(result, bytes) else result

            # 使用正则表达式匹配屏幕尺寸
            match = re.search(r'render size:\s*(\d+)x(\d+)', result_str)
            if match:
                width = int(match.group(1))
                height = int(match.group(2))
                return (width, height)
        except Exception as e:
            print(f"Warning: Failed to get device screen size: {e}")

        # 如果获取失败，返回source_width和source_height
        return (source_width, source_height)

    @staticmethod
    def convert_coordinate(driver: UiDriver, x: int, y: int, source_width: int, source_height: int) -> tuple:
        """根据屏幕尺寸转换坐标

        Args:
            driver: UiDriver实例
            x: 原始x坐标
            y: 原始y坐标
            source_width: 采集坐标时的设备屏幕宽度
            source_height: 采集坐标时的设备屏幕高度

        Returns:
            tuple: 转换后的坐标元组 (new_x, new_y)，可直接用于touch等操作

        Raises:
            ValueError: 当坐标或屏幕尺寸无效时抛出异常
        """
        try:
            # 验证输入参数
            if x < 0 or y < 0 or source_width <= 0 or source_height <= 0:
                raise ValueError(
                    f"Invalid input parameters: x={x}, y={y}, "
                    f"source_width={source_width}, source_height={source_height}")

            # 获取当前设备的屏幕尺寸
            current_width, current_height = CoordinateAdapter.get_device_screen_size(driver, source_width,
                                                                                     source_height)

            # 如果当前设备与采集设备屏幕尺寸相同，直接返回原始坐标
            if current_width == source_width and current_height == source_height:
                return (x, y)

            # 计算坐标转换比例
            x_ratio = current_width / source_width
            y_ratio = current_height / source_height

            # 转换坐标
            new_x = int(x * x_ratio)
            new_y = int(y * y_ratio)

            # 验证转换后的坐标是否在屏幕范围内
            if new_x < 0 or new_x > current_width or new_y < 0 or new_y > current_height:
                raise ValueError(
                    f"Converted coordinates ({new_x}, {new_y}) out of screen bounds ({current_width}x{current_height})")

            return (new_x, new_y)

        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Failed to convert coordinate: {str(e)}") from e
