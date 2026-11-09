"""Windows DUT 串口监控 — 轮询 pyserial，按 Hub 下游端口映射 Slot。

不依赖 SN 和固定主机 USB 口：
- 通过 location（如 1-3.4）的最后一段识别 Hub 下游端口；
- VID/PID 仅作为可选过滤；
- 同一 Slot 的插入/拔出通过快照 diff 去重。
"""

import json
import os
import re
import subprocess
import time
from threading import Event

from PySide6.QtCore import QThread, Signal
from serial.tools import list_ports

from app.utils.logger import get_logger

logger = get_logger("WindowsMonitor")

POLL_INTERVAL = 0.5
_PNP_CACHE = {"ts": 0.0, "map": {}}


def _normalize_location(location: str) -> str:
    return (location or "").split(":", 1)[0].strip().lower()


def _pnp_location_map() -> dict[str, str]:
    """pyserial 没有 location 时，用 PowerShell 读取 PnP LocationPaths。"""
    now = time.monotonic()
    if now - _PNP_CACHE["ts"] < 2.0:
        return _PNP_CACHE["map"]
    _PNP_CACHE["ts"] = now

    script = (
        "$out = Get-PnpDevice -Class Ports -PresentOnly | ForEach-Object {"
        " $p = Get-PnpDeviceProperty -InstanceId $_.InstanceId"
        " -KeyName 'DEVPKEY_Device_LocationPaths' -ErrorAction SilentlyContinue;"
        " [pscustomobject]@{Name=$_.FriendlyName; Paths=($p.Data -join ';')}"
        "}; $out | ConvertTo-Json -Compress"
    )
    kwargs = {"capture_output": True, "text": True, "timeout": 5}
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            **kwargs,
        ).stdout
        data = json.loads(out) if out.strip() else []
        if isinstance(data, dict):
            data = [data]
        mapping = {}
        for item in data:
            name = item.get("Name") or ""
            match = re.search(r"\((COM\d+)\)", name, re.IGNORECASE)
            paths = item.get("Paths") or ""
            if match and paths:
                mapping[match.group(1).upper()] = paths
        _PNP_CACHE["map"] = mapping
    except Exception as exc:
        logger.warning(f"读取 PnP LocationPaths 失败: {exc}")
        _PNP_CACHE["map"] = {}
    return _PNP_CACHE["map"]


def slot_from_location(location: str) -> int | None:
    """从 pyserial location 或 Windows LocationPaths 提取 Hub 下游端口号。

    例：
    - '1-3.4' -> 4
    - '...USBROOT(0)#USB(2)#USB(3)#USBMI(2)' -> 3
    """
    base = _normalize_location(location)
    if not base:
        return None
    # Windows PnP LocationPaths：取 USBMI 之前最后一个 USB(n)
    usb_ports = re.findall(r"USB\((\d+)\)", base, re.IGNORECASE)
    if usb_ports:
        return int(usb_ports[-1])
    parts = [p for p in base.replace(".", "-").split("-") if p]
    for part in reversed(parts):
        if part.isdigit():
            return int(part)
    return None


def interface_from_location(location: str) -> str:
    """从 pyserial location 推断复合设备接口号，如 1-2.4:x.2 或 USBMI(2) → MI_02。"""
    text = location or ""
    match = re.search(r"USBMI\((\d+)\)", text, re.IGNORECASE)
    if match:
        return f"MI_{int(match.group(1)):02d}"
    match = re.search(r"MI[_-]?(\d+)", text, re.IGNORECASE)
    if match:
        return f"MI_{int(match.group(1)):02d}"
    if ":" in text:
        tail = text.split(":", 1)[1]
        match = re.search(r"\.(\d+)\s*$", tail)
        if match:
            return f"MI_{int(match.group(1)):02d}"
    return ""


def _matching_ports(predicate=None, interface: str = "", vid: str = "",
                    pid: str = "") -> list:
    ports = []
    pnp_map = None
    target_vid = vid.upper().replace("0X", "").strip()
    target_pid = pid.upper().replace("0X", "").strip()
    for port in list_ports.comports():
        port_vid = f"{port.vid:04X}" if port.vid is not None else ""
        port_pid = f"{port.pid:04X}" if port.pid is not None else ""
        if target_vid and port_vid.upper() != target_vid:
            continue
        if target_pid and port_pid.upper() != target_pid:
            continue
        location = getattr(port, "location", "") or ""
        if not location:
            match = re.search(r"LOCATION=([0-9A-Za-z\.\-]+)", port.hwid or "")
            if match:
                port.location = match.group(1)
                location = port.location
        if not location and os.name == "nt":
            if pnp_map is None:
                pnp_map = _pnp_location_map()
            location = pnp_map.get(port.device.upper(), "")
            if location:
                port.location = location
        if not location:
            # FTDI 等驱动可能隐藏 location，且 PnP 也没有可用路径
            continue
        if interface:
            iface = interface_from_location(location)
            if iface and iface.upper() != interface.upper():
                continue
        if predicate and not predicate(port):
            continue
        ports.append(port)
    ports.sort(key=lambda p: p.device)
    return ports


