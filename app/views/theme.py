"""HIG-compliant macOS theme: colors, fonts, metrics & QSS stylesheet.

支持 Light / Dark Mode 自适应，通过 macOS 系统偏好检测。
"""

import subprocess

# ── 系统外观检测 ──────────────────────────────────────────────────────


def _is_dark_mode() -> bool:
    """检测 macOS 系统是否为 Dark Mode。"""
    try:
        result = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and "Dark" in result.stdout
    except Exception:
        return False


def _accent_color() -> str:
    """获取 macOS 系统强调色 (fallback: 标准蓝)。"""
    try:
        result = subprocess.run(
            ["defaults", "read", "-g", "AppleAccentColor"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            idx = result.stdout.strip()
            accent_map = {
                "0": "#FF3B30",
                "1": "#FF9500",
                "2": "#FFCC00",
                "3": "#34C759",
                "4": "#007AFF",
                "5": "#AF52DE",
                "6": "#FF6482",
            }
            return accent_map.get(idx, "#007AFF")
    except Exception:
        pass
    return "#007AFF"


# ── HIG Color Palette ──────────────────────────────────────────────────


class _LightColors:
    WINDOW_BG = "#F5F5F7"
    CONTROL_BG = "#FFFFFF"
    GROUP_BG = "#FFFFFF"
    SIDEBAR_BG = "#ECECF0"
    SUCCESS = "#34C759"
    SUCCESS_BG = "#D4F5DD"
    DANGER = "#FF3B30"
    DANGER_BG = "#FFD6D4"
    WARNING = "#FF9500"
    WARNING_BG = "#FFE8C0"
    RUNNING = "#149392"
    RUNNING_BG = "#C8EDEC"
    TEXT_PRIMARY = "#1D1D1F"
    TEXT_SECONDARY = "#86868B"
    TEXT_TERTIARY = "#AEAEB2"
    TEXT_PLACEHOLDER = "#C7C7CC"
    SEPARATOR = "#D1D1D6"
    BORDER = "#C7C7CC"
    LOG_BG = "#FFFFFF"
    LOG_TEXT = "#1D1D1F"
    LOG_TIMESTAMP = "#007AFF"
    LOG_LEVEL_INFO = "#34C759"
    LOG_LEVEL_DEBUG = "#AF52DE"
    LOG_LEVEL_WARNING = "#FF9500"
    LOG_LEVEL_ERROR = "#FF3B30"


class _DarkColors:
    WINDOW_BG = "#1E1E20"
    CONTROL_BG = "#2C2C2E"
    GROUP_BG = "#2C2C2E"
    SIDEBAR_BG = "#252527"
    SUCCESS = "#30D158"
    SUCCESS_BG = "#1A3A2A"
    DANGER = "#FF453A"
    DANGER_BG = "#3A1A1A"
    WARNING = "#FF9F0A"
    WARNING_BG = "#3A2A0A"
    RUNNING = "#5EE6D0"
    RUNNING_BG = "#0A2A2A"
    TEXT_PRIMARY = "#F5F5F7"
    TEXT_SECONDARY = "#98989D"
    TEXT_TERTIARY = "#636366"
    TEXT_PLACEHOLDER = "#636366"
    SEPARATOR = "#3A3A3C"
    BORDER = "#48484A"
    LOG_BG = "#2C2C2E"
    LOG_TEXT = "#F5F5F7"
    LOG_TIMESTAMP = "#64D2FF"
    LOG_LEVEL_INFO = "#30D158"
    LOG_LEVEL_DEBUG = "#BF5AF2"
    LOG_LEVEL_WARNING = "#FF9F0A"
    LOG_LEVEL_ERROR = "#FF453A"


def _resolve():
    # 锁定浅色主题，不随系统 Dark Mode 变化
    base = _LightColors
    base.PRIMARY = "#007AFF"
    base.PRIMARY_HOVER = _darken(base.PRIMARY, 0.15)
    return base


def _darken(hex_color: str, factor: float) -> str:
    """将十六进制颜色按比例加深。"""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = max(0, int(r * (1 - factor)))
    g = max(0, int(g * (1 - factor)))
    b = max(0, int(b * (1 - factor)))
    return f"#{r:02X}{g:02X}{b:02X}"


Colors = _resolve()

# ── HIG Typography ──────────────────────────────────────────────────────
# SF Pro / SF Mono — macOS system font stack

FONT_FAMILY = '"Helvetica Neue", sans-serif'
FONT_MONO = '"Menlo", "SF Mono", "Monaco", monospace'

FONT_LARGE_TITLE = (FONT_FAMILY, 24, "Semibold")
FONT_TITLE_2 = (FONT_FAMILY, 20, "Semibold")
FONT_TITLE_3 = (FONT_FAMILY, 18, "Semibold")
FONT_BODY = (FONT_FAMILY, 13, "Regular")
FONT_CALLOUT = (FONT_FAMILY, 13, "Regular")
FONT_CAPTION_1 = (FONT_FAMILY, 12, "Regular")
FONT_CAPTION_2 = (FONT_FAMILY, 11, "Regular")
FONT_MONOSPACE = (FONT_MONO, 12, "Regular")

# ── HIG Metrics ─────────────────────────────────────────────────────────
WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 768
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 640
MARGIN = 20
SECTION_GAP = 16
ELEMENT_GAP = 8
BUTTON_HEIGHT = 28
INPUT_HEIGHT = 24
BORDER_RADIUS = 6
TOOLBAR_HEIGHT = 44
STATUS_CARD_RADIUS = 8
TABLE_ROW_HEIGHT = 32

# ── QSS Stylesheet — Global ─────────────────────────────────────────────


def stylesheet() -> str:
    return f"""
    /* ── Global ── */
    QMainWindow {{
        background-color: {Colors.WINDOW_BG};
    }}

    QWidget {{
        font-family: {FONT_FAMILY};
        font-size: 13px;
        color: {Colors.TEXT_PRIMARY};
    }}

    /* ── Menu Bar ── */
    QMenuBar {{
        background-color: {Colors.WINDOW_BG};
        color: {Colors.TEXT_PRIMARY};
        border-bottom: 1px solid {Colors.SEPARATOR};
        padding: 2px 8px;
        font-size: 13px;
    }}

    QMenuBar::item {{
        padding: 4px 10px;
        border-radius: 4px;
    }}

    QMenuBar::item:selected {{
        background-color: {Colors.CONTROL_BG};
    }}

    QMenu {{
        background-color: {Colors.CONTROL_BG};
        border: 1px solid {Colors.SEPARATOR};
        border-radius: 6px;
        padding: 4px;
    }}

    QMenu::item {{
        padding: 4px 24px 4px 12px;
        border-radius: 4px;
    }}

    QMenu::item:selected {{
        background-color: {Colors.PRIMARY};
        color: white;
    }}

    QMenu::separator {{
        height: 1px;
        background: {Colors.SEPARATOR};
        margin: 4px 8px;
    }}

    /* ── Buttons ── */
    QPushButton {{
        background-color: {Colors.PRIMARY};
        color: white;
        border: none;
        border-radius: {BORDER_RADIUS}px;
        padding: 4px 16px;
        font-size: 13px;
        font-weight: 500;
        min-height: {BUTTON_HEIGHT}px;
    }}

    QPushButton:hover {{
        background-color: {Colors.PRIMARY_HOVER};
    }}

    QPushButton:pressed {{
        background-color: {_darken(Colors.PRIMARY, 0.3)};
    }}

    QPushButton:disabled {{
        background-color: {Colors.TEXT_TERTIARY};
        color: {Colors.WINDOW_BG};
    }}

    /* ── Line Edit ── */
    QLineEdit {{
        background-color: {Colors.CONTROL_BG};
        border: 1px solid {Colors.BORDER};
        border-radius: 5px;
        padding: 3px 8px;
        font-size: 13px;
        color: {Colors.TEXT_PRIMARY};
        min-height: {INPUT_HEIGHT}px;
        selection-background-color: {Colors.PRIMARY};
        selection-color: white;
    }}

    QLineEdit:focus {{
        border: 2px solid {Colors.PRIMARY};
        padding: 2px 7px;
    }}

    QLineEdit:disabled {{
        background-color: {Colors.WINDOW_BG};
        color: {Colors.TEXT_TERTIARY};
    }}

    /* ── Combo Box ── */
    QComboBox {{
        background-color: {Colors.CONTROL_BG};
        border: 1px solid {Colors.BORDER};
        border-radius: 5px;
        padding: 3px 8px;
        font-size: 13px;
        color: {Colors.TEXT_PRIMARY};
        min-height: {INPUT_HEIGHT}px;
    }}

    QComboBox:focus {{
        border: 2px solid {Colors.PRIMARY};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {Colors.CONTROL_BG};
        border: 1px solid {Colors.SEPARATOR};
        border-radius: 4px;
        selection-background-color: {Colors.PRIMARY};
        selection-color: white;
    }}

    /* ── Group Box ── */
    QGroupBox {{
        background-color: {Colors.GROUP_BG};
        border: 1px solid {Colors.SEPARATOR};
        border-radius: {BORDER_RADIUS}px;
        margin-top: 12px;
        padding: 16px 16px 12px 16px;
        font-size: 12px;
        font-weight: 600;
        color: {Colors.TEXT_SECONDARY};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 6px;
        background-color: {Colors.GROUP_BG};
    }}

    /* ── Table ── */
    QTableWidget {{
        background-color: {Colors.CONTROL_BG};
        border: 1px solid {Colors.SEPARATOR};
        border-radius: {BORDER_RADIUS}px;
        gridline-color: {Colors.SEPARATOR};
        font-size: 13px;
        selection-background-color: {Colors.PRIMARY};
        selection-color: white;
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

    /* ── Text Edit ── */
    QTextEdit {{
        background-color: {Colors.CONTROL_BG};
        border: 1px solid {Colors.SEPARATOR};
        border-radius: {BORDER_RADIUS}px;
        padding: 8px;
        font-size: 13px;
        color: {Colors.TEXT_PRIMARY};
        selection-background-color: {Colors.PRIMARY};
        selection-color: white;
    }}

    /* ── Splitter ── */
    QSplitter::handle {{
        background-color: {Colors.SEPARATOR};
        width: 1px;
    }}

    /* ── Status Bar ── */
    QStatusBar {{
        background-color: {Colors.CONTROL_BG};
        border-top: 1px solid {Colors.SEPARATOR};
        color: {Colors.TEXT_SECONDARY};
        font-size: 12px;
        padding: 2px {MARGIN}px;
    }}

    /* ── Scrollbar ── */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background: {Colors.TEXT_TERTIARY};
        border-radius: 4px;
        min-height: 30px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {Colors.TEXT_SECONDARY};
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
    }}

    QScrollBar::handle:horizontal {{
        background: {Colors.TEXT_TERTIARY};
        border-radius: 4px;
        min-width: 30px;
    }}

    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    """
