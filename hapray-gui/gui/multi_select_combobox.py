"""
多选下拉框组件
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QComboBox, QListView, QSizePolicy, QStyledItemDelegate

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


class MultiSelectComboBox(QComboBox):
    """支持多选的下拉框（带确认按钮版本）"""

    selection_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        logger.debug('MultiSelectComboBox 初始化开始')

        # 设置为可编辑，但不允许用户输入
        self.setEditable(True)
        line_edit = self.lineEdit()
        line_edit.setReadOnly(True)
        line_edit.setMinimumWidth(500)  # 设置内部 lineEdit 的最小宽度
        # 安装事件过滤器到 lineEdit，以便处理点击事件
        line_edit.installEventFilter(self)

        # 设置控件本身的最小宽度和大小策略
        self.setMinimumWidth(500)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 创建列表视图
        list_view = QListView()
        self.setView(list_view)
        self.setModel(self.model())

        # 连接信号
        self.view().pressed.connect(self.handle_item_pressed)
        self.model().dataChanged.connect(self.update_text)

        # 初始化
        self.update_text()

        logger.debug(f'MultiSelectComboBox 初始化完成，当前项目数量: {self.count()}')

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
        """显示下拉框"""
        logger.debug('MultiSelectComboBox.showPopup 被调用')
        super().showPopup()

    def hidePopup(self):
        """隐藏下拉框"""
        logger.debug('MultiSelectComboBox.hidePopup 被调用')
        # 允许正常关闭下拉框（点击外部或按下 ESC 时）
        super().hidePopup()

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
