"""
Auto-generated HapTest case
Application: DH (com.example.deephierarchy)
Strategy: depth_first
Max Steps: 20
"""

from hapray.haptest import HapTest


class HapTest_com_example_deephierarchy(HapTest):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(
            tag=self.TAG,
            configs=controllers,
            app_package='com.example.deephierarchy',
            app_name='DH',
            strategy_type='depth_first',
            max_steps=20
        )
