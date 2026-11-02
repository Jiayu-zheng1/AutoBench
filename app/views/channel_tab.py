"""ChannelTab — 单通道标签页：控制栏 + TestTable + LogPanel。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.models.test_plan import TestStep
from app.views.log_panel import LogPanel
from app.views.test_table import TestTable
from app.views.theme import Colors


class ChannelTab(QWidget):
    """一个通道的测试视图：通道状态 + 表格 + 日志。"""

    def __init__(self, channel_id: str, parent=None):
        super().__init__(parent)
        self._channel_id = channel_id
        self._testing = False
        self._test_enabled = True
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 通道控制栏 ──
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 6)
        bar.setSpacing(8)

        self._name_lbl = QLabel(self._channel_id)
        self._name_lbl.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {Colors.TEXT_PRIMARY}; background: transparent;"
        )
        bar.addWidget(self._name_lbl)

        bar.addStretch()

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(
            f"font-size: 12px; color: {Colors.TEXT_TERTIARY}; background: transparent;"
        )
        bar.addWidget(self._status_lbl)

        layout.addLayout(bar)

        # ── 表格 + 日志分栏 ──
        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {Colors.SEPARATOR}; }}"
        )

        self.test_table = TestTable()
        self.log_panel = LogPanel()

        splitter.addWidget(self.test_table)
        splitter.addWidget(self.log_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter, 1)

    # ── 公共接口 ──

    @property
    def channel_id(self) -> str:
        return self._channel_id

    def set_test_enabled(self, enabled: bool):
        """未勾选“是否测试”的通道仅展示，不参与测试。"""
        self._test_enabled = enabled
        if not enabled:
            self._testing = False
            self._status_lbl.setText("不测试")
            self._status_lbl.setStyleSheet(
                f"font-size: 12px; color: {Colors.TEXT_TERTIARY}; background: transparent;"
            )
        elif not self._testing:
            self.set_running(False)

    def set_running(self, running: bool):
        if not self._test_enabled:
            return
        self._testing = running
        if running:
            self._status_lbl.setText("Running…")
            self._status_lbl.setStyleSheet(
                f"font-size: 12px; color: {Colors.RUNNING}; font-weight: 600; background: transparent;"
            )
        else:
            self._status_lbl.setText("Ready")
            self._status_lbl.setStyleSheet(
                f"font-size: 12px; color: {Colors.TEXT_TERTIARY}; background: transparent;"
            )

    def set_done(self, passed: bool):
        if not self._test_enabled:
            return
        self._testing = False
        if passed:
            self._status_lbl.setText("PASS")
            self._status_lbl.setStyleSheet(
                f"font-size: 12px; color: {Colors.SUCCESS}; font-weight: 600; background: transparent;"
            )
        else:
            self._status_lbl.setText("FAIL")
            self._status_lbl.setStyleSheet(
                f"font-size: 12px; color: {Colors.DANGER}; font-weight: 600; background: transparent;"
            )

    def load_config(self, csv_rows: list[TestStep], headers: list[str] = None):
        self.test_table.load_config(csv_rows, headers)

    def clear_results(self):
        self.test_table.clear_results()
        self.log_panel.clear_log()

    def set_auto_scroll(self, enabled: bool):
        self.test_table.set_auto_scroll(enabled)
        self.log_panel.set_auto_scroll(enabled)

    def append_log(self, message: str):
        self.log_panel.append_log(message)

    def set_value(self, channel_id: str, display: str, value: str):
        if channel_id == self._channel_id:
            self.test_table.set_value(display, value)

    def set_result(self, channel_id: str, display: str, result: str):
        if channel_id == self._channel_id:
            self.test_table.set_result(display, result)

    def set_result_color(self, channel_id: str, display: str, result: str):
        if channel_id == self._channel_id:
            self.test_table.set_result_color(display, result)
