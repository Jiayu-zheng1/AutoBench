"""PySide6 动画工具 — 脉冲、淡入淡出、行闪烁。"""
from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from app.views.theme import Colors


def start_pulse(widget: QWidget, min_opacity: float = 0.55, duration: int = 900):
    """在 widget 上启动无限脉冲动画（呼吸灯效果）。"""
    stop_pulse(widget)
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(1.0)
    widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration)
    anim.setStartValue(1.0)
    anim.setEndValue(min_opacity)
    anim.setEasingCurve(QEasingCurve.InOutSine)
    anim.setLoopCount(-1)  # 无限循环
    anim.start()

    widget._pulse_anim = anim
    widget._pulse_effect = effect


def stop_pulse(widget: QWidget):
    """停止脉冲动画，恢复原始 opacity。"""
    anim = getattr(widget, "_pulse_anim", None)
    if anim:
        anim.stop()
        widget._pulse_anim = None
    effect = getattr(widget, "_pulse_effect", None)
    if effect:
        effect.setOpacity(1.0)


def fade_in(widget: QWidget, duration: int = 350):
    """淡入动画 — widget 从透明到不透明。"""
    stop_pulse(widget)
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start()

    widget._fade_anim = anim
    widget._fade_effect = effect


def fade_out(widget: QWidget, duration: int = 250):
    """淡出动画 — widget 从不透明到透明。"""
    effect = getattr(widget, "_fade_effect", None)
    if effect is None:
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(1.0)
        widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.InCubic)
    anim.start()

    widget._fade_anim = anim
    widget._fade_effect = effect


def flash_table_row(items: list, flash_color: str = "#A8E6CF", duration: int = 700):
    """整行短暂背景变色 — setCellWidget 完全绕过 stylesheet，带 border-bottom 消缝。"""
    if not items:
        return
    first = items[0]
    if first is None:
        return
    table = first.tableWidget()
    if table is None:
        return

    from PySide6.QtWidgets import QLabel, QTableWidgetItem

    row = first.row()
    snapshots = []
    for item in items:
        if item is None:
            snapshots.append(None)
            continue
        col = item.column()
        snap = {
            "col": col,
            "text": item.text(),
            "font": item.font(),
            "align": int(item.textAlignment()),
            "fg": item.foreground(),
            "bg": item.background(),
        }
        snapshots.append(snap)

        label = QLabel(snap["text"])
        label.setFont(snap["font"])
        label.setAlignment(Qt.AlignmentFlag(snap["align"]))
        label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        # border-bottom 匹配 QTableWidget::item 样式，消除列间视觉缝隙
        label.setStyleSheet(
            f"background-color: {flash_color}; color: {Colors.TEXT_PRIMARY}; "
            f"padding: 5px 12px; border-bottom: 1px solid {Colors.SEPARATOR};"
        )
        table.setCellWidget(row, col, label)

    def cleanup():
        for snap in snapshots:
            if snap is None:
                continue
            table.removeCellWidget(row, snap["col"])
            new_item = QTableWidgetItem(snap["text"])
            new_item.setFont(snap["font"])
            new_item.setTextAlignment(snap["align"])
            new_item.setForeground(snap["fg"])
            new_item.setBackground(snap["bg"])
            table.setItem(row, snap["col"], new_item)

    QTimer.singleShot(duration, cleanup)
