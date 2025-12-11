"""
全局配置对话框 - 管理全局配置项（输出目录、日志级别等）
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager


class GlobalConfigDialog(QDialog):
    """全局配置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.init_ui()
        self.load_config()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle('全局配置')
        self.setMinimumWidth(600)
        self.setMinimumHeight(300)

        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel('全局配置')
        title_label.setStyleSheet('font-size: 16px; font-weight: bold; margin-bottom: 10px;')
        layout.addWidget(title_label)

        # 配置表单
        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        # 输出目录配置
        output_dir_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText('请选择默认输出目录')
        output_dir_layout.addWidget(self.output_dir_edit)

        browse_button = QPushButton('浏览...')
        browse_button.clicked.connect(self.browse_output_dir)
        output_dir_layout.addWidget(browse_button)

        output_dir_widget = QWidget()
        output_dir_widget.setLayout(output_dir_layout)

        form_layout.addRow('默认输出目录:', output_dir_widget)

        # 添加帮助文本
        output_help = QLabel('所有工具的默认输出目录，可在执行时覆盖')
        output_help.setStyleSheet('color: #6b7280; font-size: 12px; margin-left: 0px;')
        form_layout.addRow('', output_help)

        # 日志级别配置
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR'])
        form_layout.addRow('日志级别:', self.log_level_combo)

        # 添加帮助文本
        log_help = QLabel('全局日志输出级别，影响所有工具的日志详细程度')
        log_help.setStyleSheet('color: #6b7280; font-size: 12px; margin-left: 0px;')
        form_layout.addRow('', log_help)

        layout.addLayout(form_layout)
        layout.addStretch()

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

    def browse_output_dir(self):
        """浏览输出目录"""
        current_dir = self.output_dir_edit.text() or str(Path.home())
        directory = QFileDialog.getExistingDirectory(
            self, '选择输出目录', current_dir, QFileDialog.Option.ShowDirsOnly
        )
        if directory:
            self.output_dir_edit.setText(directory)

    def load_config(self):
        """加载配置"""
        # 加载输出目录
        output_dir = self.config.get_global_config('output_dir', './hapray_output')
        self.output_dir_edit.setText(output_dir)

        # 加载日志级别
        log_level = self.config.get_global_config('log_level', 'INFO')
        index = self.log_level_combo.findText(log_level)
        if index >= 0:
            self.log_level_combo.setCurrentIndex(index)

    def save_and_accept(self):
        """保存配置并接受"""
        try:
            # 验证输出目录
            output_dir = self.output_dir_edit.text().strip()
            if not output_dir:
                QMessageBox.warning(self, '警告', '请设置输出目录')
                return

            # 保存配置
            self.config.set_global_config('output_dir', output_dir)
            self.config.set_global_config('log_level', self.log_level_combo.currentText())

            QMessageBox.information(self, '成功', '全局配置已保存')
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存配置失败: {e}')