class WindowsDutMonitor(QThread):
    """单通道 Windows 监控：任意目标 DUT 串口出现/消失。"""

    dut_detected = Signal(str)
    dut_lost = Signal()

    def __init__(self, location_id: str = "", interface: str = "",
                 vid: str = "", pid: str = "", parent=None):
        super().__init__(parent)
        self.location_id = location_id
        self.interface = interface
        self.vid = vid
        self.pid = pid
        self._paused = False
        self._stop_event = Event()
        self._device: str | None = None

    def set_location_id(self, location_id: str):
        # Windows 模式不使用 macOS location_id
        self.location_id = location_id

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def stop_monitor(self):
        self._stop_event.set()

    def _scan(self):
        return _matching_ports(
            interface=self.interface, vid=self.vid, pid=self.pid
        )

    def run(self):
        while not self._stop_event.is_set():
            if self._paused:
                self._stop_event.wait(POLL_INTERVAL)
                continue

            ports = self._scan()
            if self.location_id:
                target = _normalize_location(self.location_id)
                ports = [
                    p for p in ports
                    if _normalize_location(p.location) == target
                ]
            devices = [p.device for p in ports]

            if self._device and self._device not in devices:
                logger.info(f"DUT 串口已断开: {self._device}")
                self._device = None
                self.dut_lost.emit()

            if self._device is None and ports:
                port = ports[0]
                logger.info(f"DUT 串口检测到: {port.device} (location={port.location})")
                self._device = port.device
                self.dut_detected.emit(port.device)

            self._stop_event.wait(POLL_INTERVAL)


class WindowsMultiChannelDutMonitor(QThread):
    """多通道 Windows 监控：按 Hub 下游端口映射 CH1..CHn。"""

    channel_dut_detected = Signal(str, str)
    channel_dut_lost = Signal(str)

    def __init__(self, channel_loc_map: dict[str, str], interface: str = "",
                 vid: str = "", pid: str = "", parent=None):
        super().__init__(parent)
        self.interface = interface
        self.vid = vid
        self.pid = pid
        self._channel_locs = {
            ch: (loc or "") for ch, loc in channel_loc_map.items()
        }
        self._channels = set(self._channel_locs)
        self._paused = False
        self._stop_event = Event()
        self._known: dict[str, str] = {}

    def update_locations(self, channel_loc_map: dict[str, str]):
        self._channel_locs = {
            ch: (loc or "") for ch, loc in channel_loc_map.items()
        }
        self._channels = set(self._channel_locs)
        for ch in list(self._known):
            if ch not in self._channels:
                self._known.pop(ch, None)
                self.channel_dut_lost.emit(ch)

    def set_channel_location(self, channel_id: str, location_id: str):
        self._channel_locs[channel_id] = location_id or ""
        self._channels.add(channel_id)

    def remove_channel(self, channel_id: str):
        self._channels.discard(channel_id)
        self._channel_locs.pop(channel_id, None)
        if self._known.pop(channel_id, None) is not None:
            self.channel_dut_lost.emit(channel_id)

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def stop_monitor(self):
        self._stop_event.set()

    def _scan(self) -> dict[str, str]:
        ports = _matching_ports(
            interface=self.interface, vid=self.vid, pid=self.pid
        )
        current: dict[str, str] = {}
        used: set[str] = set()

        # 1) 优先按用户配置的 Location path 精确匹配
        for ch in self._channels:
            path = self._channel_locs.get(ch, "")
            if not path:
                continue
            target = _normalize_location(path)
            for port in ports:
                if port.device in used:
                    continue
                if _normalize_location(port.location) == target:
                    current[ch] = port.device
                    used.add(port.device)
                    break

        # 2) 未配置路径的通道按 Hub 下游端口号兜底
        for port in ports:
            if port.device in used:
                continue
            slot = slot_from_location(port.location)
            if slot is None:
                continue
            ch = f"CH{slot}"
            if ch in self._channels and ch not in current:
                current[ch] = port.device
                used.add(port.device)
        return current

    def run(self):
        while not self._stop_event.is_set():
            if self._paused:
                self._stop_event.wait(POLL_INTERVAL)
                continue

            current = self._scan()

            for ch, device in current.items():
                if self._known.get(ch) != device:
                    logger.info(f"[{ch}] DUT 检测到: {device}")
                    self.channel_dut_detected.emit(ch, device)
            for ch in list(self._known):
                if ch not in current:
                    logger.info(f"[{ch}] DUT 已断开")
                    self.channel_dut_lost.emit(ch)
            self._known = current
            self._stop_event.wait(POLL_INTERVAL)
