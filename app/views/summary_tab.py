"""SummaryTab — 多通道测试汇总页：网格卡片显示各通道 PASS/FAIL/Yield。"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from app.views.theme import FONT_FAMILY, MARGIN, Colors


class _ChannelCard(QFrame):
    """单通道状态卡片：显示通道名、PASS/FAIL、统计。"""

    clicked = Signal(str)  # channel_id

    def __init__(self, channel_id: str, parent=None):
        super().__init__(parent)
        self._channel_id = channel_id
        self._input_count = 0
        self._fail_count = 0
        self._overall_pass = True
        self._finished = False
        self._build()
        self.setCursor(Qt.PointingHandCursor)

    def _build(self):
        self.setMinimumSize(200, 120)
        self.setStyleSheet(f"""
            _ChannelCard {{
                background-color: {Colors.CONTROL_BG};
                border: 1px solid {Colors.SEPARATOR};
                border-radius: 10px;
            }}
            _ChannelCard:hover {{
                border-color: {Colors.PRIMARY};
                background-color: #E8F0FE;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self._name_lbl = QLabel(self._channel_id)
        self._name_lbl.setFont(QFont(FONT_FAMILY.split(",")[0].strip('"'), 14, QFont.Bold))
        self._name_lbl.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none;")
        layout.addWidget(self._name_lbl)

        self._status_lbl = QLabel("⏳ 等待中…")
        self._status_lbl.setFont(QFont(FONT_FAMILY.split(",")[0].strip('"'), 18, QFont.Bold))
        self._status_lbl.setStyleSheet(f"color: {Colors.WARNING}; background: transparent; border: none;")
        self._status_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status_lbl)

        self._detail_lbl = QLabel("")
        self._detail_lbl.setFont(QFont(FONT_FAMILY.split(",")[0].strip('"'), 10))
        self._detail_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
        layout.addWidget(self._detail_lbl)

    def mousePressEvent(self, event):
        self.clicked.emit(self._channel_id)

    def add_result(self, passed: bool):
        self._input_count += 1
        if not passed:
            self._fail_count += 1

    def set_running(self):
        self._finished = False
        self._status_lbl.setText("⏳ RUNNING")
        self._status_lbl.setStyleSheet(f"color: {Colors.RUNNING}; font-weight: bold; background: transparent; border: none;")
        self._update_detail()

    def set_finished(self, overall_pass: bool):
        self._finished = True
        self._overall_pass = overall_pass
        if overall_pass:
            self._status_lbl.setText("✅ PASS")
            self._status_lbl.setStyleSheet(f"color: {Colors.SUCCESS}; font-weight: bold; background: transparent; border: none;")
        else:
            self._status_lbl.setText("❌ FAIL")
            self._status_lbl.setStyleSheet(f"color: {Colors.DANGER}; font-weight: bold; background: transparent; border: none;")
        self._update_detail()

    def _update_detail(self):
        if self._input_count > 0:
            pass_count = self._input_count - self._fail_count
            yld = round(pass_count / self._input_count * 100, 1)
            self._detail_lbl.setText(f"Items: {self._input_count} | Fail: {self._fail_count} | Yield: {yld}%")
        else:
            self._detail_lbl.setText("In:0 F:0 Y: —")

    def reset(self):
        self._input_count = 0
        self._fail_count = 0
        self._finished = False
        self._status_lbl.setText("⏳ 等待中…")
        self._status_lbl.setStyleSheet(f"color: {Colors.WARNING}; font-weight: bold; background: transparent; border: none;")
        self._detail_lbl.setText("")


class SummaryTab(QWidget):
    """多通道测试汇总页。"""

    channel_selected = Signal(str)  # 请求切换到指定通道 Tab

    def __init__(self, channel_count: int, parent=None):
        super().__init__(parent)
        self._channel_count = channel_count
        self._cards: dict[str, _ChannelCard] = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        layout.setSpacing(12)

        title = QLabel("多通道测试总览")
        title.setFont(QFont(FONT_FAMILY.split(",")[0].strip('"'), 16, QFont.Bold))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(title)

        self._grid = QGridLayout()
        self._grid.setSpacing(12)
        layout.addLayout(self._grid)

        # 创建通道卡片
        for i in range(self._channel_count):
            ch = f"CH{i + 1}"
            card = _ChannelCard(ch)
            card.clicked.connect(self.channel_selected.emit)
            self._cards[ch] = card
            row = i // 4
            col = i % 4
            self._grid.addWidget(card, row, col)

        layout.addStretch()

    @property
    def cards(self) -> dict[str, _ChannelCard]:
        return self._cards

    def get_card(self, channel_id: str) -> _ChannelCard | None:
        return self._cards.get(channel_id)

    def reset_all(self):
        for card in self._cards.values():
            card.reset()
