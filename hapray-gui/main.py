"""
主程序入口
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from core.logger import get_logger
from gui.main_window import MainWindow

logger = get_logger(__name__)


def main():
    """主函数"""
    # 启用高DPI支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    app.setApplicationName('HapRay GUI')
    app.setOrganizationName('HapRay')

    # 创建主窗口
    window = MainWindow()
    window.show()

    logger.info('HapRay GUI 启动')

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
