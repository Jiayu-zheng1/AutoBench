"""Test results table — 列从 CSV 表头动态生成。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

from app.models.test_plan import TestStep
from app.views.theme import FONT_FAMILY, TABLE_ROW_HEIGHT, Colors

# ── 表格显示的列与 CSV 表头一致，以下是默认列宽映射 ──
_DEFAULT_COL_WIDTHS = {
    "TestName": 160,
    "Function": 0,  # 内部列，不显示（隐藏）
    "SubTestName": 250,
    "LowerLimit": 100,
    "Value": 350,
    "UpperLimit": 100,
    "Unit": 60,
    "Result": 80,
}


class TestTable(QTableWidget):
    """测试结果表格 — 列顺序和名称从 CSV 表头动态确定。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._auto_scroll = True
        self._headers: list[str] = []  # 显示的列名（不含隐藏列）
        self._col_map: dict[str, int] = {}  # 列名 → 列索引
        self._last_match: dict[str, int] = {}  # SubTestName → 上次匹配行号
        self._current_row: int = -1              # 当前测试行号 (set_value 记录, set_result/color 复用)
        self._setup()

    def _setup(self):
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.setFocusPolicy(Qt.NoFocus)

        header = self.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)

        font = QFont(FONT_FAMILY.split(",")[0].strip('"'), 13)
        self.setFont(font)

        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Colors.CONTROL_BG};
                border: 1px solid {Colors.SEPARATOR};
                border-radius: 6px;
                gridline-color: {Colors.SEPARATOR};
                font-size: 13px;
                selection-background-color: #B3D9FF;
                selection-color: {Colors.TEXT_PRIMARY};
            }}
            QTableWidget::item {{
                padding: 5px 12px;
                border-bottom: 1px solid {Colors.SEPARATOR};
            }}
            QHeaderView::section {{
                background-color: {Colors.CONTROL_BG};
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                padding: 6px 12px;
                border: none;
                border-bottom: 2px solid {Colors.SEPARATOR};
            }}
        """)

    # ── 公共接口 ──────────────────────────────────────────────────────────

    def load_config(self, csv_rows: list[TestStep], headers: list[str] = None):
        """从 TestStep 列表填充表格，列由 headers 决定（排除隐藏列 Function）。

        headers 不传时回退到旧版固定列逻辑。
        """
        self.setRowCount(0)
        self._last_match.clear()
        if not csv_rows:
            return

        # ── 确定显示列 ──
        if headers is None:
            headers = list(_DEFAULT_COL_WIDTHS.keys())
        # 排除内部／隐藏列
        hidden = {"Function"}
        self._headers = [h for h in headers if h not in hidden]
        self._col_map = {name: i for i, name in enumerate(self._headers)}

        self.setColumnCount(len(self._headers))
        self.setHorizontalHeaderLabels(self._headers)

        for i, name in enumerate(self._headers):
            w = _DEFAULT_COL_WIDTHS.get(name, 100)
            if w > 0:
                self.setColumnWidth(i, w)

        for row in csv_rows:
            if row.get("Running", "") != "Y":
                continue
            r = self.rowCount()
            self.insertRow(r)
            self.setRowHeight(r, TABLE_ROW_HEIGHT)
            visible = row.get("Visible", "Y") == "Y"  # Y→UI显示limits, N→后台静默
            for name in self._headers:
                col = self._col_map[name]
                # 当 Visible=N 时，LowerLimit / UpperLimit 不显示（Unit 始终显示）
                if name in ("LowerLimit", "UpperLimit") and not visible:
                    self.setItem(r, col, self._cell(""))
                else:
                    self.setItem(r, col, self._cell(row.get(name, "")))

    def clear_results(self):
        self._last_match.clear()
        for r in range(self.rowCount()):
            for name in ("Value", "Result"):
                col = self._col_map.get(name)
                if col is not None:
                    self.setItem(r, col, self._cell(""))

    def set_value(self, sub_test_name: str, value: str):
        """按 SubTestName + _last_match 定位行，记录到 _current_row 供 set_result/color 复用。"""
        col_item = self._col_map.get("SubTestName")
        col_val = self._col_map.get("Value")
        if col_item is None or col_val is None:
            return
        start = self._last_match.get(sub_test_name, 0)
        for r in range(start, self.rowCount()):
            item = self.item(r, col_item)
            if item and item.text() == sub_test_name:
                self._last_match[sub_test_name] = r + 1
                self._current_row = r
                self.setItem(r, col_val, self._cell(value))
                if self._auto_scroll:
                    self.scrollToItem(item, QAbstractItemView.PositionAtCenter)
                return

    def set_result(self, sub_test_name: str, result: str):
        """复用 _current_row，直接更新 Result 列。"""
        self._update_current_row("Result", result)

    def set_result_color(self, sub_test_name: str, result: str):
        """复用 _current_row，给 Result 单元格上色。"""
        if self._current_row < 0:
            return
        col_result = self._col_map.get("Result")
        if col_result is None:
            return
        result_item = self.item(self._current_row, col_result)
        if result_item:
            if result == "Pass":
                result_item.setBackground(QBrush(QColor(Colors.SUCCESS_BG)))
                result_item.setForeground(QBrush(QColor(Colors.SUCCESS)))
            else:
                result_item.setBackground(QBrush(QColor(Colors.DANGER_BG)))
                result_item.setForeground(QBrush(QColor(Colors.DANGER)))

    def _update_current_row(self, col_name: str, value: str):
        if self._current_row < 0:
            return
        col = self._col_map.get(col_name)
        if col is not None:
            self.setItem(self._current_row, col, self._cell(value))

    def set_auto_scroll(self, enabled: bool):
        self._auto_scroll = enabled

    def _cell(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return item
