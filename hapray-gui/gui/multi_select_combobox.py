"""
多选下拉框组件
支持搜索过滤功能
"""

from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QSizePolicy,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger

logger = get_logger(__name__)


class CheckableComboBox(QComboBox):
    """支持多选的下拉框"""

    # 选择改变信号
    selection_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 设置视图
        self.view().pressed.connect(self.handle_item_pressed)

        # 使用自定义代理来显示复选框
        self.setItemDelegate(CheckBoxDelegate(self))

        # 设置模型
        self.model().dataChanged.connect(self.update_text)

        # 初始化文本
        self.update_text()

    def handle_item_pressed(self, index):
        """处理项目点击事件"""
        item = self.model().itemFromIndex(index)
        if item.checkState() == Qt.Checked:
            item.setCheckState(Qt.Unchecked)
        else:
            item.setCheckState(Qt.Checked)

    def update_text(self):
        """更新显示文本"""
        checked_items = self.get_checked_items()
        if not checked_items:
            self.setEditText('请选择...')
        elif len(checked_items) == 1:
            self.setEditText(checked_items[0])
        else:
            self.setEditText(f'已选择 {len(checked_items)} 项')

        # 发送选择改变信号
        self.selection_changed.emit(checked_items)

    def get_checked_items(self) -> list[str]:
        """获取所有选中的项目"""
        checked_items = []
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item and item.checkState() == Qt.Checked:
                checked_items.append(item.text())
        return checked_items

    def set_checked_items(self, items: list[str]):
        """设置选中的项目"""
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item:
                if item.text() in items:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
        self.update_text()

    def addItem(self, text, userData=None):
        """添加项目"""
        super().addItem(text, userData)
        item = self.model().item(self.count() - 1, 0)
        item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        item.setCheckState(Qt.Unchecked)

    def addItems(self, texts):
        """添加多个项目"""
        for text in texts:
            self.addItem(text)

    def clear(self):
        """清空所有项目"""
        super().clear()
        self.update_text()

    def hidePopup(self):
        """重写隐藏弹出框方法，防止点击后立即关闭"""
        # 不调用父类的hidePopup，保持弹出框打开
        pass

    def showPopup(self):
        """显示弹出框"""
        super().showPopup()


class CheckBoxDelegate(QStyledItemDelegate):
    """复选框代理"""

    def paint(self, painter, option, index):
        """绘制项目"""
        # 使用默认绘制
        super().paint(painter, option, index)


