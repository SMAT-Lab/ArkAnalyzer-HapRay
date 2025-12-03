"""
多选下拉框组件
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QListView, QStyledItemDelegate


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

        # 设置为可编辑，但不允许用户输入
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)

        # 创建列表视图
        list_view = QListView()
        self.setView(list_view)
        self.setModel(self.model())

        # 连接信号
        self.view().pressed.connect(self.handle_item_pressed)
        self.model().dataChanged.connect(self.update_text)

        # 初始化
        self.update_text()

    def handle_item_pressed(self, index):
        """处理项目点击"""
        item = self.model().itemFromIndex(index)
        if item.checkState() == Qt.Checked:
            item.setCheckState(Qt.Unchecked)
        else:
            item.setCheckState(Qt.Checked)
        return False  # 阻止关闭下拉框

    def update_text(self):
        """更新显示文本"""
        checked_items = self.get_checked_items()
        if not checked_items:
            self.lineEdit().setText('请选择测试用例...')
        elif len(checked_items) == 1:
            self.lineEdit().setText(checked_items[0])
        else:
            self.lineEdit().setText(f'已选择 {len(checked_items)} 个测试用例')

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
