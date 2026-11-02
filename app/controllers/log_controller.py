"""日志控制器 — 桥接 loguru 到 Qt UI + 兼容旧接口。

> 模块化日志由 app/utils/logger.py 统一管理。
> LogController 只负责 Qt 信号桥接和 TestRunner 兼容接口。
"""

from loguru import logger as _raw_logger  # raw loguru 实例，用于 add handler
from PySide6.QtCore import QObject, Signal

from app.utils.logger import get_logger

logger = get_logger("LogController")


# ═══════════════════════════════════════════════════════════════════════════
#  Qt 信号桥接器
# ═══════════════════════════════════════════════════════════════════════════

class LogHandler(QObject):
    _signal = Signal(str)

    def __init__(self):
        super().__init__()

    def write(self, message):
        self._signal.emit(message.strip())

    def flush(self):
        pass


# ═══════════════════════════════════════════════════════════════════════════
#  控制器
# ═══════════════════════════════════════════════════════════════════════════

class LogController:
    """Qt 信号桥接 + 兼容旧接口。"""

    UI_FMT = "{time:YYYY-MM-DD HH:mm:ss.SS} | {level:<5} | {extra[module]} | {message}"

    def __init__(self, log_path: str = ""):
        self._handler: LogHandler | None = None

    def initialize(self):
        """初始化 — 触发 loguru stdout handler 配置。"""
        get_logger("LogController")

    def _path_logger(self):
        """兼容旧接口 — 不再按模块分文件。"""

    def rename_log(self, sn: str = ""):
        """兼容旧接口 — 不再按测试轮转日志。"""

    def bind_signal(self, log_slot):
        """将 loguru 输出桥接到 Qt slot（UI LogPanel）。"""
        self._handler = LogHandler()
        self._handler._signal.connect(log_slot)
        _raw_logger.add(self._handler, format=self.UI_FMT, level="INFO")
