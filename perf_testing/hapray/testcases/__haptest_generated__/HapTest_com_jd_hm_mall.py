"""
Auto-generated HapTest case
Application: 京东 (com.jd.hm.mall)
Strategy: random
Max Steps: 20
"""

from hapray.haptest import HapTest


class HapTest_com_jd_hm_mall(HapTest):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(
            tag=self.TAG,
            configs=controllers,
            app_package='com.jd.hm.mall',
            app_name='京东',
            strategy_type='random',
            max_steps=20
        )
