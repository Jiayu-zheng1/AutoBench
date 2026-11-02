"""MultiChannelDutMonitor — 多通道 DUT 串口监控。

每个通道独立监控其 location ID，检测到 DUT 连接/断开时通过信号通知。
用于多通道自动测试模式（Mode 4）。

信号:
    channel_dut_detected(ch, device)   — 某通道 DUT 已连接
    channel_dut_lost(ch)               — 某通道 DUT 已断开
"""

import re
import subprocess
import time
from threading import Event

from PySide6.QtCore import QThread, Signal

from app.utils.logger import get_logger

logger = get_logger("MultiChannelDutMonitor")


class MultiChannelDutMonitor(QThread):
    """后台线程：按 location ID 列表同时监控多个 DUT 串口。

    每个通道有独立的:
    - location_id: USB location ID 字符串
    - 检测状态 (已连接/未连接)
    - 状态变化时发射对应信号
    """

    channel_dut_detected = Signal(str, str)  # (channel_id, device_path)
    channel_dut_lost = Signal(str)           # (channel_id)

    def __init__(self, channel_loc_map: dict[str, str], parent=None):
        """
        Args:
            channel_loc_map: {channel_id: location_id} 映射
                             例: {"CH1": "0x14200000", "CH2": "0x14200001"}
        """
        super().__init__(parent)
        self._channel_loc_map: dict[str, str] = dict(channel_loc_map)
        self._paused = False
        self._stop_event = Event()
        self._device_state: dict[str, str | None] = {
            ch: None for ch in self._channel_loc_map
        }  # channel_id → device_path or None

    def update_locations(self, channel_loc_map: dict[str, str]):
        """更新通道 location 映射（设置页保存后调用）。"""
        self._channel_loc_map = dict(channel_loc_map)
        # 为新通道初始化状态
        for ch in self._channel_loc_map:
            if ch not in self._device_state:
                self._device_state[ch] = None

    def set_channel_location(self, channel_id: str, location_id: str):
        """更新单个通道的 location ID。"""
        self._channel_loc_map[channel_id] = location_id

    def remove_channel(self, channel_id: str):
        """移除通道监控。"""
        self._channel_loc_map.pop(channel_id, None)
        self._device_state.pop(channel_id, None)

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def stop_monitor(self):
        """请求停止，不阻塞——线程在下一个循环自行退出。"""
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            if self._paused:
                self._sleep(0.5)
                continue

            if not self._channel_loc_map:
                self._sleep(1)
                continue

            # 一次性获取所有 DUT 设备信息（避免每个通道重复调 ioreg）
            all_devices = self._scan_all_devices()

            for channel_id, location_id in self._channel_loc_map.items():
                if not location_id:
                    continue
                device = self._find_device(all_devices, location_id)
                prev = self._device_state.get(channel_id)

                if device and not prev:
                    # DUT 连接事件
                    self._device_state[channel_id] = device
                    logger.info(f"[{channel_id}] DUT 检测到: {device} (loc={location_id})")
                    self.channel_dut_detected.emit(channel_id, device)
                elif not device and prev:
                    # DUT 断开事件
                    self._device_state[channel_id] = None
                    logger.info(f"[{channel_id}] DUT 已断开")
                    self.channel_dut_lost.emit(channel_id)

            self._sleep(0.6)

    def _scan_all_devices(self) -> list[dict]:
        """一次性 ioreg 扫描，提取所有 IOSerialBSDClient 设备。"""
        try:
            cmd = "ioreg -itrc IOSerialBSDClient -w0"
            p = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, _ = p.communicate()
            raw = stdout.decode(errors="replace")
        except Exception:
            return []

        devices = []
        for block in raw.split("+-o "):
            sm = re.search(r'"IOTTYSuffix"\s*=\s*"(\d+)"', block)
            dm = re.search(r'"IOCalloutDevice"\s*=\s*"(/dev/cu\.\S+)"', block)
            if sm and dm and "BLTH" not in dm.group(1) and "Bluetooth" not in dm.group(1):
                devices.append({
                    "suffix": sm.group(1),
                    "device": dm.group(1),
                    "location_id": f"0x{sm.group(1)}",
                })
        return devices

    def _find_device(self, all_devices: list[dict], location_id: str) -> str | None:
        """在设备列表中按 location_id 查找匹配的串口。

        匹配优先级（与 find_port_by_location 一致）:
        1. IOTTYSuffix 精准匹配
        2. IOTTYSuffix 前缀匹配
        3. 反向匹配
        4. 公共前缀匹配（唯一匹配时）
        """
        if not location_id:
            return None

        loc_id = location_id.lower().replace("0x", "")

        # L1: 精准匹配
        for d in all_devices:
            if d["suffix"] == loc_id:
                return d["device"]

        # L2: loc_id 是 suffix 的前缀
        if len(loc_id) >= 3:
            for d in all_devices:
                if d["suffix"].startswith(loc_id):
                    return d["device"]

        # L3: suffix 是 loc_id 的前缀
        for d in all_devices:
            if loc_id.startswith(d["suffix"]) and len(d["suffix"]) >= 5:
                return d["device"]

        # L4: 公共前缀 ≥ 5 位，且唯一匹配
        if len(loc_id) >= 5:
            matched = []
            for d in all_devices:
                common = self._common_prefix(d["suffix"], loc_id)
                if len(common) >= 5:
                    matched.append(d["device"])
            if len(matched) == 1:
                return matched[0]

        return None

    @staticmethod
    def _common_prefix(a: str, b: str) -> str:
        i = 0
        for i, (ca, cb) in enumerate(zip(a, b)):
            if ca != cb:
                return a[:i]
        return a[:i + 1]

    def _sleep(self, seconds: float):
        """可分片 sleep——每 0.2s 检查一次停止信号。"""
        elapsed = 0.0
        while elapsed < seconds and not self._stop_event.is_set():
            time.sleep(min(0.2, seconds - elapsed))
            elapsed += 0.2
