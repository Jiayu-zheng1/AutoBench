"""仪器管理器 — 单例模式，管理 34970A / IT6382 / Relayboard 的连接和状态。"""

import json
import os
import threading

from PySide6.QtCore import QObject, Signal

from app.utils.logger import get_logger

logger = get_logger("InstrumentManager")

from app.models.instruments.keysight_34970a import KEYSIGHT_34970A
from app.models.instruments.ps_it6382 import IT6382
from app.models.instruments.relay_board import RELAYBOARD
from app.utils.constants import INSTRUMENT_CONFIG_PATH

# ── 默认配置 ──────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "dmm_mode": "usb",                     # "usb" | "gpib"
    "dmm_port": "/dev/cu.usbserial-FTDH1RD8",  # 34970A USB 串口路径
    "dmm_gpib": "11",                       # 34970A GPIB 地址
    "ps_mode": "gpib",                      # "usb" | "gpib"
    "ps_port": "8",                         # IT6382 GPIB 地址
    "ps_usb_port": "",                      # IT6382 USB 串口路径
    "relay_port": "/dev/cu.usbserial-AL02P374",  # Relayboard 串口路径
    "relay_version": "0",
}

DEVICE_CHECK_TIMEOUT = 3  # 每台仪器检测超时 (秒)


class InstrumentManager(QObject):
    """仪器管理器单例。

    启动后台线程自动检测连接三台仪器，通过 Qt 信号通知 UI 状态变化。
    """

    # 单台仪器状态: (device_name, connected: bool, idn_or_error: str)
    signal_device_status = Signal(str, bool, str)
    # 全部仪器检测完成
    signal_all_checked = Signal()

    _instance = None

    @classmethod
    def instance(cls) -> "InstrumentManager":
        if cls._instance is None:
            cls._instance = InstrumentManager()
        return cls._instance

    def __init__(self, parent=None):
        if InstrumentManager._instance is not None:
            raise RuntimeError(
                "InstrumentManager is a singleton — use InstrumentManager.instance()"
            )
        super().__init__(parent)
        InstrumentManager._instance = self

        # 仪器实例
        self._dmm: KEYSIGHT_34970A | None = None
        self._ps: IT6382 | None = None
        self._relay: RELAYBOARD | None = None

        # 状态
        self._dmm_connected = False
        self._ps_connected = False
        self._relay_connected = False
        self._checking = False
        self._config = dict(DEFAULT_CONFIG)
        self._load_config()

    # ── 配置 ──────────────────────────────────────────────────────────

    @property
    def config(self) -> dict:
        return self._config

    def _load_config(self):
        """从 JSON 文件加载仪器配置，合并到当前配置中。"""
        try:
            if os.path.exists(INSTRUMENT_CONFIG_PATH):
                with open(INSTRUMENT_CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._config.update(saved)
                logger.info(f"仪器配置已从 {INSTRUMENT_CONFIG_PATH} 加载")
            else:
                logger.info("未找到仪器配置文件，使用默认配置")
        except Exception as e:
            logger.warning(f"加载仪器配置失败: {e}")

    def _save_config(self):
        """保存当前仪器配置到 JSON 文件。"""
        try:
            os.makedirs(os.path.dirname(INSTRUMENT_CONFIG_PATH), exist_ok=True)
            with open(INSTRUMENT_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info(f"仪器配置已保存到 {INSTRUMENT_CONFIG_PATH}")
        except Exception as e:
            logger.warning(f"保存仪器配置失败: {e}")

    def update_config(self, **kwargs):
        """更新仪器配置（端口、版本等）并自动持久化。"""
        for k, v in kwargs.items():
            if k in self._config:
                self._config[k] = v
        self._save_config()
        logger.info(f"InstrumentManager config updated: {self._config}")

    # ── 仪器访问 ──────────────────────────────────────────────────────

    @property
    def dmm(self) -> KEYSIGHT_34970A | None:
        return self._dmm if self._dmm_connected else None

    @property
    def ps(self) -> IT6382 | None:
        return self._ps if self._ps_connected else None

    @property
    def relay(self) -> RELAYBOARD | None:
        return self._relay if self._relay_connected else None

    @property
    def dmm_connected(self) -> bool:
        return self._dmm_connected

    @property
    def ps_connected(self) -> bool:
        return self._ps_connected

    @property
    def relay_connected(self) -> bool:
        return self._relay_connected

    @property
    def is_checking(self) -> bool:
        """后台线程是否正在检测仪器中。"""
        return self._checking

    @property
    def all_connected(self) -> bool:
        return self._dmm_connected and self._ps_connected and self._relay_connected

    # ── 自动检测（后台线程）────────────────────────────────────────────

    def start_auto_check(self):
        """启动后台线程自动检测连接所有仪器。"""
        if self._checking:
            return
        self._checking = True
        logger.info("InstrumentManager: 开始自动检测仪器...")
        thread = threading.Thread(target=self._auto_check_devices, daemon=True)
        thread.start()

    def _auto_check_devices(self):
        """按顺序检测三台仪器，通过信号通知每台结果。"""
        self._check_dmm()
        self._check_ps()
        self._check_relay()
        self._checking = False
        self.signal_all_checked.emit()
        logger.info("InstrumentManager: 仪器检测完成")

    # ── 单台仪器检测 ──────────────────────────────────────────────────

    def _check_dmm(self):
        """检测 34970A DMM。"""
        mode = self._config.get("dmm_mode", "usb")
        port = self._config.get("dmm_gpib", "11") if mode == "gpib" else \
               self._config.get("dmm_port", "/dev/cu.usbserial-FTDH1RD8")

        self.signal_device_status.emit("34970A", False, f"检测中 ({port})...")
        logger.info(f"检查 34970A (模式: {mode}, 端口: {port})...")

        def _create(): return KEYSIGHT_34970A(gpipID=9, serial_port=port)
        def _on_ok(inst):
            inst.set_DMMcls()
            self._dmm, self._dmm_connected = inst, True
        self._check_instrument("34970A", _create, _on_ok)

    def _check_ps(self):
        """检测 IT6382 电源。"""
        mode = self._config.get("ps_mode", "gpib")
        if mode == "usb":
            port = self._config.get("ps_usb_port", "")
            label = f"USB:{port}" if port else "USB (auto)"
        else:
            port = self._config["ps_port"]
            label = f"GPIB:{port}"

        self.signal_device_status.emit("IT6382", False, f"检测中 ({label})...")
        logger.info(f"检查 IT6382 ({label})...")

        gpibid = port if mode == "gpib" else None
        def _create(): return IT6382(gpibid) if gpibid else IT6382("")
        def _on_ok(inst):
            self._ps, self._ps_connected = inst, True
        self._check_instrument("IT6382", _create, _on_ok)

    def _check_relay(self):
        """检测继电器板。"""
        port = self._config["relay_port"]
        version = self._config["relay_version"]
        self.signal_device_status.emit("Relayboard", False, f"检测中 ({port})...")
        logger.info(f"检查 Relayboard ({port}, v{version})...")

        def _create(): return RELAYBOARD(version, port)
        def _on_ok(inst):
            inst.turn_off_relays(range(1, 9))
            self._relay, self._relay_connected = inst, True
        self._check_instrument("Relayboard", _create, _on_ok)

    def _check_instrument(self, name: str, factory, on_ok):
        """通用仪器检测 — 利用 BaseInstrument 多态接口。

        Args:
            name: 仪器显示名
            factory: () → BaseInstrument  仪器工厂函数
            on_ok: (BaseInstrument) → None  连接成功后的回调
        """
        try:
            inst = factory()
            if inst.connect():
                idn = inst.get_identity() or "IDN 查询失败"
                on_ok(inst)
                self.signal_device_status.emit(name, True, idn.strip())
                logger.info(f"{name} 连接成功: {idn.strip()}")
            else:
                self.signal_device_status.emit(name, False, "未找到仪器")
                logger.warning(f"{name} 未找到仪器")
        except Exception as e:
            self.signal_device_status.emit(name, False, f"错误: {e}")
            logger.error(f"{name} 检测异常: {e}")

    # ── 手动重连 ──────────────────────────────────────────────────────

    def reconnect_device(self, device_name: str):
        """手动重新连接指定仪器。"""
        if device_name == "34970A":
            self._disconnect_dmm()
            self._check_dmm()
        elif device_name == "IT6382":
            self._disconnect_ps()
            self._check_ps()
        elif device_name == "Relayboard":
            self._disconnect_relay()
            self._check_relay()

    def disconnect_device(self, device_name: str):
        """断开指定仪器并通知 UI。"""
        if device_name == "34970A":
            self._disconnect_dmm()
            self.signal_device_status.emit("34970A", False, "已断开")
        elif device_name == "IT6382":
            self._disconnect_ps()
            self.signal_device_status.emit("IT6382", False, "已断开")
        elif device_name == "Relayboard":
            self._disconnect_relay()
            self.signal_device_status.emit("Relayboard", False, "已断开")

    def reconnect_all(self):
        """断开并重新检测所有仪器。"""
        self._disconnect_all()
        thread = threading.Thread(target=self._auto_check_devices, daemon=True)
        thread.start()

    # ── 断开 ──────────────────────────────────────────────────────────

    def _disconnect_dmm(self):
        if self._dmm:
            try:
                self._dmm.close()
            except Exception:
                pass
        self._dmm = None
        self._dmm_connected = False

    def _disconnect_ps(self):
        if self._ps:
            try:
                self._ps.close()
            except Exception:
                pass
        self._ps = None
        self._ps_connected = False

    def _disconnect_relay(self):
        if self._relay:
            try:
                self._relay.close()
            except Exception:
                pass
        self._relay = None
        self._relay_connected = False

    def _disconnect_all(self):
        self._disconnect_dmm()
        self._disconnect_ps()
        self._disconnect_relay()

    def shutdown(self):
        """程序退出时断开所有仪器。"""
        self._disconnect_all()
        logger.info("InstrumentManager: 所有仪器已断开")
