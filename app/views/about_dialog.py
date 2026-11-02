"""关于对话框 — 版本、简介、技术栈与项目链接。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.utils.constants import APP_NAME, APP_VERSION
from app.views.theme import Colors, FONT_FAMILY

REPO_URL = "https://github.com/Jiayu-zheng1/AutoBench"

DESCRIPTION = (
    "串口测试自动化工具：通过串口驱动待测设备（DUT），控制 34970A 数字万用表、"
    "IT6382 程控电源与 Relayboard 继电器板，按 CSV 配置的测试序列执行测量与判定，"
    "实时输出 Pass/Fail，生成报表，可选上报 SFC 系统。"
)

FACTS = [
    ("版本", APP_VERSION),
    ("技术栈", "PySide6 + qfluentwidgets / pyserial / pyvisa"),
    ("运行环境", "macOS 10.15+ / Python 3.12+"),
    ("测试模式", "单通道手动 · 插拔自动 · 多通道并行（1–8）"),
    ("开源许可", "Apache License 2.0"),
]


class AboutDialog(QDialog):
    """应用"关于"窗口。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"关于 {APP_NAME}")
        self.setModal(True)
        self.setFixedWidth(520)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 22)
        layout.setSpacing(0)

        title = QLabel(APP_NAME)
        title.setStyleSheet(
            f"font-family: {FONT_FAMILY}; font-size: 26px; font-weight: 600;"
            f" color: {Colors.TEXT_PRIMARY};"
        )
        layout.addWidget(title)

        subtitle = QLabel("串口测试自动化工具")
        subtitle.setStyleSheet(
            f"font-family: {FONT_FAMILY}; font-size: 13px;"
            f" color: {Colors.TEXT_SECONDARY};"
        )
        layout.addWidget(subtitle)
        layout.addSpacing(16)

        desc = QLabel(DESCRIPTION)
        desc.setWordWrap(True)
        desc.setTextInteractionFlags(Qt.TextSelectableByMouse)
        desc.setStyleSheet(
            f"font-family: {FONT_FAMILY}; font-size: 13px; line-height: 150%;"
            f" color: {Colors.TEXT_PRIMARY};"
        )
        layout.addWidget(desc)
        layout.addSpacing(18)

        layout.addWidget(self._separator())
        layout.addSpacing(14)

        for key, value in FACTS:
            layout.addLayout(self._fact_row(key, value))

        layout.addSpacing(10)
        layout.addWidget(self._separator())
        layout.addSpacing(14)

        link_row = QHBoxLayout()
        link_row.setSpacing(8)
        link_label = QLabel("项目地址")
        link_label.setStyleSheet(
            f"font-family: {FONT_FAMILY}; font-size: 12px; color: {Colors.TEXT_SECONDARY};"
        )
        link_label.setFixedWidth(76)
        link = QLabel(f'<a href="{REPO_URL}" style="color: {Colors.PRIMARY};">{REPO_URL}</a>')
        link.setOpenExternalLinks(True)
        link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        link.setStyleSheet(f"font-family: {FONT_FAMILY}; font-size: 12px;")
        link_row.addWidget(link_label)
        link_row.addWidget(link, 1)
        layout.addLayout(link_row)

        copyright_label = QLabel(f"Copyright © 2026 {APP_NAME} Contributors")
        copyright_label.setStyleSheet(
            f"font-family: {FONT_FAMILY}; font-size: 11px; color: {Colors.TEXT_TERTIARY};"
        )
        layout.addSpacing(6)
        layout.addWidget(copyright_label)

        layout.addSpacing(18)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        ok_button = QPushButton("确定")
        ok_button.setDefault(True)
        ok_button.setFixedWidth(88)
        ok_button.clicked.connect(self.accept)
        button_row.addWidget(ok_button)
        layout.addLayout(button_row)

    def _separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {Colors.SEPARATOR}; border: none;")
        return line

    def _fact_row(self, key: str, value: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.setContentsMargins(0, 2, 0, 2)

        key_label = QLabel(key)
        key_label.setFixedWidth(76)
        key_label.setStyleSheet(
            f"font-family: {FONT_FAMILY}; font-size: 12px; color: {Colors.TEXT_SECONDARY};"
        )
        value_label = QLabel(value)
        value_label.setWordWrap(True)
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        value_label.setStyleSheet(
            f"font-family: {FONT_FAMILY}; font-size: 12px; color: {Colors.TEXT_PRIMARY};"
        )

        row.addWidget(key_label)
        row.addWidget(value_label, 1)
        return row
