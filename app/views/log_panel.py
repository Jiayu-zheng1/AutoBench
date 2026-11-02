"""实时日志面板 — QTextEdit + HTML + macOS Cmd+C 可用。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence, QTextCursor
from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from app.views.theme import BORDER_RADIUS, FONT_MONO, MARGIN, Colors


class LogPanel(QWidget):
    """实时日志面板。QTextEdit 支持 HTML 渲染 + 原生选中复制。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup()

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QLabel("Log")
        header.setFont(QFont(FONT_MONO.split(",")[0].strip('"'), 11))
        header.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; padding: 0 {MARGIN}px;")
        layout.addWidget(header)

        self._auto_scroll = True
        self.text_edit = _CopyableTextEdit()
        self.text_edit.setFont(QFont(FONT_MONO.split(",")[0].strip('"'), 11))
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.LOG_BG};
                color: {Colors.LOG_TEXT};
                border: 1px solid {Colors.SEPARATOR};
                border-radius: {BORDER_RADIUS}px;
                padding: 10px 14px;
                selection-background-color: {Colors.PRIMARY};
                selection-color: white;
            }}
        """)
        layout.addWidget(self.text_edit)

    def set_auto_scroll(self, enabled: bool):
        self._auto_scroll = enabled

    def append_log(self, message: str):
        self.text_edit.append(message)
        if self._auto_scroll:
            self.text_edit.moveCursor(QTextCursor.End)

    def clear_log(self):
        self.text_edit.clear()


class _CopyableTextEdit(QTextEdit):
    """不使用 setReadOnly(True)（它会禁用 macOS Cmd+C），改为手动阻止编辑。

    macOS 上当 setReadOnly=True 时，AppKit 认定此控件不需要编辑快捷键，
    Cmd+C 在原生层就被吞掉了，无法通过 keyPressEvent 拦截。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # 不使用 setReadOnly(True)
        # 仅阻止文本插入 + 粘贴
        self.setAcceptRichText(False)

    def keyPressEvent(self, event):
        # 允许复制（Cmd+C / Ctrl+C）→ 调用全局 copy 槽
        if (event.modifiers() in (Qt.ControlModifier, Qt.MetaModifier)
                and event.key() == Qt.Key_C) \
                or event.matches(QKeySequence.Copy):
            self.copy()
            return
        # 允许全选
        if (event.modifiers() in (Qt.ControlModifier, Qt.MetaModifier)
                and event.key() == Qt.Key_A):
            self.selectAll()
            return
        # 允许导航键 / Shift+↑↓ 选择
        if event.key() in (
            Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down,
            Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Home, Qt.Key_End,
        ):
            super().keyPressEvent(event)
            return
        # 拦截所有会导致文本写入的按键
        if event.text() and not event.modifiers():
            return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        pass  # 阻止粘贴（Cmd+V / Ctrl+V）
