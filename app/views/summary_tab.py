"""SummaryTab — 多通道测试汇总页：网格卡片显示各通道 PASS/FAIL/Yield。"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

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
        self._test_enabled = True
        self._build()
        self.setCursor(Qt.PointingHandCursor)

    def _build(self):
        self.setMinimumSize(300, 210)
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

        # 主页单通道卡片内的 SN 扫描框（多通道测试共用全局 Start）
        self.sn_input = QLineEdit()
        self.sn_input.setPlaceholderText("扫描 SN")
        self.sn_input.setFixedHeight(30)
        self.sn_input.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {Colors.BORDER};
                border-radius: 5px;
                padding: 2px 8px;
                font-size: 13px;
                background: white;
            }}
            QLineEdit:focus {{
                border: 2px solid {Colors.PRIMARY};
                padding: 1px 7px;
            }}
            QLineEdit:disabled {{
                background: {Colors.WINDOW_BG};
                color: {Colors.TEXT_TERTIARY};
            }}
        """)
        layout.addWidget(self.sn_input)

        self._status_lbl = QLabel("等待中…")
        self._status_lbl.setFont(QFont(FONT_FAMILY.split(",")[0].strip('"'), 18, QFont.Bold))
        self._status_lbl.setStyleSheet(f"color: {Colors.WARNING}; background: transparent; border: none;")
        self._status_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status_lbl)

        # 独立的 Input / Pass / Fail 统计
        metrics = QHBoxLayout()
        metrics.setSpacing(8)
        self._metric_values: dict[str, QLabel] = {}
        for key, label, color in (
            ("input", "Input", Colors.TEXT_PRIMARY),
            ("pass", "Pass", Colors.SUCCESS),
            ("fail", "Fail", Colors.DANGER),
        ):
            col = QVBoxLayout()
            col.setSpacing(0)
            value = QLabel("0")
            value.setFont(QFont(FONT_FAMILY.split(",")[0].strip('"'), 16, QFont.Bold))
            value.setStyleSheet(
                f"color: {color}; background: transparent; border: none;"
            )
            value.setAlignment(Qt.AlignCenter)
            caption = QLabel(label)
            caption.setFont(QFont(FONT_FAMILY.split(",")[0].strip('"'), 9))
            caption.setStyleSheet(
                f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
            )
            caption.setAlignment(Qt.AlignCenter)
            col.addWidget(value)
            col.addWidget(caption)
            metrics.addLayout(col, 1)
            self._metric_values[key] = value
        layout.addLayout(metrics)

    def mousePressEvent(self, event):
        self.clicked.emit(self._channel_id)

    def set_test_enabled(self, enabled: bool):
        """未勾选“是否测试”的通道仅展示，不参与测试。"""
        self._test_enabled = enabled
        self.sn_input.setEnabled(enabled)
        self.reset()

    def get_sn(self) -> str:
        return self.sn_input.text().strip()

    def clear_sn(self):
        self.sn_input.clear()

    @property
    def test_enabled(self) -> bool:
        return self._test_enabled

    def set_running(self):
        if not self._test_enabled:
            return
        self._finished = False
        self._status_lbl.setText("RUNNING")
        self._status_lbl.setStyleSheet(f"color: {Colors.RUNNING}; font-weight: bold; background: transparent; border: none;")
        self._update_detail()

    def set_finished(self, overall_pass: bool):
        if not self._test_enabled:
            return
        self._finished = True
        self._overall_pass = overall_pass
        # 整个测试单元只统计一次
        self._input_count += 1
        if not overall_pass:
            self._fail_count += 1
        if overall_pass:
            self._status_lbl.setText("PASS")
            self._status_lbl.setStyleSheet(f"color: {Colors.SUCCESS}; font-weight: bold; background: transparent; border: none;")
        else:
            self._status_lbl.setText("FAIL")
            self._status_lbl.setStyleSheet(f"color: {Colors.DANGER}; font-weight: bold; background: transparent; border: none;")
        self._update_detail()

    def _update_detail(self):
        pass_count = self._input_count - self._fail_count
        self._metric_values["input"].setText(str(self._input_count))
        self._metric_values["pass"].setText(str(pass_count))
        self._metric_values["fail"].setText(str(self._fail_count))

    def reset(self, clear_counts: bool = True):
        if clear_counts:
            self._input_count = 0
            self._fail_count = 0
        self._finished = False
        self._overall_pass = True
        if not self._test_enabled:
            self._status_lbl.setText("不测试")
            self._status_lbl.setStyleSheet(
                f"color: {Colors.TEXT_TERTIARY}; font-weight: bold; background: transparent; border: none;"
            )
            for value in self._metric_values.values():
                value.setText("-")
            return
        self._status_lbl.setText("等待中…")
        self._status_lbl.setStyleSheet(f"color: {Colors.WARNING}; font-weight: bold; background: transparent; border: none;")
        self._update_detail()


class SummaryTab(QWidget):
    """多通道测试汇总页。"""

    channel_selected = Signal(str)  # 请求切换到指定通道 Tab

    def __init__(self, channel_count: int, enabled_flags: list[bool] | None = None,
                 parent=None):
        super().__init__(parent)
        self._channel_count = channel_count
        self._enabled_flags = enabled_flags or [True] * channel_count
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
        self._grid.setSpacing(20)
        layout.addLayout(self._grid)

        # 创建通道卡片
        for i in range(self._channel_count):
            ch = f"CH{i + 1}"
            card = _ChannelCard(ch)
            card.set_test_enabled(
                self._enabled_flags[i] if i < len(self._enabled_flags) else True
            )
            card.clicked.connect(self.channel_selected.emit)
            card.sn_input.returnPressed.connect(
                lambda ch=ch: self.focus_next_sn(ch)
            )
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

    def focus_next_sn(self, channel_id: str):
        """扫描完当前通道 SN 后，焦点跳到下一个已勾选通道的 SN 输入框。"""
        ids = list(self._cards)
        try:
            start = ids.index(channel_id) + 1
        except ValueError:
            start = 0
        for ch in ids[start:] + ids[:start]:
            card = self._cards[ch]
            if card.test_enabled:
                card.sn_input.setFocus()
                card.sn_input.selectAll()
                return

    def reset_all(self, clear_counts: bool = True):
        for card in self._cards.values():
            card.reset(clear_counts=clear_counts)
