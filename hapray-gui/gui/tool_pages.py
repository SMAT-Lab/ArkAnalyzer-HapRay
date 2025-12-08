"""
工具页面 - 包含各个工具的配置和执行界面
"""

import sys
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.base_tool import BaseTool
from core.config_manager import ConfigManager
from core.file_utils import FileUtils
from core.logger import get_logger
from core.plugin_loader import PluginLoader
from core.result_processor import ResultProcessor
from core.tool_executor import ToolExecutor
from gui.multi_select_combobox import MultiSelectComboBox

logger = get_logger(__name__)


class DynamicChoicesLoader(QThread):
    """异步加载动态选项的线程"""

    choices_loaded = Signal(str, list)  # param_name, choices

    def __init__(self, param_name: str, choices_func_name: str):
        super().__init__()
        self.param_name = param_name
        self.choices_func_name = choices_func_name

    def run(self):
        """后台加载选项"""
        try:
            choices = []
            if self.choices_func_name == 'get_testcases':
                choices = FileUtils.get_testcases()
            elif self.choices_func_name == 'get_installed_apps':
                # 添加超时处理，避免长时间卡顿
                start_time = time.time()
                choices = FileUtils.get_installed_apps()
                elapsed = time.time() - start_time
                if elapsed > 2.0:  # 如果加载时间超过2秒，记录警告
                    logger.warning(f'加载应用列表耗时: {elapsed:.2f}秒')
            else:
                logger.warning(f'未知的动态选项函数: {self.choices_func_name}')

            self.choices_loaded.emit(self.param_name, choices)
        except Exception as e:
            logger.error(f'加载动态选项失败: {e}')
            self.choices_loaded.emit(self.param_name, [])


class ExecutionThread(QThread):
    """执行线程"""

    output_received = Signal(str)
    finished = Signal(str, str)  # tool_name, result_path

    def __init__(self, tool: BaseTool, params: dict[str, Any]):
        super().__init__()
        self.tool = tool
        self.params = params
        self.executor = ToolExecutor()
        self.processor = ResultProcessor()

    def run(self):
        """执行工具"""
        # 验证参数
        valid, error = self.tool.validate_parameters(self.params)
        if not valid:
            self.output_received.emit(f'参数验证失败: {error}')
            return

        # 执行工具
        def output_callback(text: str):
            self.output_received.emit(text)

        # 处理run_testcases参数（如果是字符串，需要分割成列表）
        if 'run_testcases' in self.params and isinstance(self.params['run_testcases'], str):
            testcases = self.params['run_testcases'].strip()
            if testcases:
                self.params['run_testcases'] = testcases.split()
            else:
                self.params.pop('run_testcases', None)

        # 处理devices参数（如果是字符串，需要分割成列表）
        if 'devices' in self.params and isinstance(self.params['devices'], str):
            devices = self.params['devices'].strip()
            if devices:
                self.params['devices'] = devices.split()
            else:
                self.params.pop('devices', None)

        # 获取插件ID
        plugin_id = self.tool.plugin_id if hasattr(self.tool, 'plugin_id') else self.tool.get_name()

        # 尝试获取 cmd 可执行文件路径
        cmd_executable = self.tool.get_cmd_executable()

        # 获取脚本路径
        script_path = self.tool.get_cmd_script_path()

        # 获取插件根目录
        plugin_root_dir = None
        if hasattr(self.tool, 'plugin_path') and self.tool.plugin_path:
            plugin_root_dir = str(self.tool.plugin_path.resolve())

        # 获取 action_mapping 配置（如果有 action）
        action_mapping = None
        if 'action' in self.params:
            action = self.params.get('action')
            if hasattr(self.tool, 'get_action_mapping'):
                action_mapping = self.tool.get_action_mapping(action)

        # 使用统一的执行方法
        result = self.executor.execute_tool(
            plugin_id=plugin_id,
            executable_path=cmd_executable,
            script_path=script_path,
            params=self.params.copy(),
            plugin_root_dir=plugin_root_dir,
            callback=output_callback,
            action_mapping=action_mapping,
        )

        # 保存结果
        result_path = self.processor.save_result(self.tool.get_name(), result, self.params)

        self.finished.emit(self.tool.get_name(), result_path)


