"""统一系统配置 — 单一入口读写 ~/Documents/AutoBench/system_config.json。

配置按运行平台分为 macOS / Windows 两套 profile：
    {
      "platform_mode": "macos",
      "profiles": {
        "macos": { ...扁平配置... },
        "windows": { ...扁平配置... }
      }
    }

旧版扁平配置会自动迁移到当前平台 profile。
"""

import json
import os
import shutil
import sys

from app.utils.constants import CHANNEL_CONFIG_PATH, CONFIG_DIR

SYSTEM_CONFIG_PATH = os.path.join(CONFIG_DIR, "system_config.json")
LEGACY_CONFIG_DIR = os.path.expanduser("~/Documents/AutoBench")
_legacy_migrated = False


def _migrate_legacy_config():
    """Windows 首次升级时，把旧 Documents 配置复制到 AppData。"""
    global _legacy_migrated
    if _legacy_migrated or not sys.platform.startswith("win"):
        return
    _legacy_migrated = True
    if os.path.abspath(LEGACY_CONFIG_DIR) == os.path.abspath(CONFIG_DIR):
        return
    if not os.path.isdir(LEGACY_CONFIG_DIR):
        return
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        for name in ("system_config.json", "instrument_config.json", "channel_config.json"):
            src = os.path.join(LEGACY_CONFIG_DIR, name)
            dst = os.path.join(CONFIG_DIR, name)
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.copy2(src, dst)
    except Exception:
        pass

PLATFORM_MACOS = "macos"
PLATFORM_WINDOWS = "windows"
PLATFORM_MODES = (PLATFORM_MACOS, PLATFORM_WINDOWS)

DEFAULTS = {
    "log_retention_days": 90,
    "log_path": "~/Documents/AutoBench",  # 数据根目录：日志/CSV 子目录在此之下
    "dut_baud_rate": 921600,
    "dut_location_id": "",
    "dut_interface": "",  # Windows 复合设备接口，如 MI_02；空=任意
    "dut_vid": "",        # Windows DUT VID 过滤，如 290B
    "dut_pid": "",        # Windows DUT PID 过滤，如 092F
    "auto_test_mode": False,
    "auto_connect_instruments": True,   # 启动时自动检测连接仪器
    "fail_stop_test": True,
    "auto_scroll_log": True,
    "sfc_url": "",
    "sfc_online": False,
    "sfc_vip": "",
    # 多通道测试
    "multi_channel_mode": False,        # 是否启用多通道模式
    "channel_count": 4,                 # 通道数量 (1-8)
    "channel_location_ids": ["", "", "", ""],  # 每个通道的 DUT location ID
}


def _read_json(path: str) -> dict:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _write_json(path: str, data: dict):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def default_platform() -> str:
    return PLATFORM_WINDOWS if sys.platform.startswith("win") else PLATFORM_MACOS


def _normalize_mode(mode: str | None) -> str:
    return mode if mode in PLATFORM_MODES else default_platform()


def get_platform_mode() -> str:
    """返回当前运行平台模式（macos / windows）。"""
    _migrate_legacy_config()
    data = _read_json(SYSTEM_CONFIG_PATH)
    return _normalize_mode(data.get("platform_mode"))


def _system_profiles(data: dict) -> tuple[str, dict]:
    """解析系统配置，兼容旧版扁平结构。"""
    mode = _normalize_mode(data.get("platform_mode"))
    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        legacy = {
            key: value
            for key, value in data.items()
            if key not in ("profiles", "platform_mode")
        }
        profiles = {mode: legacy} if legacy else {}
    return mode, profiles


def _channel_profiles(data: dict, mode: str) -> dict:
    """解析多通道配置，兼容旧版扁平结构。"""
    profiles = data.get("profiles")
    if isinstance(profiles, dict):
        return profiles
    legacy = {
        key: value
        for key, value in data.items()
        if key not in ("profiles", "platform_mode")
    }
    return {mode: legacy} if legacy else {}


def _complete_profiles(profiles: dict, defaults: dict | None = None) -> dict:
    """保证两个平台 profile 都存在。"""
    result = {}
    for mode in PLATFORM_MODES:
        profile = profiles.get(mode)
        base = dict(defaults) if defaults else {}
        if isinstance(profile, dict):
            base.update(profile)
        result[mode] = base
    return result


def set_platform_mode(mode: str):
    """切换当前平台模式，保留两套 profile。"""
    _migrate_legacy_config()
    mode = _normalize_mode(mode)
    data = _read_json(SYSTEM_CONFIG_PATH)
    _, profiles = _system_profiles(data)
    _write_json(
        SYSTEM_CONFIG_PATH,
        {
            "platform_mode": mode,
            "profiles": _complete_profiles(profiles, DEFAULTS),
        },
    )


def load_config(platform: str | None = None) -> dict:
    """加载指定平台（默认当前平台）的系统配置，合并默认值。"""
    _migrate_legacy_config()
    data = _read_json(SYSTEM_CONFIG_PATH)
    current, profiles = _system_profiles(data)
    mode = _normalize_mode(platform or current)
    cfg = dict(DEFAULTS)
    cfg.update(profiles.get(mode, {}))
    return cfg


def save_config(cfg: dict, platform: str | None = None):
    """保存指定平台（默认当前平台）的系统配置，不动另一套 profile。"""
    _migrate_legacy_config()
    data = _read_json(SYSTEM_CONFIG_PATH)
    current, profiles = _system_profiles(data)
    mode = _normalize_mode(platform or current)
    profiles[mode] = dict(cfg)
    _write_json(
        SYSTEM_CONFIG_PATH,
        {
            "platform_mode": current,
            "profiles": _complete_profiles(profiles, DEFAULTS),
        },
    )


def load_channel_config(platform: str | None = None) -> dict:
    """加载指定平台（默认当前平台）的多通道配置。"""
    _migrate_legacy_config()
    data = _read_json(CHANNEL_CONFIG_PATH)
    mode = _normalize_mode(platform or get_platform_mode())
    profiles = _channel_profiles(data, mode)
    value = profiles.get(mode, {})
    return dict(value) if isinstance(value, dict) else {}


def save_channel_config(data: dict, platform: str | None = None):
    """保存指定平台（默认当前平台）的多通道配置，不动另一套 profile。"""
    _migrate_legacy_config()
    raw = _read_json(CHANNEL_CONFIG_PATH)
    mode = _normalize_mode(platform or get_platform_mode())
    profiles = _channel_profiles(raw, mode)
    profiles[mode] = dict(data)
    profiles.setdefault(PLATFORM_MACOS, {})
    profiles.setdefault(PLATFORM_WINDOWS, {})
    _write_json(CHANNEL_CONFIG_PATH, {"profiles": profiles})