class SearchableMultiSelectComboBox(QComboBox):
    """支持多选和搜索的下拉框"""

    selection_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        logger.debug('SearchableMultiSelectComboBox 初始化开始')

        # 设置为可编辑，但不允许用户输入
        self.setEditable(True)
        line_edit = self.lineEdit()
        line_edit.setReadOnly(True)
        line_edit.setMinimumWidth(500)  # 设置内部 lineEdit 的最小宽度
        # 安装事件过滤器到 lineEdit，以便处理点击事件
        line_edit.installEventFilter(self)

        # 设置控件样式 - 与主界面风格一致
        self.setStyleSheet("""
            QComboBox {
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 6px 32px 6px 8px;
                background-color: #ffffff;
                color: #1f2937;
                min-width: 120px;
                transition: all 0.3s ease;
                selection-background-color: rgba(102, 126, 234, 0.2);
            }
            QComboBox:hover {
                border-color: #667eea;
            }
            QComboBox:focus {
                border-color: #667eea;
                box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.1);
            }
            QComboBox::drop-down {
                border: none;
                border-left: 1px solid #e5e7eb;
                width: 30px;
                subcontrol-origin: padding;
                subcontrol-position: center right;
                background-color: #ffffff;
                border-radius: 0 3px 3px 0;
            }
            QComboBox::drop-down:hover {
                background-color: rgba(102, 126, 234, 0.08);
            }
            QComboBox::down-arrow {
                color: #1f2937;
                font-size: 14px;
                font-weight: bold;
                width: 14px;
                height: 14px;
                qproperty-text: "▼";
            }
        """)

        # 设置控件本身的最小宽度和大小策略
        self.setMinimumWidth(500)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 创建过滤代理模型
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setSourceModel(self.model())

        # 创建列表视图并设置代理模型
        list_view = QListView()
        list_view.setModel(self.proxy_model)
        self.setView(list_view)

        # 创建搜索弹出窗口
        self.search_popup = SearchPopupWidget(self.proxy_model, parent=self)

        # 连接信号
        list_view.pressed.connect(self.handle_item_pressed)
        self.model().dataChanged.connect(self.update_text)

        # 初始化
        self.update_text()

        logger.debug(f'SearchableMultiSelectComboBox 初始化完成，当前项目数量: {self.count()}')

    def handle_item_pressed(self, index):
        """处理项目点击"""
        item = self.model().itemFromIndex(index)
        if item:
            if item.checkState() == Qt.Checked:
                item.setCheckState(Qt.Unchecked)
            else:
                item.setCheckState(Qt.Checked)
        # 对于多选下拉框，点击选项后不自动关闭，让用户可以继续选择
        # 用户点击外部区域时会自动关闭

    def update_text(self):
        """更新显示文本"""
        row_count = self.model().rowCount()
        logger.debug(f'MultiSelectComboBox.update_text 被调用，模型行数: {row_count}，控件 count: {self.count()}')
        checked_items = self.get_checked_items()
        if not checked_items:
            display_text = '请选择测试用例...'
            self.lineEdit().setText(display_text)
            logger.debug(f'更新显示文本为: "{display_text}"')
        elif len(checked_items) == 1:
            display_text = checked_items[0]
            self.lineEdit().setText(display_text)
            logger.debug(f'更新显示文本为: "{display_text}"')
        else:
            display_text = f'已选择 {len(checked_items)} 个测试用例'
            self.lineEdit().setText(display_text)
            logger.debug(f'更新显示文本为: "{display_text}"')

        self.selection_changed.emit(checked_items)

    def get_checked_items(self) -> list[str]:
        """获取所有选中的项目"""
        row_count = self.model().rowCount()
        logger.debug(f'MultiSelectComboBox.get_checked_items 被调用，模型行数: {row_count}')
        checked_items = []
        for i in range(row_count):
            item = self.model().item(i)
            if item:
                if item.checkState() == Qt.Checked:
                    checked_items.append(item.text())
            else:
                logger.warning(f'第 {i} 行的模型项为 None')
        logger.debug(f'选中的项目: {checked_items}，共 {len(checked_items)} 个')
        return checked_items

    def set_checked_items(self, items: list[str]):
        """设置选中的项目"""
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item:
                if item.text() in items:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
        self.update_text()

    def addItem(self, text, userData=None):
        """添加项目"""
        logger.debug(f'MultiSelectComboBox.addItem 被调用，添加项目: {text}')
        super().addItem(text, userData)
        item = self.model().item(self.count() - 1, 0)
        if item:
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Unchecked)
            logger.debug(f'项目 "{text}" 添加成功，当前总数: {self.count()}')
        else:
            logger.error(f'项目 "{text}" 添加失败，无法获取模型项')

    def addItems(self, texts):
        """添加多个项目"""
        logger.info(f'MultiSelectComboBox.addItems 被调用，准备添加 {len(texts)} 个项目')
        logger.debug(f'项目列表: {texts}')
        if not texts:
            logger.warning('MultiSelectComboBox.addItems 接收到空列表')
        for text in texts:
            self.addItem(text)
        logger.info(f'MultiSelectComboBox.addItems 完成，当前项目总数: {self.count()}')

    def clear(self):
        """清空所有项目"""
        old_count = self.count()
        logger.info(f'MultiSelectComboBox.clear 被调用，清空前项目数: {old_count}')
        super().clear()
        new_count = self.count()
        logger.info(f'MultiSelectComboBox.clear 完成，清空后项目数: {new_count}')
        self.update_text()

    def showPopup(self):
        """显示带有搜索功能的弹出框"""
        logger.debug('SearchableMultiSelectComboBox.showPopup 被调用')

        # 设置弹出窗口的位置和大小
        combo_rect = self.rect()
        popup_width = max(combo_rect.width(), 500)  # 至少500px宽，与输入框一致

        # 设置弹出窗口大小
        self.search_popup.setFixedWidth(popup_width)
        self.search_popup.adjustSize()  # 调整高度

        popup_pos = self.mapToGlobal(combo_rect.bottomLeft())
        self.search_popup.move(popup_pos)
        self.search_popup.show()

        # 设置焦点到搜索框
        self.search_popup.search_edit.setFocus()

    def hidePopup(self):
        """隐藏弹出框"""
        logger.debug('SearchableMultiSelectComboBox.hidePopup 被调用')
        if self.search_popup.isVisible():
            self.search_popup.hide()

    def eventFilter(self, obj, event):
        """事件过滤器，处理 lineEdit 的点击事件"""
        if (
            obj == self.lineEdit()
            and isinstance(event, QMouseEvent)
            and event.type() == QMouseEvent.Type.MouseButtonPress
            and event.button() == Qt.LeftButton
        ):
            # 点击 lineEdit 时显示下拉框（因为 lineEdit 是只读的，无法输入）
            try:
                view = self.view()
                if not view.isVisible():
                    logger.debug('点击 lineEdit，显示下拉框')
                    self.showPopup()
                    return True  # 阻止默认行为
            except Exception as e:
                logger.error(f'处理 lineEdit 点击事件时出错: {e}')
        return super().eventFilter(obj, event)


