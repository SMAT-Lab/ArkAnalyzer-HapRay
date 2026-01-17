"""
GUI样式定义文件
采用浅蓝色简约风格，参考web项目样式
"""

# 颜色定义
COLORS = {
    # 主色调 - 浅蓝色系
    'primary': '#667eea',
    'primary_dark': '#5a67d8',
    'primary_light': '#7c3aed',
    # 背景色
    'background': '#f5f7fa',
    'background_light': '#ffffff',
    'background_dark': '#f8f9fa',
    # 文字颜色
    'text_primary': '#1f2937',
    'text_secondary': '#6b7280',
    'text_light': '#9ca3af',
    # 边框颜色
    'border_light': '#e5e7eb',
    'border_medium': '#d1d5db',
    'border_dark': '#9ca3af',
    # 状态颜色
    'success': '#10b981',
    'warning': '#f59e0b',
    'error': '#ef4444',
    'info': '#3b82f6',
    # 阴影
    'shadow_sm': '0 1px 2px rgba(0, 0, 0, 0.05)',
    'shadow_md': '0 4px 6px rgba(0, 0, 0, 0.1)',
    'shadow_lg': '0 10px 15px rgba(0, 0, 0, 0.1)',
}

# 主样式表
MAIN_STYLE = f"""
/* 全局样式 */
QWidget {{
    background-color: {COLORS['background']};
    color: {COLORS['text_primary']};
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 14px;
}}

/* 主窗口 */
QMainWindow {{
    background-color: {COLORS['background']};
}}

/* 菜单栏 */
QMenuBar {{
    background-color: {COLORS['background_light']};
    border-bottom: 1px solid {COLORS['border_light']};
    padding: 4px 8px;
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 4px 12px;
    border-radius: 6px;
    margin: 0 2px;
}}

QMenuBar::item:selected {{
    background-color: rgba(102, 126, 234, 0.1);
    color: {COLORS['primary']};
}}

QMenuBar::item:pressed {{
    background-color: rgba(102, 126, 234, 0.2);
}}

/* 菜单 */
QMenu {{
    background-color: {COLORS['background_light']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
    padding: 4px 0px;
}}

QMenu::item {{
    padding: 8px 24px;
    border-radius: 4px;
    margin: 2px 4px;
}}

QMenu::item:selected {{
    background-color: rgba(102, 126, 234, 0.1);
    color: {COLORS['primary']};
}}

QMenu::separator {{
    height: 1px;
    background-color: {COLORS['border_light']};
    margin: 4px 8px;
}}

/* 状态栏 */
QStatusBar {{
    background-color: {COLORS['background_light']};
    border-top: 1px solid {COLORS['border_light']};
    padding: 4px 8px;
}}

/* 标签页 */
QTabWidget::pane {{
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
    background-color: {COLORS['background_light']};
}}

QTabBar::tab {{
    background-color: {COLORS['background_light']};
    border: 1px solid {COLORS['border_light']};
    padding: 8px 16px;
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
    color: {COLORS['text_secondary']};
}}

QTabBar::tab:selected {{
    background-color: {COLORS['background']};
    color: {COLORS['primary']};
    border-bottom: 2px solid {COLORS['primary']};
}}

QTabBar::tab:hover {{
    background-color: rgba(102, 126, 234, 0.05);
    color: {COLORS['primary_dark']};
}}

/* 树形控件 - 功能列表 */
QTreeWidget {{
    background-color: {COLORS['background_light']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
    alternate-background-color: rgba(102, 126, 234, 0.02);
}}

QTreeWidget::item {{
    padding: 6px 8px;
    border-radius: 4px;
    margin: 1px 4px;
}}

QTreeWidget::item:selected {{
    background-color: rgba(102, 126, 234, 0.15);
    color: {COLORS['primary']};
}}

QTreeWidget::item:hover {{
    background-color: rgba(102, 126, 234, 0.08);
}}

QTreeWidget::branch {{
    background: transparent;
}}

QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings {{
    border-image: none;
    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwIDMuNUw3LjUgNi41IDEwIDkuNSIgc3Ryb2tlPSIjOWNhM2FmIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
}}

QTreeWidget::branch:open:has-children:!has-siblings,
QTreeWidget::branch:open:has-children:has-siblings {{
    border-image: none;
    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTMuNSA2LjVMNi41IDMuNSA5LjUgNi41IiBzdHJva2U9IiM2NjdlZWEiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPg==);
}}

/* 分组框 */
QGroupBox {{
    font-weight: bold;
    border: 2px solid {COLORS['border_light']};
    border-radius: 8px;
    margin-top: 8px;
    padding-top: 16px;
    background-color: {COLORS['background_light']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 4px 8px;
    color: {COLORS['primary']};
    font-weight: bold;
    background-color: {COLORS['background_light']};
    border-radius: 4px;
}}

/* 标签 */
QLabel {{
    color: {COLORS['text_primary']};
}}

QLabel#title_label {{
    color: {COLORS['primary']};
    font-size: 16px;
    font-weight: bold;
    padding: 8px 0px;
}}

/* 按钮样式 */
QPushButton {{
    background-color: {COLORS['background_light']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
    color: {COLORS['text_primary']};
}}

QPushButton:hover {{
    background-color: rgba(102, 126, 234, 0.05);
    border-color: {COLORS['primary']};
    color: {COLORS['primary']};
}}

QPushButton:pressed {{
    background-color: rgba(102, 126, 234, 0.1);
    border-color: {COLORS['primary_dark']};
}}

QPushButton:disabled {{
    background-color: {COLORS['background_dark']};
    color: {COLORS['text_light']};
    border-color: {COLORS['border_medium']};
}}

/* 主按钮样式 */
QPushButton#primary_button {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 {COLORS['primary']},
                                stop:1 #764ba2);
    border: none;
    color: white;
    font-weight: bold;
}}

QPushButton#primary_button:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 {COLORS['primary_dark']},
                                stop:1 #6b46c1);
}}

QPushButton#primary_button:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #5a67d8,
                                stop:1 #553c9a);
}}

/* 输入框样式 */
QLineEdit {{
    border: 1px solid {COLORS['border_light']};
    border-radius: 6px;
    padding: 8px 12px;
    background-color: {COLORS['background_light']};
    color: {COLORS['text_primary']};
    selection-background-color: rgba(102, 126, 234, 0.2);
}}

QLineEdit:focus {{
    border-color: {COLORS['primary']};
}}

QLineEdit:hover {{
    border-color: {COLORS['primary_light']};
}}

/* 组合框 */
QComboBox {{
    border: 1px solid {COLORS['border_light']};
    border-radius: 6px;
    padding: 6px 32px 6px 8px;
    background-color: {COLORS['background_light']};
    color: {COLORS['text_primary']};
    min-width: 120px;
    selection-background-color: rgba(102, 126, 234, 0.2);
}}

QComboBox:hover {{
    border-color: {COLORS['primary']};
}}

QComboBox:focus {{
    border-color: {COLORS['primary']};
}}

QComboBox::drop-down {{
    border: none;
    border-left: 1px solid {COLORS['border_light']};
    width: 30px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
    background-color: {COLORS['background_light']};
    border-radius: 0 3px 3px 0;
}}

QComboBox::drop-down:hover {{
    background-color: rgba(102, 126, 234, 0.08);
}}

QComboBox::down-arrow {{
    /* 使用明确的Unicode向下箭头，确保绝对可见 */
    color: {COLORS['text_primary']};
    font-size: 14px;
    font-weight: bold;
    width: 14px;
    height: 14px;
    qproperty-text: "▼";  /* 强制显示向下箭头字符 */
}}

QComboBox QAbstractItemView {{
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
    background-color: {COLORS['background_light']};
    selection-background-color: rgba(102, 126, 234, 0.1);
    outline: none;
}}

QComboBox QAbstractItemView::item {{
    padding: 10px 16px;
    border-radius: 6px;
    margin: 3px 6px;
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: rgba(102, 126, 234, 0.15);
    color: {COLORS['primary']};
    font-weight: 500;
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: rgba(102, 126, 234, 0.08);
}}

/* 复选框 */
QCheckBox {{
    spacing: 8px;
    color: {COLORS['text_primary']};
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {COLORS['border_light']};
    border-radius: 4px;
    background-color: {COLORS['background_light']};
}}

QCheckBox::indicator:checked {{
    background-color: {COLORS['primary']};
    border-color: {COLORS['primary']};
    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTkgNEw3IDYiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPg==);
}}

QCheckBox::indicator:hover {{
    border-color: {COLORS['primary']};
}}

/* 文本编辑器 */
QTextEdit {{
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
    padding: 8px;
    background-color: {COLORS['background_light']};
    color: {COLORS['text_primary']};
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 13px;
    selection-background-color: rgba(102, 126, 234, 0.2);
}}

QTextEdit:focus {{
    border-color: {COLORS['primary']};
}}

/* 进度条 */
QProgressBar {{
    border: 1px solid {COLORS['border_light']};
    border-radius: 6px;
    text-align: center;
    background-color: {COLORS['background_light']};
    color: {COLORS['text_primary']};
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 {COLORS['primary']},
                                stop:1 {COLORS['primary_light']});
    border-radius: 5px;
}}

/* 滚动条 */
QScrollBar:vertical {{
    background-color: {COLORS['background_light']};
    width: 12px;
    border-radius: 6px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS['border_medium']};
    border-radius: 6px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS['border_dark']};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    border: none;
    background: none;
}}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: none;
}}

/* 分割器 */
QSplitter::handle {{
    background-color: {COLORS['border_light']};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

QSplitter::handle:hover {{
    background-color: {COLORS['primary']};
}}

/* 消息框 */
QMessageBox {{
    background-color: {COLORS['background_light']};
}}

QMessageBox QLabel {{
    color: {COLORS['text_primary']};
    font-size: 14px;
}}

QMessageBox QPushButton {{
    min-width: 80px;
    padding: 6px 16px;
}}

/* 对话框 */
QDialog {{
    background-color: {COLORS['background_light']};
    border-radius: 12px;
}}

QDialog QLabel {{
    color: {COLORS['text_primary']};
}}
"""


def apply_styles(app):
    """应用样式到应用程序"""
    app.setStyleSheet(MAIN_STYLE)


def get_color(name):
    """获取颜色值"""
    return COLORS.get(name, '#000000')
