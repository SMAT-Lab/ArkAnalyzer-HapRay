"""
Auto-generated HapTest case
Application: 示例应用 (com.example.app)
Strategy: depth_first
Max Steps: 30
"""

from hapray.haptest import HapTest


class HapTest_com_example_app(HapTest):
    def __init__(self, controllers):
        super().__init__(
            tag='HapTest_com_example_app',
            configs=controllers,
            app_package='com.example.app',
            app_name='示例应用',
            strategy_type='depth_first',
            max_steps=30
        )
