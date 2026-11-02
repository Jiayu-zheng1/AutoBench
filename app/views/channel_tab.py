"""ChannelTab — 单通道标签页：控制栏 + TestTable + LogPanel。"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.models.test_plan import TestStep
from app.views.log_panel import LogPanel
from app.views.test_table import TestTable
from app.views.theme import Colors


class ChannelTab(QWidget):
    """一个通道的完整测试视图：SN 输入 + Start + 表格 + 日志。

    信号:
        start_requested(channel_id, sn) — 本通道请求开始测试
    """

    start_requested = Signal(str, str)

    def __init__(self, channel_id: str, parent=None):
        super().__init__(parent)
        self._channel_id = channel_id
        self._testing = False
        self._auto_mode = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 通道控制栏 ──
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 6)
        bar.setSpacing(8)

        self._name_lbl = QLabel(f"📡 {self._channel_id}")
        self._name_lbl.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {Colors.TEXT_PRIMARY}; background: transparent;"
        )
        bar.addWidget(self._name_lbl)

        bar.addSpacing(12)

        sn_label = QLabel("SN:")
        sn_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        bar.addWidget(sn_label)

        self.sn_input = QLineEdit()
        self.sn_input.setPlaceholderText("Scan SN")
        self.sn_input.setFixedWidth(180)
        self.sn_input.setFixedHeight(30)
        self.sn_input.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 13px;
                background: {Colors.WINDOW_BG};
            }}
            QLineEdit:focus {{
                border: 2px solid {Colors.PRIMARY};
            }}
        """)
        self.sn_input.returnPressed.connect(self._on_start)
        bar.addWidget(self.sn_input)

        self.start_btn = QPushButton("Start")
        self.start_btn.setFixedHeight(30)
        self.start_btn.setFixedWidth(70)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY};
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {Colors.PRIMARY_HOVER}; }}
            QPushButton:pressed {{ background-color: #0051AA; }}
            QPushButton:disabled {{ background-color: {Colors.TEXT_TERTIARY}; }}
        """)
        self.start_btn.clicked.connect(self._on_start)
        bar.addWidget(self.start_btn)

        self._status_lbl = QLabel("⏳ Ready")
        self._status_lbl.setStyleSheet(
            f"font-size: 12px; color: {Colors.TEXT_TERTIARY}; background: transparent;"
        )
        bar.addWidget(self._status_lbl)

        bar.addStretch()
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

    def _on_start(self):
        if self._testing:
            return
        sn = self.sn_input.text().strip()
        self.start_requested.emit(self._channel_id, sn)

    # ── 公共接口 ──

    @property
    def channel_id(self) -> str:
        return self._channel_id

    def set_running(self, running: bool):
        self._testing = running
        self.sn_input.setEnabled(not running and not self._auto_mode)
        if running:
            self.start_btn.setText("⏳")
            self.start_btn.setEnabled(False)
            self._status_lbl.setText("Running…")
            self._status_lbl.setStyleSheet(
                f"font-size: 12px; color: {Colors.RUNNING}; font-weight: 600; background: transparent;"
            )
        else:
            self.start_btn.setText("Start" if not self._auto_mode else "Auto")
            self.start_btn.setEnabled(not self._auto_mode)
            self._status_lbl.setText("Ready")
            self._status_lbl.setStyleSheet(
                f"font-size: 12px; color: {Colors.TEXT_TERTIARY}; background: transparent;"
            )
            if not self._auto_mode:
                self.sn_input.clear()

    def set_done(self, passed: bool):
        self._testing = False
        self.sn_input.setEnabled(not self._auto_mode)
        self.start_btn.setText("Start" if not self._auto_mode else "Auto")
        self.start_btn.setEnabled(not self._auto_mode)
        if passed:
            self._status_lbl.setText("✅ PASS")
            self._status_lbl.setStyleSheet(
                f"font-size: 12px; color: {Colors.SUCCESS}; font-weight: 600; background: transparent;"
            )
        else:
            self._status_lbl.setText("❌ FAIL")
            self._status_lbl.setStyleSheet(
                f"font-size: 12px; color: {Colors.DANGER}; font-weight: 600; background: transparent;"
            )

    def set_auto_mode(self, auto: bool):
        """切换自动/手动模式：自动模式下禁用 SN 输入和 Start 按钮。"""
        self._auto_mode = auto
        if auto:
            self.sn_input.setEnabled(False)
            self.sn_input.setPlaceholderText("自动测试模式…")
            self.start_btn.setEnabled(False)
            self.start_btn.setText("Auto")
        else:
            self.sn_input.setEnabled(True)
            self.sn_input.setPlaceholderText("Scan SN")
            self.start_btn.setEnabled(True)
            self.start_btn.setText("Start")

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
