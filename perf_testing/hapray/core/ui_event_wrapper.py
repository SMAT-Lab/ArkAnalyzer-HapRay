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
import logging
import time
from abc import abstractmethod, ABC

from hypium import UiDriver, BY

from hapray.core.common.coordinate_adapter import CoordinateAdapter
from hapray.core.common.exe_utils import ExeUtils


class UIEventWrapper(ABC):
    def __init__(self, device):
        self.driver = UiDriver(device)
        self.source_screen_width = None
        self.source_screen_height = None

    @property
    @abstractmethod
    def app_package(self) -> str:
        """Package identifier of the application under test"""

    def start_app(self, wait_seconds=5):
        """通用应用启动方法"""
        self.driver.wake_up_display()
        time.sleep(1)
        self.driver.swipe_to_home()
        time.sleep(1)
        self.driver.start_app(self.app_package)
        time.sleep(wait_seconds)

    def stop_app(self):
        """通用应用退出方法"""
        self.driver.swipe_to_home()
        self.driver.stop_app(self.app_package)

    def convert_coordinate(self, x, y) -> tuple:
        return CoordinateAdapter.convert_coordinate(
            self.driver,
            x=x,
            y=y,
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        )

    def touch_by_coordinates(self, x, y, wait_seconds=2) -> bool:
        """通过坐标点击元素"""
        component = self.convert_coordinate(x, y)
        self.driver.touch(component)
        time.sleep(wait_seconds)
        return True

    def touch_by_text(self, text: str, wait_seconds=2) -> bool:
        """通过文本点击元素"""
        component = self.driver.find_component(BY.text(text))
        if component:
            self.driver.touch(component)
            time.sleep(wait_seconds)
            return True
        logging.warning('touch_by_text not found text %s', text)
        return False

    def touch_by_id(self, component_id: str, wait_seconds=2) -> bool:
        component = self.driver.find_component(BY.id(component_id))
        if component:
            self.driver.touch(component)
            time.sleep(wait_seconds)
            return True
        return False

    def touch_by_key(self, key: str, wait_seconds=2) -> bool:
        component = self.driver.find_component(BY.key(key))
        if component:
            self.driver.touch(component)
            time.sleep(wait_seconds)
            return True
        return False

    def swipes_up(self, swip_num: int, sleep: int, timeout=300):
        for _ in range(swip_num):
            self._swipe(630, 1904, 630, 954, timeout)
            time.sleep(sleep)

    def swipes_down(self, swip_num: int, sleep: int, timeout=300):
        for _ in range(swip_num):
            self._swipe(630, 954, 630, 1904, timeout)
            time.sleep(sleep)

    def swipes_left(self, swip_num: int, sleep: int, timeout=300):
        for _ in range(swip_num):
            self._swipe(1008, 1360, 504, 1360, timeout)
            time.sleep(sleep)

    def swipes_right(self, swip_num: int, sleep: int, timeout=300):
        for _ in range(swip_num):
            self._swipe(504, 1360, 1008, 1360, timeout)
            time.sleep(sleep)

    def find_by_text_up(self, text: str, try_times=3) -> bool:
        while try_times >= 0:
            component = self.driver.find_component(BY.text(text))
            if component:
                return True
            self.swipes_up(1, 1)
            try_times -= 1
        return False

    def swipe_to_back(self, sleep: int = 0):
        self.driver.swipe_to_back()
        if sleep > 0:
            time.sleep(sleep)

    def swipe_to_home(self, sleep: int = 0):
        self.driver.swipe_to_home()
        if sleep > 0:
            time.sleep(sleep)

    def _swipe(self, x1, y1, x2, y2, _time=300):
        ExeUtils.execute_command_check_output(
            f'hdc -t {self.driver.device_sn} shell uinput -T -m {str(x1)} {str(y1)} {str(x2)} {str(y2)} {str(_time)} ')
