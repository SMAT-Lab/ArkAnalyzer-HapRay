"""
主程序入口
"""

import io
import os
import sys

# 在 Windows 上设置 UTF-8 编码
if sys.platform == 'win32':
    # 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    # 重新配置 stdout 和 stderr 的编码
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            # 如果 reconfigure 方法失败，使用 TextIOWrapper 包装
            try:
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
            except Exception:
                pass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from core.logger import get_logger
from gui.main_window import MainWindow
from gui.styles import apply_styles

logger = get_logger(__name__)


def main():
    """主函数"""
    # 启用高DPI支持（新版本 PySide6 默认启用，无需手动设置）
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName('HapRay GUI')
    app.setOrganizationName('HapRay')

    # 应用样式
    apply_styles(app)

    # 创建主窗口
    window = MainWindow()
    window.show()

    logger.info('HapRay GUI 启动')

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
