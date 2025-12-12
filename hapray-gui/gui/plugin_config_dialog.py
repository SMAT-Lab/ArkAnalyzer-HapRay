"""
插件配置对话框 - 管理所有插件的配置项
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
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from core.plugin_loader import PluginLoader


class PluginConfigDialog(QDialog):
    """插件配置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.plugin_loader = PluginLoader()
        self.config_widgets: dict[str, dict[str, Any]] = {}  # plugin_id -> {config_key -> widget}
        self.init_ui()
        self.load_configs()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle('插件配置')
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)

        layout = QVBoxLayout(self)

        # 标签页
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # 加载所有插件
        self.plugin_loader.load_all_plugins()
        plugins = self.plugin_loader.get_all_plugins()

        # 为每个有配置项的插件创建标签页
        for plugin_id, tool in plugins.items():
            if hasattr(tool, 'get_config_schema'):
                config_schema = tool.get_config_schema()
                config_items = config_schema.get('items', {})
                if config_items:
                    tab = self.create_plugin_tab(plugin_id, tool, config_items)
                    plugin_name = tool.get_name()
                    self.tabs.addTab(tab, plugin_name)

        # 如果没有插件有配置项，显示提示
        if self.tabs.count() == 0:
            no_config_label = QWidget()
            no_config_layout = QVBoxLayout(no_config_label)
            no_config_layout.addStretch()

            label = QLabel('当前没有插件定义了配置项')
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_config_layout.addWidget(label)
            no_config_layout.addStretch()
            self.tabs.addTab(no_config_label, '无配置')

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        save_button = QPushButton('保存')
        save_button.clicked.connect(self.save_and_accept)
        button_layout.addWidget(save_button)

        cancel_button = QPushButton('取消')
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def create_plugin_tab(self, plugin_id: str, tool: Any, config_items: dict[str, Any]) -> QWidget:
        """为插件创建配置标签页"""
        tab = QWidget()
        layout = QFormLayout(tab)

        self.config_widgets[plugin_id] = {}

        for config_key, config_def in config_items.items():
            widget = self.create_config_widget(plugin_id, config_key, config_def, tool)
            if widget:
                self.config_widgets[plugin_id][config_key] = widget
                label = config_def.get('label', config_key)
                help_text = config_def.get('help', '')
                label_with_help = f'{label}\n({help_text})' if help_text else label
                layout.addRow(label_with_help + ':', widget)

        layout.addRow(QWidget())  # 添加空白行
        return tab

    def create_config_widget(self, plugin_id: str, config_key: str, config_def: dict[str, Any], tool: Any) -> QWidget:
        """创建配置项控件"""
        config_type = config_def.get('type', 'str')
        default = config_def.get('default')

        # 从配置中读取当前值，如果没有则使用默认值
        current_value = tool.get_config_value(config_key, default) if hasattr(tool, 'get_config_value') else default

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

    def load_configs(self):
        """加载所有配置项的值（已在创建控件时加载）"""
        pass

    def save_and_accept(self):
        """保存配置并接受"""
        try:
            plugins = self.plugin_loader.get_all_plugins()
            for plugin_id, tool in plugins.items():
                if plugin_id not in self.config_widgets:
                    continue

                if not hasattr(tool, 'set_config_value'):
                    continue

                # 获取该插件的所有配置项值
                for config_key, widget in self.config_widgets[plugin_id].items():
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
                    tool.set_config_value(config_key, value)

            QMessageBox.information(self, '成功', '配置已保存')
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存配置失败: {e}')
