import time
from typing import Optional

from hypium import BY

from hapray.core.perf_testcase import Log, PerfTestCase


class ResourceUsage_PerformanceDynamic_taobao_9999(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.taobao.taobao4hmos'
        self._app_name = '淘宝'

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def find_component_safely(self, by_type: str, text: str) -> Optional[object]:
        """Safely find a component with retry and logging."""
        try:
            Log.info(f'Looking for component: {text}')
            component = self.driver.find_component(BY.type(by_type).text(text))
            if component:
                Log.info(f'Found component: {text}')
                return component
            Log.error(f'Component not found: {text}')
            return None
        except Exception as e:
            Log.error(f'Error finding component {text}: {str(e)}')
            return None

    def process(self):
        try:
            self.driver.swipe_to_home()

            # 启动被测应用
            self.driver.start_app(self.app_package)
            self.driver.wait(5)

            # Click on '推荐' first
            component = self.find_component_safely('Text', '推荐')
            if component:
                self.driver.touch(component)
                time.sleep(2)
            else:
                Log.error('Failed to find 推荐 button, continuing with test...')

            def step1():
                # 淘宝-首页上下滑5次，间隔2s
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
                # 淘宝-点击关注按钮并滑动几次
                try:
                    component = self.find_component_safely('Text', '关注')
                    if component:
                        self.driver.touch(component)
                        time.sleep(2)
                        for i in range(3):
                            Log.info(f'Performing swipe in 关注 page {i + 1}/3')
                            self.swipes_up(1, 2, 300)
                        time.sleep(3)
                    else:
                        Log.error('Failed to find 关注 button')
                except Exception as e:
                    Log.error(f'Error in step2: {str(e)}')

            def step3():
                # 3. 淘宝-点击上新标签并等待
                try:
                    # Find and click on '上新'
                    component = self.find_component_safely('Text', '上新')
                    if component:
                        self.driver.touch(component)
                        time.sleep(5)
                        self.driver.swipe_to_back()
                        time.sleep(2)
                    else:
                        Log.error('Failed to find 上新 button')
                except Exception as e:
                    Log.error(f'Error in step3: {str(e)}')

            self.execute_performance_step('淘宝-首页浏览-step1首页上下滑5次，间隔2s', 30, step1)
            self.execute_performance_step('淘宝-首页浏览-step2点击关注按钮并滑动几次', 10, step2)
            self.execute_performance_step('淘宝-首页浏览-step3点击上新标签并等待', 10, step3)

        except Exception as e:
            Log.error(f'Error in process: {str(e)}')
            raise
