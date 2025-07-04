# coding: utf-8
import time
from typing import Optional

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.perf_testcase import PerfTestCase, Log


class ResourceUsage_PerformanceDynamic_taobao_9999(PerfTestCase):
    # Constants for swipe coordinates
    SWIPE_START_X = 625
    SWIPE_START_Y = 2000
    SWIPE_END_X = 625
    SWIPE_END_Y = 1000
    SWIPE_DURATION = 300

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.taobao.taobao4hmos'
        self._app_name = '淘宝'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 淘宝-首页上下滑5次，间隔2s"
            },
            {
                "name": "step2",
                "description": "2. 淘宝-点击关注按钮并滑动几次"
            },
            {
                "name": "step3",
                "description": "3. 淘宝-点击上新标签并等待"
            }
        ]

    @property
    def steps(self) -> list:
        return self._steps

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def find_component_safely(self, driver, by_type: str, text: str, timeout: int = 5) -> Optional[object]:
        """Safely find a component with retry and logging."""
        try:
            Log.info(f'Looking for component: {text}')
            component = driver.find_component(BY.type(by_type).text(text))
            if component:
                Log.info(f'Found component: {text}')
                return component
            Log.error(f'Component not found: {text}')
            return None
        except Exception as e:
            Log.error(f'Error finding component {text}: {str(e)}')
            return None

    def find_bottom_tab(self, driver, text: str) -> Optional[object]:
        """Find a bottom tab component with multiple strategies."""
        try:
            Log.info(f'Looking for bottom tab: {text}')
            # Try different strategies to find the bottom tab
            strategies = [
                BY.type('Text').text(text),
                BY.type('Button').text(text),
                BY.type('Image').text(text),
                BY.type('Tab').text(text)
            ]

            for strategy in strategies:
                try:
                    component = driver.find_component(strategy)
                    if component:
                        Log.info(f'Found bottom tab: {text} using strategy: {strategy}')
                        return component
                except Exception:
                    continue

            Log.error(f'Bottom tab not found: {text} after trying all strategies')
            return None
        except Exception as e:
            Log.error(f'Error finding bottom tab {text}: {str(e)}')
            return None

    def process(self):
        try:
            self.driver.swipe_to_home()

            Step('启动被测应用')
            self.driver.start_app(self.app_package)
            self.driver.wait(5)

            # Click on '推荐' first
            component = self.find_component_safely(self.driver, 'Text', '推荐')
            if component:
                self.driver.touch(component)
                time.sleep(2)
            else:
                Log.error('Failed to find 推荐 button, continuing with test...')

            def step1():
                Step('1. 淘宝-首页上下滑5次，间隔2s')
                try:
                    for i in range(5):
                        Log.info(f'Performing swipe down {i + 1}/5')
                        self.swipes_up(1, 2, 300)
                    for i in range(5):
                        Log.info(f'Performing swipe up {i + 1}/5')
                        self.swipes_down(1, 2, 300)
                    time.sleep(3)
                except Exception as e:
                    Log.error(f'Error in step1: {str(e)}')

            def step2():
                Step('2. 淘宝-点击关注按钮并滑动几次')
                try:
                    component = self.find_component_safely(self.driver, 'Text', '关注')
                    if component:
                        self.driver.touch(component)
                        time.sleep(2)
                        for i in range(3):
                            Log.info(f'Performing swipe in 关注 page {i + 1}/3')
                            self._swipe(self.SWIPE_START_X, self.SWIPE_START_Y,
                                        self.SWIPE_END_X, self.SWIPE_END_Y,
                                        self.SWIPE_DURATION)
                            time.sleep(2)
                        time.sleep(3)
                    else:
                        Log.error('Failed to find 关注 button')
                except Exception as e:
                    Log.error(f'Error in step2: {str(e)}')

            def step3():
                Step('3. 淘宝-点击上新标签并等待')
                try:
                    # Find and click on '上新'
                    component = self.find_component_safely(self.driver, 'Text', '上新')
                    if component:
                        self.driver.touch(component)
                        time.sleep(5)
                        self.driver.swipe_to_back()
                        time.sleep(2)
                    else:
                        Log.error('Failed to find 上新 button')
                except Exception as e:
                    Log.error(f'Error in step3: {str(e)}')

            self.execute_performance_step(1, step1, 30)
            self.execute_performance_step(2, step2, 10)
            self.execute_performance_step(3, step3, 10)

        except Exception as e:
            Log.error(f'Error in process: {str(e)}')
            raise