class ToolPage(QWidget):
    """单个工具页面"""

    execution_finished = Signal(str, str)  # tool_name, result_path

    def __init__(self, tool: BaseTool):
        super().__init__()
        self.tool = tool
        self.param_widgets: dict[str, Any] = {}
        self.execution_thread: ExecutionThread = None
        self.current_action: str = None  # 当前选中的action
        self.params_group: QGroupBox = None  # 参数组控件引用
        self.dynamic_loaders: dict[str, DynamicChoicesLoader] = {}  # param_name -> loader
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 工具描述
        desc_label = QLabel(self.tool.get_description())
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # 初始化current_action（从外部设置，如main_window中的show_tool_config）
        actions = self.tool.get_all_actions() if hasattr(self.tool, 'get_all_actions') else []
        if actions:
            self.current_action = actions[0]  # 默认使用第一个action
        else:
            self.current_action = None

        # 参数表单
        self.params_group = QGroupBox('⚙️ 参数配置')
        self.params_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e5e7eb;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 16px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 4px 8px;
                color: #667eea;
                font-weight: bold;
                background-color: #ffffff;
                border-radius: 4px;
            }
        """)
        self.params_layout = QFormLayout()
        self.params_group.setLayout(self.params_layout)
        layout.addWidget(self.params_group)

        # 初始化参数表单
        self.rebuild_param_form()

        # 输出区域
        output_group = QGroupBox('📝 执行输出')
        output_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e5e7eb;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 16px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 4px 8px;
                color: #667eea;
                font-weight: bold;
                background-color: #ffffff;
                border-radius: 4px;
            }
        """)
        output_layout = QVBoxLayout()

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFontFamily('Consolas')
        output_layout.addWidget(self.output_text)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        output_layout.addWidget(self.progress_bar)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # 按钮
        button_layout = QHBoxLayout()

        self.execute_button = QPushButton('执行')
        self.execute_button.setObjectName('primary_button')
        self.execute_button.clicked.connect(self.execute_tool)
        button_layout.addWidget(self.execute_button)

        self.cancel_button = QPushButton('取消')
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_execution)
        button_layout.addWidget(self.cancel_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def on_action_changed(self, index: int):
        """Action选择改变时的回调"""
        if hasattr(self, 'action_selector'):
            self.current_action = self.action_selector.currentData()
            self.rebuild_param_form()

    def rebuild_param_form(self):
        """重建参数表单"""
        # 清理异步加载器
        self.cleanup_loaders()

        # 清空现有参数控件
        while self.params_layout.count():
            item = self.params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.param_widgets.clear()

        # 获取当前action的参数定义
        if self.current_action and hasattr(self.tool, 'get_parameters'):
            parameters = self.tool.get_parameters(self.current_action)
        else:
            parameters = self.tool.get_parameters() if hasattr(self.tool, 'get_parameters') else {}

        # 创建新的参数控件
        for param_name, param_def in parameters.items():
            widget = self.create_param_widget(param_name, param_def)
            if widget:
                self.param_widgets[param_name] = widget
                label = param_def.get('label', param_name)
                help_text = param_def.get('help', '')
                required = param_def.get('required', False)

                # 如果是必选参数，添加红色星号
                label_text = f'<span style="color: red;">*</span> {label}:' if required else label + ':'

                label_widget = QLabel(label_text)
                label_widget.setTextFormat(Qt.RichText)

                # 如果有帮助文本，添加到标签的工具提示
                if help_text:
                    tooltip = help_text
                    if required:
                        tooltip = f'【必填】{tooltip}'
                    label_widget.setToolTip(tooltip)
                elif required:
                    label_widget.setToolTip('【必填】')

                self.params_layout.addRow(label_widget, widget)

    def create_param_widget(self, param_name: str, param_def: dict[str, Any]) -> QWidget:
        """创建参数控件"""
        param_type = param_def.get('type', 'str')
        default = param_def.get('default')
        param_def.get('required', False)

        if param_type == 'bool':
            widget = QCheckBox()
            widget.setChecked(default if default is not None else False)
            return widget

        if param_type == 'int':
            widget = QSpinBox()
            widget.setMinimum(-999999)
            widget.setMaximum(999999)
            widget.setValue(default if default is not None else 0)
            return widget

        if param_type == 'file':
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)
            line_edit = QLineEdit()
            line_edit.setText(str(default) if default else '')
            browse_button = QPushButton('浏览...')
            browse_button.clicked.connect(
                lambda: self.browse_file(line_edit, param_def.get('filter', 'All Files (*.*)'))
            )
            layout.addWidget(line_edit)
            layout.addWidget(browse_button)
            return widget

        if param_type == 'dir':
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)
            line_edit = QLineEdit()
            line_edit.setText(str(default) if default else '')
            browse_button = QPushButton('浏览...')
            browse_button.clicked.connect(lambda: self.browse_directory(line_edit))
            layout.addWidget(line_edit)
            layout.addWidget(browse_button)
            return widget

        if param_type == 'choice':
            # 检查是否支持多选
            multi_select = param_def.get('multi_select', False)

            if multi_select:
                # 多选下拉框
                widget = MultiSelectComboBox()
                choices = param_def.get('choices', [])

                # 如果choices是函数名，则异步加载选项
                if isinstance(choices, str):
                    self._setup_dynamic_choices_async(param_name, choices, widget, multi_select=True, default=default)
                    # 先添加占位符选项
                    widget.addItems(['加载中...'])
                else:
                    widget.addItems(choices)
                    # 设置默认选中项
                    if default:
                        if isinstance(default, list):
                            widget.set_checked_items(default)
                        else:
                            widget.set_checked_items([str(default)])

                return widget
            # 单选下拉框
            widget = QComboBox()
            choices = param_def.get('choices', [])

            # 如果choices是函数名，则异步加载选项
            if isinstance(choices, str):
                self._setup_dynamic_choices_async(param_name, choices, widget, multi_select=False, default=default)
                # 先添加占位符选项
                widget.addItem('加载中...')
            else:
                widget.addItems(choices)
                if default:
                    index = widget.findText(str(default))
                    if index >= 0:
                        widget.setCurrentIndex(index)
            return widget

        # str
        widget = QLineEdit()
        widget.setText(str(default) if default else '')
        return widget

    def _setup_dynamic_choices_async(
        self, param_name: str, choices_func_name: str, widget: QWidget, multi_select: bool = False, default: Any = None
    ):
        """设置异步加载动态选项"""
        # 创建加载器
        loader = DynamicChoicesLoader(param_name, choices_func_name)
        loader.choices_loaded.connect(lambda p, c: self._on_choices_loaded(p, c, widget, multi_select, default))
        self.dynamic_loaders[param_name] = loader

        # 延迟启动加载，避免界面初始化时的卡顿
        QTimer.singleShot(100, loader.start)

    def _on_choices_loaded(self, param_name: str, choices: list, widget: QWidget, multi_select: bool, default: Any):
        """动态选项加载完成回调"""
        try:
            # 清理之前的加载器
            if param_name in self.dynamic_loaders:
                del self.dynamic_loaders[param_name]

            # 更新控件选项
            if multi_select and isinstance(widget, MultiSelectComboBox):
                # 清空现有选项
                widget.clear()
                widget.addItems(choices)

                # 设置默认选中项
                if default:
                    if isinstance(default, list):
                        widget.set_checked_items(default)
                    else:
                        widget.set_checked_items([str(default)])

            elif not multi_select and isinstance(widget, QComboBox):
                # 清空现有选项
                widget.clear()
                widget.addItems(choices)

                # 设置默认选中项
                if default:
                    index = widget.findText(str(default))
                    if index >= 0:
                        widget.setCurrentIndex(index)

            logger.debug(f'动态选项加载完成: {param_name}, {len(choices)} 个选项')

        except Exception as e:
            logger.error(f'更新动态选项失败: {e}')

    def browse_file(self, line_edit: QLineEdit, filter: str):
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(self, '选择文件', '', filter)
        if file_path:
            line_edit.setText(file_path)

    def browse_directory(self, line_edit: QLineEdit):
        """浏览目录"""
        dir_path = QFileDialog.getExistingDirectory(self, '选择目录')
        if dir_path:
            line_edit.setText(dir_path)

    def get_params(self) -> dict[str, Any]:
        """获取参数值"""
        params = {}
        for param_name, widget in self.param_widgets.items():
            if isinstance(widget, QCheckBox):
                params[param_name] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                params[param_name] = widget.value()
            elif isinstance(widget, MultiSelectComboBox):
                # 多选下拉框，返回选中项列表
                checked_items = widget.get_checked_items()
                if checked_items:
                    params[param_name] = checked_items
            elif isinstance(widget, QComboBox):
                params[param_name] = widget.currentText()
            elif isinstance(widget, QWidget):  # file or dir
                line_edit = widget.findChild(QLineEdit)
                if line_edit:
                    value = line_edit.text().strip()
                    if value:
                        params[param_name] = value
            else:  # QLineEdit
                value = widget.text().strip()
                if value:
                    params[param_name] = value
        return params

    def execute_tool(self):
        """执行工具"""
        params = self.get_params()

        # 如果有当前action，添加到参数中
        if self.current_action:
            params['action'] = self.current_action

        # 验证参数
        valid, error = self.tool.validate_parameters(params)
        if not valid:
            QMessageBox.warning(self, '参数错误', f'参数验证失败: {error}')
            return

        # 清空输出
        self.output_text.clear()
        action_name = ''
        if self.current_action and hasattr(self.tool, 'get_action_info'):
            action_info = self.tool.get_action_info(self.current_action)
            if action_info:
                action_name = f' - {action_info.get("name", self.current_action)}'
        self.output_text.append(f'开始执行工具: {self.tool.get_name()}{action_name}\n')

        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度

        # 禁用执行按钮，启用取消按钮
        self.execute_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

        # 创建执行线程
        self.execution_thread = ExecutionThread(self.tool, params)
        self.execution_thread.output_received.connect(self.on_output_received)
        self.execution_thread.finished.connect(self.on_execution_finished)
        self.execution_thread.start()

    def cancel_execution(self):
        """取消执行"""
        if self.execution_thread and self.execution_thread.isRunning():
            executor = ToolExecutor()
            plugin_id = self.tool.plugin_id if hasattr(self.tool, 'plugin_id') else self.tool.get_name()
            executor.cancel_task(plugin_id)
            self.execution_thread.terminate()
            self.execution_thread.wait()
            self.output_text.append('\n执行已取消')
            self.on_execution_finished(self.tool.get_name(), '')

    def cleanup_loaders(self):
        """清理异步加载器"""
        for loader in self.dynamic_loaders.values():
            if loader.isRunning():
                loader.terminate()
                loader.wait()
        self.dynamic_loaders.clear()

    def on_output_received(self, text: str):
        """接收输出"""
        self.output_text.append(text)
        # 自动滚动到底部
        scrollbar = self.output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_execution_finished(self, tool_name: str, result_path: str):
        """执行完成"""
        self.progress_bar.setVisible(False)
        self.execute_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

        if result_path:
            self.output_text.append(f'\n执行完成！结果保存在: {result_path}')
            self.execution_finished.emit(tool_name, result_path)
        else:
            self.output_text.append('\n执行失败')


