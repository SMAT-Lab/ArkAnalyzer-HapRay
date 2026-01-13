"""
Auto-generated HapTest case
Application: weixing (com.example.wsywechat)
Strategy: random
Max Steps: 20
"""

from hapray.haptest import HapTest


class HapTest_com_example_wsywechat(HapTest):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(
            tag=self.TAG,
            configs=controllers,
            app_package='com.example.wsywechat',
            app_name='weixing',
            strategy_type='random',
            max_steps=20
        )
