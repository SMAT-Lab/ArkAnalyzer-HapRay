"""
设置对话框
"""

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle('设置')
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # 标签页
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # 工具设置
        tools_tab = QWidget()
        tools_layout = QFormLayout(tools_tab)

        self.tool_paths = {}
        tools = ['perf_testing', 'optimization_detector', 'symbol_recovery', 'sa']

        for tool_name in tools:
            widget = QWidget()
            h_layout = QHBoxLayout(widget)
            h_layout.setContentsMargins(0, 0, 0, 0)

            line_edit = QLineEdit()
            line_edit.setPlaceholderText(f'输入 {tool_name} 的路径')
            browse_button = QPushButton('浏览...')
            browse_button.clicked.connect(lambda checked, le=line_edit, tn=tool_name: self.browse_tool_path(le, tn))

            h_layout.addWidget(line_edit)
            h_layout.addWidget(browse_button)

            self.tool_paths[tool_name] = line_edit
            tools_layout.addRow(f'{tool_name}:', widget)

        self.tabs.addTab(tools_tab, '工具路径')

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_button = QPushButton('确定')
        ok_button.clicked.connect(self.save_and_accept)
        button_layout.addWidget(ok_button)

        cancel_button = QPushButton('取消')
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def browse_tool_path(self, line_edit: QLineEdit, tool_name: str):
        """浏览工具路径"""
        dir_path = QFileDialog.getExistingDirectory(self, f'选择 {tool_name} 目录')
        if dir_path:
            line_edit.setText(dir_path)

    def load_settings(self):
        """加载设置"""
        for tool_name, line_edit in self.tool_paths.items():
            path = self.config.get_tool_path(tool_name)
            if path:
                line_edit.setText(path)

    def save_and_accept(self):
        """保存设置并接受"""
        for tool_name, line_edit in self.tool_paths.items():
            path = line_edit.text().strip()
            if path:
                self.config.set(f'tools.{tool_name}.path', path)

        self.accept()
