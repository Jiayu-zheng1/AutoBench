"""HIG-styled control bar — SN input, Start button, timer, instrument gear, 仪器状态。"""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from app.views.animations import start_pulse, stop_pulse
from app.views.theme import (
    BORDER_RADIUS,
    BUTTON_HEIGHT,
    ELEMENT_GAP,
    FONT_BODY,
    FONT_TITLE_2,
    INPUT_HEIGHT,
    MARGIN,
    Colors,
)

STATUS_LABELS = {"34970A": "34970A", "IT6382": "IT6382", "Relayboard": "Relay"}


class ControlBar(QWidget):
    """Top control area with SN input, Start button, and elapsed timer."""

    signal_gear_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._elapsed = 0.0
        self._timer = QTimer()
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self._status_labels: dict[str, tuple[QLabel, QLabel]] = {}
        self._auto_mode = False
        self._setup()

    def _setup(self):
        self.setFixedHeight(56)
        self.setStyleSheet(f"""
            ControlBar {{
                background-color: {Colors.CONTROL_BG};
                border-bottom: 1px solid {Colors.SEPARATOR};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(MARGIN, 8, MARGIN, 8)
        layout.setSpacing(ELEMENT_GAP)

        # ── 仪器状态圆点 ──
        for name, label in STATUS_LABELS.items():
            dot = QLabel("●")
            dot.setFixedWidth(18)
            dot.setAlignment(Qt.AlignCenter)
            dot.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 12px;")
            layout.addWidget(dot)

            lbl = QLabel(label)
            lbl.setFont(self._font(*FONT_BODY))
            lbl.setStyleSheet(f"color: {Colors.TEXT_TERTIARY};")
            layout.addWidget(lbl)

            self._status_labels[name] = (dot, lbl)

        # DUT 状态灯
        self.dut_dot = QLabel("●")
        self.dut_dot.setFixedWidth(18)
        self.dut_dot.setAlignment(Qt.AlignCenter)
        self.dut_dot.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 12px;")
        self.dut_dot.setToolTip("DUT 状态")
        layout.addWidget(self.dut_dot)

        self.dut_label = QLabel("DUT")
        self.dut_label.setFont(self._font(*FONT_BODY))
        self.dut_label.setStyleSheet(f"color: {Colors.TEXT_TERTIARY};")
        layout.addWidget(self.dut_label)

        layout.addSpacing(12)
        layout.addStretch()

        # SN Label
        sn_label = QLabel("SN:")
        sn_label.setFont(self._font(*FONT_BODY))
        layout.addWidget(sn_label)

        # SN Input
        self.sn_input = QLineEdit()
        self.sn_input.setPlaceholderText("Scan Serial Number")
        self.sn_input.setFixedWidth(200)
        self.sn_input.setFixedHeight(INPUT_HEIGHT + 4)
        self.sn_input.setFont(self._font(*FONT_BODY))
        self.sn_input.setStyleSheet(f"""
            QLineEdit {{
                border: 1.5px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 4px 12px;
                background: {Colors.WINDOW_BG};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 2px solid {Colors.PRIMARY};
                padding: 3px 11px;
            }}
        """)
        layout.addWidget(self.sn_input)

        # Start Button
        self.start_btn = QPushButton("Start")
        self.start_btn.setFixedHeight(BUTTON_HEIGHT + 2)
        self.start_btn.setFont(self._font(*FONT_BODY))
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 24px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Colors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: #0051AA;
            }}
            QPushButton:disabled {{
                background-color: {Colors.TEXT_TERTIARY};
                color: #F5F5F7;
            }}
        """)
        layout.addWidget(self.start_btn)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet(f"color: {Colors.SEPARATOR};")
        layout.addWidget(sep)

        # Timer
        timer_label = QLabel("Time:")
        timer_label.setFont(self._font(*FONT_BODY))
        layout.addWidget(timer_label)

        self.time_display = QLabel("00:00")
        self.time_display.setFont(self._font(*FONT_TITLE_2))
        self.time_display.setMinimumWidth(70)
        self.time_display.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.time_display)

        # Gear button
        self.gear_btn = QPushButton("⚙")
        self.gear_btn.setFixedSize(36, 36)
        self.gear_btn.setFont(self._font(*FONT_BODY))
        self.gear_btn.setCursor(Qt.PointingHandCursor)
        self.gear_btn.setToolTip("仪器设置")
        self.gear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER};
                border-radius: {BORDER_RADIUS}px;
                font-size: 18px;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: {Colors.WINDOW_BG};
                color: {Colors.PRIMARY};
                border-color: {Colors.PRIMARY};
            }}
        """)
        self.gear_btn.clicked.connect(self.signal_gear_clicked.emit)
        layout.addWidget(self.gear_btn)

    def set_device_status(self, device_name: str, connected: bool, detail: str):
        pair = self._status_labels.get(device_name)
        if not pair:
            return
        dot, lbl = pair
        if connected:
            dot.setStyleSheet(f"color: {Colors.SUCCESS}; font-size: 14px;")
            lbl.setStyleSheet(f"color: {Colors.SUCCESS}; font-weight: 600;")
        else:
            dot.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 14px;")
            lbl.setStyleSheet(f"color: {Colors.TEXT_TERTIARY};")

    def set_auto_mode(self, auto: bool):
        """切换自动/手动模式（由设置页驱动）。"""
        self._auto_mode = auto
        if auto:
            self.sn_input.setEnabled(False)
            self.sn_input.setPlaceholderText("自动测试模式…")
            self.start_btn.setEnabled(False)
        else:
            self.sn_input.setEnabled(True)
            self.sn_input.setPlaceholderText("Scan Serial Number")
            self.start_btn.setEnabled(True)

    def set_dut_status(self, connected: bool):
        """更新 DUT 连接状态圆点。"""
        if connected:
            self.dut_dot.setStyleSheet(f"color: {Colors.SUCCESS}; font-size: 14px;")
            self.dut_label.setStyleSheet(f"color: {Colors.SUCCESS}; font-weight: 600;")
            start_pulse(self.dut_dot, min_opacity=0.5, duration=800)
        else:
            stop_pulse(self.dut_dot)
            self.dut_dot.setStyleSheet(
                f"color: {Colors.TEXT_TERTIARY}; font-size: 12px;"
            )
            self.dut_label.setStyleSheet(f"color: {Colors.TEXT_TERTIARY};")

    def is_auto_mode(self) -> bool:
        return self._auto_mode

    def _tick(self):
        self._elapsed += 0.1
        total_s = int(self._elapsed)
        frac = int((self._elapsed - total_s) * 1000)
        self.time_display.setText(f"{total_s // 60:02d}:{total_s % 60:02d}.{frac:03d}")

    def start_timer(self):
        self._elapsed = 0.0
        self._timer.start()

    def stop_timer(self):
        self._timer.stop()

    def set_running(self, running: bool):
        self.sn_input.setEnabled(not running and not self._auto_mode)
        self.start_btn.setEnabled(not running and not self._auto_mode)
        if running:
            self.start_btn.setText("Running…")
            start_pulse(self.time_display, min_opacity=0.5, duration=1000)
        else:
            self.start_btn.setText("Start")
            stop_pulse(self.time_display)

    def _font(self, family: str, size: int, weight: str):
        f = QFont(family.split(",")[0].strip('"'), size)
        if weight == "Semibold":
            f.setWeight(QFont.DemiBold)
        return f
