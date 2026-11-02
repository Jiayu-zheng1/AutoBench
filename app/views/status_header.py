"""HIG-styled status indicator cards."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.views.animations import start_pulse, stop_pulse
from app.views.theme import (
    FONT_CAPTION_1,
    FONT_LARGE_TITLE,
    MARGIN,
    SECTION_GAP,
    STATUS_CARD_RADIUS,
    Colors,
)


class StatusHeader(QWidget):
    """Row of metric cards: Input, Fail, Yield, and test status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._input_count = 0
        self._fail_count = 0
        self._setup()

    def _setup(self):
        self.setFixedHeight(90)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(MARGIN, 10, MARGIN, 10)
        layout.setSpacing(SECTION_GAP)

        self.input_card = self._make_card("Input", "0", Colors.PRIMARY)
        self.fail_card = self._make_card("Fail", "0", Colors.DANGER)
        self.yield_card = self._make_card("Yield", "0%", Colors.SUCCESS)
        self.status_card = self._make_status_card()

        layout.addWidget(self.input_card)
        layout.addWidget(self.fail_card)
        layout.addWidget(self.yield_card)
        layout.addWidget(self.status_card)
        layout.addStretch()

    def _make_card(self, label: str, value: str, accent: str) -> QFrame:
        card = QFrame()
        card.setFixedSize(160, 68)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.CONTROL_BG};
                border: 1px solid {Colors.SEPARATOR};
                border-radius: {STATUS_CARD_RADIUS}px;
            }}
        """)

        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(16, 10, 16, 10)
        vbox.setSpacing(2)

        val = QLabel(value)
        val.setFont(self._font(*FONT_LARGE_TITLE))
        val.setStyleSheet(f"color: {accent}; background: transparent; border: none;")

        lbl = QLabel(label)
        lbl.setFont(self._font(*FONT_CAPTION_1))
        lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")

        vbox.addWidget(val)
        vbox.addWidget(lbl)
        return card

    def _make_status_card(self) -> QFrame:
        card = QFrame()
        card.setFixedSize(200, 68)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.WARNING};
                border-radius: {STATUS_CARD_RADIUS}px;
            }}
        """)

        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(16, 10, 16, 10)

        self.status_label = QLabel("Ready")
        self.status_label.setFont(self._font(*FONT_LARGE_TITLE))
        self.status_label.setStyleSheet("color: white; background: transparent; border: none;")
        self.status_label.setAlignment(Qt.AlignCenter)

        vbox.addWidget(self.status_label)
        return card

    def reset(self):
        self._input_count = 0
        self._fail_count = 0
        self._update_displays("0", "0", "0%")
        self.set_ready()

    def add_result(self, passed: bool):
        self._input_count += 1
        if not passed:
            self._fail_count += 1
        pass_count = self._input_count - self._fail_count
        pct = round(pass_count / self._input_count * 100, 2)
        self._update_displays(
            str(self._input_count),
            str(self._fail_count),
            f"{pct}%"
        )

    def set_running(self):
        self.status_label.setText("Running")
        self.status_card.setStyleSheet(f"""
            QFrame {{ background-color: {Colors.RUNNING}; border-radius: {STATUS_CARD_RADIUS}px; }}
        """)
        start_pulse(self.status_card, min_opacity=0.65)

    def set_pass(self):
        stop_pulse(self.status_card)
        self.status_label.setText("PASS")
        self.status_card.setStyleSheet(f"""
            QFrame {{ background-color: {Colors.SUCCESS}; border-radius: {STATUS_CARD_RADIUS}px; }}
        """)

    def set_fail(self):
        stop_pulse(self.status_card)
        self.status_label.setText("FAIL")
        self.status_card.setStyleSheet(f"""
            QFrame {{ background-color: {Colors.DANGER}; border-radius: {STATUS_CARD_RADIUS}px; }}
        """)

    def set_ready(self):
        stop_pulse(self.status_card)
        self.status_label.setText("Ready")
        self.status_card.setStyleSheet(f"""
            QFrame {{ background-color: {Colors.WARNING}; border-radius: {STATUS_CARD_RADIUS}px; }}
        """)

    def _update_displays(self, inp: str, fail: str, yld: str):
        self.input_card.layout().itemAt(0).widget().setText(inp)
        self.fail_card.layout().itemAt(0).widget().setText(fail)
        self.yield_card.layout().itemAt(0).widget().setText(yld)

    def _font(self, family: str, size: int, weight: str):
        f = QFont(family.split(",")[0].strip('"'), size)
        if weight == "Semibold":
            f.setWeight(QFont.DemiBold)
        return f
