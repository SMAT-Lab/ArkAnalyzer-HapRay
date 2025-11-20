"""
主窗口 - 应用程序的主界面
"""

import sys
from pathlib import Path

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from gui.plugin_config_dialog import PluginConfigDialog
from gui.result_viewer import ResultViewer
from gui.tool_pages import ToolPages


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.init_ui()
        self.setup_menu()
        self.setup_statusbar()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle('HapRay GUI - 工具集成平台')
        self.setGeometry(100, 100, 1200, 800)

        # 设置窗口图标
        icon_path = self._get_icon_path()
        if icon_path and icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # 从配置读取窗口大小
        width = self.config.get('ui.window_width', 1200)
        height = self.config.get('ui.window_height', 800)
        self.resize(width, height)

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # 创建标签页
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 工具页面
        self.tool_pages = ToolPages()
        self.tab_widget.addTab(self.tool_pages, '工具执行')

        # 结果查看器
        self.result_viewer = ResultViewer()
        self.tab_widget.addTab(self.result_viewer, '结果查看')

        # 连接信号
        self.tool_pages.execution_finished.connect(self.on_execution_finished)

    def setup_menu(self):
        """设置菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu('文件(&F)')

        exit_action = QAction('退出(&X)', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 设置菜单
        settings_menu = menubar.addMenu('设置(&S)')

        plugin_config_action = QAction('插件配置(&P)', self)
        plugin_config_action.triggered.connect(self.show_plugin_config)
        settings_menu.addAction(plugin_config_action)

        # 帮助菜单
        help_menu = menubar.addMenu('帮助(&H)')

        about_action = QAction('关于(&A)', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_statusbar(self):
        """设置状态栏"""
        self.statusBar().showMessage('就绪')

    def _get_icon_path(self):
        """获取图标文件路径（支持打包后的路径）"""
        # 获取当前文件所在目录
        current_dir = Path(__file__).parent.parent
        # 尝试多个可能的路径
        possible_paths = [
            current_dir / 'resources' / 'icon.ico',
            current_dir / 'icon.ico',
            Path.cwd() / 'resources' / 'icon.ico',
            Path.cwd() / 'icon.ico',
        ]
        # 如果是打包后的应用，尝试从 sys._MEIPASS 获取
        if hasattr(sys, '_MEIPASS'):
            possible_paths.insert(0, Path(sys._MEIPASS) / 'resources' / 'icon.ico')
            possible_paths.insert(1, Path(sys._MEIPASS) / 'icon.ico')

        for path in possible_paths:
            if path.exists():
                return path
        return None

    def show_plugin_config(self):
        """显示插件配置对话框"""
        dialog = PluginConfigDialog(self)
        dialog.exec()

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            '关于 HapRay GUI',
            'HapRay GUI v1.0.0\n\n'
            '工具集成平台\n'
            '整合了以下工具：\n'
            '- 动态测试 (perf_testing)\n'
            '- 优化检测 (optimization_detector)\n'
            '- 符号恢复 (symbol_recovery)\n'
            '- 静态分析 (sa)',
        )

    def on_execution_finished(self, tool_name: str, result_path: str):
        """执行完成回调"""
        self.statusBar().showMessage(f'工具 {tool_name} 执行完成', 5000)
        # 切换到结果查看标签页
        self.tab_widget.setCurrentIndex(1)
        # 刷新结果查看器
        self.result_viewer.refresh_results()

    def closeEvent(self, event):
        """关闭事件"""
        # 保存窗口大小
        self.config.set('ui.window_width', self.width())
        self.config.set('ui.window_height', self.height())
        event.accept()
