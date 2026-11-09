"""输出目录解析 — 日志、CSV 统一跟随设置里的“数据保存路径”。"""

import os
from pathlib import Path

from app.utils.config import load_config

DEFAULT_BASE = "~/Documents/AutoBench"


def output_base() -> Path:
    """返回数据保存根目录。

    兼容旧配置：如果保存路径仍以 unit-archive 结尾，取其父目录作为根目录。
    """
    raw = load_config().get("log_path") or DEFAULT_BASE
    path = Path(os.path.expanduser(str(raw)))
    if path.name.lower() == "unit-archive":
        path = path.parent
    return path


def archive_dir(create: bool = True) -> Path:
    path = output_base() / "unit-archive"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def csv_dir(create: bool = True) -> Path:
    path = output_base() / "Test_CSV"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path