class ToolPages(QWidget):
    """工具页面容器"""

    execution_finished = Signal(str, str)  # tool_name, result_path

    def __init__(self):
        super().__init__()
        self.config = ConfigManager()

        # 确定插件目录路径
        if hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'):
            # 打包后的环境
            exe_dir = Path(sys.executable).parent

            # 尝试多个可能的插件位置
            # 打包后exe在 dist/hapray/ 或 dist/ 目录
            # 插件在项目根目录（dist的父级或祖父级）
            possible_plugin_dirs = [
                exe_dir / 'tools',  # 同级tools目录
                exe_dir.parent / 'tools',  # 父级tools目录
                exe_dir.parent.parent,  # 祖父级目录（项目根目录）
                exe_dir.parent.parent.parent,  # 曾祖父级目录
                exe_dir.parent,  # 父级目录
            ]

            plugins_dir = None
            for dir_path in possible_plugin_dirs:
                if not dir_path.exists():
                    continue

                # 检查是否包含插件目录（如perf_testing等）
                try:
                    plugin_subdirs = [d for d in dir_path.iterdir() if d.is_dir() and (d / 'plugin.json').exists()]
                    if plugin_subdirs:
                        plugins_dir = dir_path
                        # 写入日志文件
                        try:
                            with open(exe_dir / 'plugin_loader_debug.log', 'a', encoding='utf-8') as f:
                                f.write(f'找到插件目录: {plugins_dir}, 插件: {[d.name for d in plugin_subdirs]}\n')
                        except Exception:  # 忽略日志写入错误
                            pass
                        break
                except Exception as e:
                    try:
                        with open(exe_dir / 'plugin_loader_debug.log', 'a', encoding='utf-8') as f:
                            f.write(f'检查目录失败 {dir_path}: {e}\n')
                    except Exception:  # 忽略日志写入错误
                        pass
                    continue

            if plugins_dir is None:
                # 如果找不到，使用exe的祖父级目录作为默认
                plugins_dir = exe_dir.parent.parent
                try:
                    with open(exe_dir / 'plugin_loader_debug.log', 'a', encoding='utf-8') as f:
                        f.write(f'未找到插件，使用默认目录: {plugins_dir}\n')
                except Exception:  # 忽略日志写入错误
                    pass
        else:
            # 开发环境，使用默认路径
            plugins_dir = None

        self.plugin_loader = PluginLoader(plugins_dir)
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 创建工具标签页
        self.tool_tabs = QTabWidget()
        layout.addWidget(self.tool_tabs)

        # 加载所有插件
        self.plugin_loader.load_all_plugins()

        # 添加各个工具页面
        plugins = self.plugin_loader.get_all_plugins()
        for plugin_id, tool in plugins.items():
            # 检查插件是否启用（优先使用插件ID，然后使用工具名称）
            enabled = self.config.is_plugin_enabled(plugin_id) or self.config.is_tool_enabled(tool.get_name())
            if enabled:
                tool_page = ToolPage(tool)
                tool_page.execution_finished.connect(self.execution_finished.emit)
                self.tool_tabs.addTab(tool_page, tool.get_name())
