"""
插件配置对话框 - 管理所有插件的配置项
每个有配置的插件都有独立的配置窗口
"""

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from core.plugin_loader import PluginLoader


class PluginConfigDialog(QDialog):
    """插件配置对话框 - 为单个插件显示配置"""

    def __init__(self, parent=None, plugin_id: str = None):
        """
        初始化插件配置对话框

        Args:
            parent: 父窗口
            plugin_id: 插件ID，如果为None则显示第一个有配置的插件
        """
        super().__init__(parent)
        self.config = ConfigManager()
        self.plugin_loader = PluginLoader()
        self.plugin_id = plugin_id
        self.config_widgets: dict[str, Any] = {}  # config_key -> widget
        self.init_ui()
        self.load_config()

    def init_ui(self):
        """初始化UI"""
        # 加载所有插件
        self.plugin_loader.load_all_plugins()
        plugins = self.plugin_loader.get_all_plugins()

        # 如果没有指定插件ID，使用第一个有配置的插件
        if not self.plugin_id:
            for pid, tool in plugins.items():
                if hasattr(tool, 'get_config_schema'):
                    config_schema = tool.get_config_schema()
                    if config_schema.get('items'):
                        self.plugin_id = pid
                        break

        # 获取插件
        if not self.plugin_id or self.plugin_id not in plugins:
            self.setWindowTitle('插件配置')
            layout = QVBoxLayout(self)
            label = QLabel('未找到插件配置')
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            return

        self.tool = plugins[self.plugin_id]
        plugin_name = self.tool.get_name()
        self.setWindowTitle(f'{plugin_name} - 配置')
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel(f'{plugin_name} 配置')
        title_label.setStyleSheet('font-size: 16px; font-weight: bold; margin-bottom: 10px;')
        layout.addWidget(title_label)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        # 配置表单容器
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(15)

        # 获取配置项
        config_schema = self.tool.get_config_schema()
        config_items = config_schema.get('items', {})

        if config_items:
            for config_key, config_def in config_items.items():
                widget = self.create_config_widget(config_key, config_def)
                if widget:
                    self.config_widgets[config_key] = widget
                    label = config_def.get('label', config_key)
                    help_text = config_def.get('help', '')

                    # 添加标签
                    form_layout.addRow(label + ':', widget)

                    # 添加帮助文本
                    if help_text:
                        help_label = QLabel(help_text)
                        help_label.setStyleSheet('color: #6b7280; font-size: 12px; margin-left: 0px;')
                        form_layout.addRow('', help_label)
        else:
            no_config_label = QLabel('该插件没有配置项')
            no_config_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            form_layout.addRow(no_config_label)

        scroll_area.setWidget(form_widget)
        layout.addWidget(scroll_area)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        save_button = QPushButton('保存')
        save_button.setMinimumWidth(80)
        save_button.clicked.connect(self.save_and_accept)
        button_layout.addWidget(save_button)

        cancel_button = QPushButton('取消')
        cancel_button.setMinimumWidth(80)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def create_config_widget(self, config_key: str, config_def: dict[str, Any]) -> QWidget:
        """创建配置项控件"""
        config_type = config_def.get('type', 'str')
        default = config_def.get('default')

        # 从配置中读取当前值，如果没有则使用默认值
        current_value = (
            self.tool.get_config_value(config_key, default)
            if hasattr(self.tool, 'get_config_value')
            else default
        )

        if config_type == 'bool':
            widget = QCheckBox()
            widget.setChecked(current_value if current_value is not None else False)
            return widget

        if config_type == 'int':
            widget = QSpinBox()
            widget.setMinimum(-999999)
            widget.setMaximum(999999)
            widget.setValue(current_value if current_value is not None else 0)
            return widget

        if config_type == 'choice':
            widget = QComboBox()
            choices = config_def.get('choices', [])
            widget.addItems(choices)
            if current_value:
                index = widget.findText(str(current_value))
                if index >= 0:
                    widget.setCurrentIndex(index)
            return widget

        # str
        widget = QLineEdit()
        widget.setText(str(current_value) if current_value is not None else '')
        return widget

    def load_config(self):
        """加载配置项的值（已在创建控件时加载）"""
        pass

    def save_and_accept(self):
        """保存配置并接受"""
        try:
            if not hasattr(self, 'tool') or not hasattr(self.tool, 'set_config_value'):
                QMessageBox.warning(self, '警告', '无法保存配置')
                return

            # 获取该插件的所有配置项值
            for config_key, widget in self.config_widgets.items():
                if isinstance(widget, QCheckBox):
                    value = widget.isChecked()
                elif isinstance(widget, QSpinBox):
                    value = widget.value()
                elif isinstance(widget, QComboBox):
                    value = widget.currentText()
                else:  # QLineEdit
                    value = widget.text().strip()
                    value = value if value else None

                # 保存配置
                self.tool.set_config_value(config_key, value)

            QMessageBox.information(self, '成功', '配置已保存')
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存配置失败: {e}')