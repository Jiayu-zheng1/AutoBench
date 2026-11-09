"""精简 Logger — 非测试期间仅 stdout，测试期间按 SN→时间戳 写入 test.log。

目录结构:
    <设置中的数据保存路径>/unit-archive/
    ├── GVVG93V6JH/
    │   ├── 20260624_143000/
    │   │   ├── test.log
    │   │   └── records.csv
    │   └── 20260624_150000/
    │       ├── test.log
    │       └── records.csv
    └── ...

用法:
    from app.utils.logger import get_logger
    logger = get_logger("DUT")
    logger.info("消息")
"""

import sys
import threading
import time
from pathlib import Path

from loguru import logger as _logger

from app.utils.paths import archive_dir

# ═══════════════════════════════════════════════════════════════════════════
#  全局状态
# ═══════════════════════════════════════════════════════════════════════════

_initialized = False
_init_lock = threading.Lock()

# 多线程安全: 每个 runner 独立持有 handler_id，不再用全局变量
_handlers_lock = threading.Lock()
_active_handlers: dict[int, Path] = {}  # handler_id → unit_dir（调试用）


# ═══════════════════════════════════════════════════════════════════════════
#  初始化（全局一次，仅 stdout）
# ═══════════════════════════════════════════════════════════════════════════

def _init_once():
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        _logger.remove()
        _logger.add(
            sys.stdout,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SS}</green> | "
                "<level>{level:<5}</level> | "
                "<cyan>{extra[module]}</cyan> | "
                "{message}"
            ),
            level="INFO",
            colorize=True,
        )
        _initialized = True


# ═══════════════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════════════

def get_logger(module_name: str):
    """返回绑定模块名的 logger — 非测试期间仅 stdout，测试期间同时写入 SN 的 test.log。"""
    _init_once()
    return _logger.bind(module=module_name)


# ═══════════════════════════════════════════════════════════════════════════
#  单pcs 日志归档 — 每 SN 一个文件夹，多线程安全
# ═══════════════════════════════════════════════════════════════════════════

def make_unit_folder(scan_sn: str = "", fgsn: str = "", mlbsn: str = "") -> Path:
    """创建单pcs测试的日志文件夹 — SN/{时间戳}/。

    目录结构: unit-archive/{SN}/{YYYYMMDD_HHMMSS}/
    同一 SN 多次测试: 每次新建一个时间戳子文件夹。

    Returns:
        创建的时间戳文件夹 Path
    """
    sn = scan_sn or fgsn or mlbsn or time.strftime("%Y%m%d_%H%M%S")
    ts = time.strftime("%Y%m%d_%H%M%S")
    unit_dir = archive_dir() / sn / ts
    unit_dir.mkdir(parents=True, exist_ok=True)
    return unit_dir


def begin_unit_log(unit_dir: Path) -> int:
    """为单次测试开启独立日志文件 — 返回 handler_id，调用方负责保存并传入 end_unit_log。

    多线程安全: 每个 runner 独立持有 handler_id，互不干扰。
    """
    _init_once()
    handler_id = _logger.add(
        unit_dir / "test.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<5} | {extra[module]} | {message}",
        level="DEBUG",
        encoding="utf-8",
        enqueue=True,  # 多线程安全：每个 handler 独立队列，避免并发阻塞
    )
    with _handlers_lock:
        _active_handlers[handler_id] = unit_dir
    return handler_id


def end_unit_log(handler_id: int):
    """结束单元日志 — 按 handler_id 精确移除，不影响其他线程的 handler。"""
    try:
        _logger.remove(handler_id)
    except Exception:
        pass
    with _handlers_lock:
        _active_handlers.pop(handler_id, None)
