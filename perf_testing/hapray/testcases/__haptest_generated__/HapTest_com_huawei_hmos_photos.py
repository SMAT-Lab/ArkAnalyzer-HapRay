"""
Auto-generated HapTest case
Application: 图库 (com.huawei.hmos.photos)
Strategy: depth_first
Max Steps: 20
"""

from hapray.haptest import HapTest


class HapTest_com_huawei_hmos_photos(HapTest):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(
            tag=self.TAG,
            configs=controllers,
            app_package='com.huawei.hmos.photos',
            app_name='图库',
            strategy_type='depth_first',
            max_steps=20
        )
