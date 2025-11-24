"""
工具页面 - 包含各个工具的配置和执行界面
"""

from typing import Any

from PySide6.QtCore import QThread, Signal
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
from core.plugin_loader import PluginLoader
from core.result_processor import ResultProcessor
from core.tool_executor import ToolExecutor


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

        # 使用统一的执行方法
        result = self.executor.execute_tool(
            plugin_id=plugin_id,
            executable_path=cmd_executable,
            script_path=script_path,
            params=self.params.copy(),
            plugin_root_dir=plugin_root_dir,
            callback=output_callback,
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
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 工具描述
        desc_label = QLabel(self.tool.get_description())
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # 参数表单
        params_group = QGroupBox('参数配置')
        params_layout = QFormLayout()

        parameters = self.tool.get_parameters()
        for param_name, param_def in parameters.items():
            widget = self.create_param_widget(param_name, param_def)
            if widget:
                self.param_widgets[param_name] = widget
                label = param_def.get('label', param_name)
                params_layout.addRow(label + ':', widget)

        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        # 输出区域
        output_group = QGroupBox('执行输出')
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
        self.execute_button.clicked.connect(self.execute_tool)
        button_layout.addWidget(self.execute_button)

        self.cancel_button = QPushButton('取消')
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_execution)
        button_layout.addWidget(self.cancel_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

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
            widget = QComboBox()
            choices = param_def.get('choices', [])
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

        # 验证参数
        valid, error = self.tool.validate_parameters(params)
        if not valid:
            QMessageBox.warning(self, '参数错误', f'参数验证失败: {error}')
            return

        # 清空输出
        self.output_text.clear()
        self.output_text.append(f'开始执行工具: {self.tool.get_name()}\n')

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
        self.plugin_loader = PluginLoader()
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
