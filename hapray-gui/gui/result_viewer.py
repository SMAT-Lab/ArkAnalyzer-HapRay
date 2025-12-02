"""
结果查看器 - 查看工具执行历史结果
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from core.result_processor import ResultProcessor


class ResultViewer(QWidget):
    """结果查看器"""

    def __init__(self):
        super().__init__()
        self.processor = ResultProcessor()
        self.config = ConfigManager()
        self.init_ui()
        self.refresh_results()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        refresh_button = QPushButton('刷新')
        refresh_button.clicked.connect(self.refresh_results)
        toolbar_layout.addWidget(refresh_button)

        self.open_dir_button = QPushButton('打开输出目录')
        self.open_dir_button.clicked.connect(self.open_output_directory)
        self.open_dir_button.setEnabled(False)
        toolbar_layout.addWidget(self.open_dir_button)

        self.copy_path_button = QPushButton('复制路径')
        self.copy_path_button.clicked.connect(self.copy_output_path)
        self.copy_path_button.setEnabled(False)
        toolbar_layout.addWidget(self.copy_path_button)


        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)

        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 左侧：结果列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        list_label = QLabel('执行历史')
        left_layout.addWidget(list_label)

        self.result_list = QListWidget()
        self.result_list.itemSelectionChanged.connect(self.on_result_selected)
        left_layout.addWidget(self.result_list)

        splitter.addWidget(left_widget)

        # 右侧：结果详情
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        detail_label = QLabel('结果详情')
        right_layout.addWidget(detail_label)

        self.result_detail = QTextEdit()
        self.result_detail.setReadOnly(True)
        self.result_detail.setFontFamily('Consolas')
        right_layout.addWidget(self.result_detail)

        splitter.addWidget(right_widget)

        # 设置分割比例
        splitter.setSizes([300, 900])

    def refresh_results(self):
        """刷新结果列表"""
        self.result_list.clear()

        # 获取所有工具的结果历史
        history = self.processor.get_result_history()

        for result_data in history:
            tool_name = result_data.get('tool_name', 'Unknown')
            timestamp = result_data.get('timestamp', '')
            success = result_data.get('success', False)

            status = '✓' if success else '✗'
            item_text = f'[{status}] {tool_name} - {timestamp}'

            self.result_list.addItem(item_text)
            # 保存结果数据到item
            item = self.result_list.item(self.result_list.count() - 1)
            item.setData(Qt.UserRole, result_data)

    def on_result_selected(self):
        """结果项被选中"""
        current_item = self.result_list.currentItem()
        if not current_item:
            # 没有选中项时禁用按钮
            self.open_dir_button.setEnabled(False)
            self.copy_path_button.setEnabled(False)
            return

        result_data = current_item.data(Qt.UserRole)
        if not result_data:
            # 没有数据时禁用按钮
            self.open_dir_button.setEnabled(False)
            self.copy_path_button.setEnabled(False)
            return

        # 显示结果详情
        detail_text = self.format_result_detail(result_data)
        self.result_detail.setPlainText(detail_text)

        # 检查是否有输出路径，启用相应按钮
        output_path = result_data.get('output_path')
        has_output_path = bool(output_path)
        self.open_dir_button.setEnabled(has_output_path)
        self.copy_path_button.setEnabled(has_output_path)

    def format_result_detail(self, result_data: dict) -> str:
        """格式化结果详情"""
        lines = []
        lines.append('=' * 60)
        lines.append(f'工具名称: {result_data.get("tool_name", "Unknown")}')
        lines.append(f'执行时间: {result_data.get("timestamp", "Unknown")}')
        lines.append(f'执行状态: {"成功" if result_data.get("success") else "失败"}')
        lines.append(f'消息: {result_data.get("message", "")}')
        lines.append('=' * 60)
        lines.append('')

        # 参数
        lines.append('参数:')
        params = result_data.get('params', {})
        for key, value in params.items():
            lines.append(f'  {key}: {value}')
        lines.append('')

        # 输出路径
        output_path = result_data.get('output_path')
        if output_path:
            lines.append(f'输出路径: {output_path}')
            lines.append('')

        # 错误信息
        error = result_data.get('error')
        if error:
            lines.append('错误信息:')
            lines.append(error)
            lines.append('')

        # 数据
        data = result_data.get('data')
        if data:
            lines.append('执行数据:')
            lines.append(json.dumps(data, indent=2, ensure_ascii=False))

        return '\n'.join(lines)

    def open_output_directory(self):
        """打开输出目录"""
        current_item = self.result_list.currentItem()
        if not current_item:
            return

        result_data = current_item.data(Qt.UserRole)
        if not result_data:
            return

        output_path = result_data.get('output_path')
        if not output_path:
            QMessageBox.warning(self, '警告', '没有输出路径信息')
            return

        path = Path(output_path)
        if not path.exists():
            QMessageBox.warning(self, '警告', f'路径不存在: {output_path}')
            return

        # 如果是文件，打开其所在目录
        if path.is_file():
            path = path.parent

        # 根据操作系统打开文件管理器
        try:
            if sys.platform == 'win32':
                os.startfile(str(path))
            elif sys.platform == 'darwin':
                subprocess.run(['open', str(path)], check=True)
            else:  # linux
                subprocess.run(['xdg-open', str(path)], check=True)
        except Exception as e:
            QMessageBox.critical(self, '错误', f'打开目录失败: {e}')

    def copy_output_path(self):
        """复制输出路径到剪贴板"""
        current_item = self.result_list.currentItem()
        if not current_item:
            return

        result_data = current_item.data(Qt.UserRole)
        if not result_data:
            return

        output_path = result_data.get('output_path')
        if not output_path:
            QMessageBox.warning(self, '警告', '没有输出路径信息')
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(str(output_path))
        QMessageBox.information(self, '成功', f'路径已复制到剪贴板:\n{output_path}')

