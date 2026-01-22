"""
主窗口 - 应用程序的主界面
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from core.plugin_loader import PluginLoader
from gui.plugin_config_dialog import PluginConfigDialog
from gui.result_viewer import ResultViewer
from gui.tool_pages import ToolPage


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.plugin_loader = PluginLoader()
        self.current_tool_page = None  # 当前显示的工具页面
        self.init_ui()
        self.setup_menu()
        self.setup_statusbar()
        self.load_plugins()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle('HapRay GUI - 工具集成平台')
        self.setGeometry(100, 100, 1400, 900)

        # 设置窗口图标
        icon_path = self._get_icon_path()
        if icon_path and icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # 从配置读取窗口大小
        width = self.config.get('ui.window_width', 1400)
        height = self.config.get('ui.window_height', 900)
        self.resize(width, height)

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主水平布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # 创建分割器
        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        # 左侧功能树
        self.create_function_tree()

        # 右侧内容区域
        self.create_content_area()

        # 设置分割器比例
        self.splitter.setSizes([350, 1050])

    def create_function_tree(self):
        """创建左侧功能树"""
        # 功能树容器
        tree_container = QWidget()
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)

        # 标题
        title_label = QLabel('功能列表')
        title_label.setObjectName('title_label')
        tree_layout.addWidget(title_label)

        # 功能树
        self.function_tree = QTreeWidget()
        self.function_tree.setHeaderHidden(True)
        self.function_tree.itemClicked.connect(self.on_function_selected)
        tree_layout.addWidget(self.function_tree)

        self.splitter.addWidget(tree_container)

    def create_content_area(self):
        """创建右侧内容区域"""
        # 内容区域容器
        self.content_container = QWidget()
        content_layout = QVBoxLayout(self.content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # 工具配置区域
        self.tool_config_area = QWidget()
        self.tool_config_layout = QVBoxLayout(self.tool_config_area)
        content_layout.addWidget(self.tool_config_area)

        # 结果查看器（默认隐藏）
        self.result_viewer = ResultViewer()
        self.result_viewer.hide()  # 默认隐藏
        content_layout.addWidget(self.result_viewer)

        # 默认显示欢迎信息
        self.show_welcome_message()

        self.splitter.addWidget(self.content_container)

    def show_welcome_message(self):
        """显示欢迎信息"""
        welcome_widget = QWidget()
        welcome_layout = QVBoxLayout(welcome_widget)
        welcome_layout.setAlignment(Qt.AlignCenter)
        welcome_layout.setSpacing(16)

        # 欢迎图标区域
        icon_frame = QFrame()
        icon_frame.setFixedSize(80, 80)
        icon_frame.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 #667eea,
                                        stop:1 #764ba2);
            border-radius: 40px;
        """)
        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setAlignment(Qt.AlignCenter)

        icon_label = QLabel('🚀')
        icon_label.setStyleSheet('font-size: 32px; color: white;')
        icon_layout.addWidget(icon_label)

        welcome_layout.addWidget(icon_frame)

        # 欢迎标题
        welcome_label = QLabel('欢迎使用 HapRay GUI')
        welcome_label.setStyleSheet('font-size: 24px; font-weight: bold; color: #667eea; margin: 8px 0px;')
        welcome_layout.addWidget(welcome_label)

        # 副标题
        subtitle_label = QLabel('HapRay 工具集成平台')
        subtitle_label.setStyleSheet('font-size: 16px; color: #6b7280; margin-bottom: 16px;')
        welcome_layout.addWidget(subtitle_label)

        # 功能介绍
        features_layout = QVBoxLayout()
        features_layout.setSpacing(8)

        feature_items = [
            '🔧 动态测试 - 性能测试和trace收集',
            '⚡ 优化检测 - 二进制文件优化级别检测',
            '🔍 符号恢复 - 二进制符号恢复工具',
            '📊 静态分析 - HAP包静态分析',
        ]

        for feature in feature_items:
            feature_label = QLabel(feature)
            feature_label.setStyleSheet('font-size: 14px; color: #4b5563; padding: 4px 0px;')
            features_layout.addWidget(feature_label)

        welcome_layout.addLayout(features_layout)

        # 提示信息
        hint_frame = QFrame()
        hint_frame.setStyleSheet("""
            background-color: rgba(102, 126, 234, 0.05);
            border: 1px solid rgba(102, 126, 234, 0.1);
            border-radius: 8px;
            padding: 16px;
            margin: 16px 0px;
        """)
        hint_layout = QVBoxLayout(hint_frame)

        hint_title = QLabel('开始使用')
        hint_title.setStyleSheet('font-size: 16px; font-weight: bold; color: #667eea; margin-bottom: 8px;')
        hint_layout.addWidget(hint_title)

        hint_label = QLabel('请在左侧的功能列表中选择您要使用的工具')
        hint_label.setStyleSheet('font-size: 14px; color: #6b7280; line-height: 1.4;')
        hint_layout.addWidget(hint_label)

        welcome_layout.addWidget(hint_frame)

        welcome_layout.addStretch()

        # 替换工具配置区域的内容
        self._replace_tool_config_content(welcome_widget)

    def load_plugins(self):
        """加载插件并构建功能树"""
        self.plugin_loader.load_all_plugins()
        self.build_function_tree()

    def build_function_tree(self):
        """构建功能树"""
        self.function_tree.clear()

        plugins = self.plugin_loader.get_all_plugins()

        # 一级菜单配置（保留固定的两个一级菜单）
        top_level_menus = {
            '负载测试': {'icon': '📊', 'order': 1},
            '应用分析': {'icon': '🔍', 'order': 2},
        }

        # 收集所有 actions 及其菜单信息
        # 格式: {menu1: {action_key: {plugin_id, action_info, order, icon}}}
        menu_actions: dict[str, list[dict]] = {}

        for plugin_id, tool in plugins.items():
            # 检查插件是否启用
            enabled = self.config.is_plugin_enabled(plugin_id)
            if not enabled:
                continue

            # 获取所有 actions
            actions = tool.get_all_actions() if hasattr(tool, 'get_all_actions') else []

            for action_key in actions:
                action_info = tool.get_action_info(action_key) if hasattr(tool, 'get_action_info') else {}
                if not action_info:
                    continue

                # 获取 menu 配置
                menu_config = action_info.get('menu', {})
                menu1 = menu_config.get('menu1')

                # 如果 action 没有配置 menu1，跳过（不显示在菜单中）
                if not menu1 or menu1 not in top_level_menus:
                    continue

                # 获取菜单信息
                menu2 = menu_config.get('menu2')  # 二级菜单名称（可选）
                order = menu_config.get('order', 999)  # 排序，默认999（最后）
                icon = menu_config.get('icon', '⚙️')  # 图标，默认⚙️
                display_name = menu2 if menu2 else action_info.get('name', action_key)

                # 添加到对应的一级菜单
                if menu1 not in menu_actions:
                    menu_actions[menu1] = []

                menu_actions[menu1].append(
                    {
                        'plugin_id': plugin_id,
                        'action_key': action_key,
                        'action_info': action_info,
                        'display_name': display_name,
                        'order': order,
                        'icon': icon,
                    }
                )

        # 构建菜单结构
        # 按 order 排序一级菜单
        sorted_top_menus = sorted(top_level_menus.items(), key=lambda x: x[1]['order'])

        for menu_name, menu_config in sorted_top_menus:
            menu_item = QTreeWidgetItem(self.function_tree)
            menu_item.setText(0, f'{menu_config["icon"]} {menu_name}')

            # 获取该一级菜单下的所有 actions
            actions_list = menu_actions.get(menu_name, [])

            # 按 order 排序 actions
            actions_list.sort(key=lambda x: x['order'])

            # 创建二级菜单项
            for action_data in actions_list:
                action_item = QTreeWidgetItem(menu_item)
                action_item.setText(0, f'{action_data["icon"]} {action_data["display_name"]}')
                action_item.setData(
                    0,
                    Qt.UserRole,
                    {
                        'type': 'action',
                        'plugin_id': action_data['plugin_id'],
                        'action': action_data['action_key'],
                        'action_name': action_data['display_name'],
                        'menu_category': menu_name,
                    },
                )

            # 如果一级菜单下没有子项，隐藏该菜单
            if menu_item.childCount() == 0:
                self.function_tree.takeTopLevelItem(self.function_tree.indexOfTopLevelItem(menu_item))
            else:
                # 展开一级菜单
                menu_item.setExpanded(True)

        # 添加结果查看器节点
        result_item = QTreeWidgetItem(self.function_tree)
        result_item.setText(0, '📋 结果查看')
        result_item.setData(0, Qt.UserRole, {'type': 'result_viewer'})

    def on_function_selected(self, item, column):
        """功能选择事件"""
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        function_type = data.get('type')

        if function_type == 'result_viewer':
            self.show_result_viewer()
        elif function_type in ['plugin', 'action']:
            plugin_id = data.get('plugin_id')
            action = data.get('action')
            action_name = data.get('action_name')
            menu_category = data.get('menu_category')
            self.show_tool_config(plugin_id, action, action_name, menu_category)

    def show_tool_config(self, plugin_id, action=None, action_name=None, menu_category=None):
        """显示工具配置界面"""
        tool = self.plugin_loader.get_plugin(plugin_id)
        if not tool:
            return

        # 如果没有指定 action，使用第一个可用的 action
        if not action:
            actions = tool.get_all_actions() if hasattr(tool, 'get_all_actions') else []
            action = actions[0] if actions else ''

        # 创建工具页面
        tool_page = ToolPage(tool, action=action, action_name=action_name, menu_category=menu_category)

        tool_page.execution_finished.connect(self.on_execution_finished)

        # 显示工具配置页面
        self._replace_tool_config_content(tool_page)
        self.current_tool_page = tool_page

    def show_result_viewer(self):
        """显示结果查看器"""
        # 隐藏工具配置区域，显示结果查看器
        self.tool_config_area.hide()
        self.result_viewer.show()

    def _replace_tool_config_content(self, new_widget):
        """替换工具配置区域的内容"""
        # 清除现有内容
        while self.tool_config_layout.count():
            item = self.tool_config_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().setParent(None)

        # 添加新内容
        self.tool_config_layout.addWidget(new_widget)
        new_widget.show()

        # 确保显示状态正确
        self.tool_config_area.show()
        self.result_viewer.hide()

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
            'HapRay GUI v1.4.7\n\n'
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
        # 自动切换到结果查看器
        self.show_result_viewer()
        # 刷新结果查看器
        self.result_viewer.refresh_results()

    def closeEvent(self, event):
        """关闭事件"""
        # 保存窗口大小
        self.config.set('ui.window_width', self.width())
        self.config.set('ui.window_height', self.height())
        event.accept()