class SearchPopupWidget(QWidget):
    """带有搜索功能的弹出窗口"""

    def __init__(self, proxy_model, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.proxy_model = proxy_model
        self.parent_combo = parent

        # 设置窗口属性
        self.setWindowFlags(Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        # 设置窗口样式 - 与主界面风格一致
        self.setStyleSheet("""
            SearchPopupWidget {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                background-color: #ffffff;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            }
        """)

        # 创建布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        # 创建搜索框容器
        search_container = QWidget()
        search_container.setStyleSheet("""
            QWidget {
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                background-color: #f8f9fa;
                transition: all 0.3s ease;
            }
            QWidget:focus-within {
                border-color: #667eea;
                box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.1);
            }
        """)
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(8, 6, 8, 6)
        search_layout.setSpacing(6)

        # 搜索图标和标签
        search_label = QLabel('🔍')
        search_label.setStyleSheet('color: #666; font-size: 12px;')
        search_layout.addWidget(search_label)

        # 搜索输入框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('输入关键词搜索...')
        self.search_edit.setStyleSheet("""
            QLineEdit {
                border: none;
                background-color: transparent;
                font-size: 13px;
                color: #1f2937;
                padding: 2px;
                selection-background-color: rgba(102, 126, 234, 0.2);
            }
            QLineEdit:focus {
                outline: none;
            }
        """)
        self.search_edit.textChanged.connect(self.filter_items)
        search_layout.addWidget(self.search_edit)

        layout.addWidget(search_container)

        # 创建列表视图
        self.list_view = QListView()
        self.list_view.setModel(proxy_model)
        self.list_view.setMinimumHeight(250)
        self.list_view.setMaximumHeight(350)
        self.list_view.setStyleSheet("""
            QListView {
                border: none;
                border-radius: 6px;
                background-color: #ffffff;
                alternate-background-color: rgba(102, 126, 234, 0.02);
                selection-background-color: rgba(102, 126, 234, 0.1);
                font-size: 13px;
                padding: 2px;
                outline: none;
            }
            QListView::item {
                padding: 8px 12px;
                border-radius: 4px;
                margin: 2px 6px;
                transition: all 0.2s ease;
            }
            QListView::item:hover {
                background-color: rgba(102, 126, 234, 0.08);
            }
            QListView::item:selected {
                background-color: rgba(102, 126, 234, 0.15);
                color: #667eea;
                font-weight: 500;
            }
            /* 滚动条样式 - 与主界面一致 */
            QListView QScrollBar:vertical {
                background-color: #ffffff;
                width: 12px;
                border-radius: 6px;
                margin: 2px;
            }
            QListView QScrollBar::handle:vertical {
                background-color: #d1d5db;
                border-radius: 6px;
                min-height: 30px;
                transition: background-color 0.3s ease;
            }
            QListView QScrollBar::handle:vertical:hover {
                background-color: #9ca3af;
            }
            QListView QScrollBar::add-line:vertical,
            QListView QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            QListView QScrollBar::add-page:vertical,
            QListView QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        self.list_view.pressed.connect(self.handle_item_pressed)
        layout.addWidget(self.list_view)

        # 设置窗口大小
        self.setMinimumWidth(500)
        self.adjustSize()

    def filter_items(self, text):
        """根据输入文本过滤项目"""
        self.proxy_model.setFilterFixedString(text)

    def handle_item_pressed(self, index):
        """处理项目点击事件"""
        # 获取源模型中的项目
        source_index = self.proxy_model.mapToSource(index)
        item = self.parent_combo.model().itemFromIndex(source_index)

        if item:
            if item.checkState() == Qt.Checked:
                item.setCheckState(Qt.Unchecked)
            else:
                item.setCheckState(Qt.Checked)

    def showEvent(self, event):
        """显示事件，清空搜索框"""
        super().showEvent(event)
        self.search_edit.clear()
        self.filter_items('')  # 重置过滤器

    def hideEvent(self, event):
        """隐藏事件，更新父控件文本"""
        super().hideEvent(event)
        self.parent_combo.update_text()


# 保持向后兼容，为原来的类名创建一个别名
MultiSelectComboBox = SearchableMultiSelectComboBox
