"""DUT 串口监控 — 后台线程用 ioreg 按 location ID 检测 DUT 插拔。"""

import re
import subprocess
import time
from threading import Event

from PySide6.QtCore import QThread, Signal

from app.utils.logger import get_logger

logger = get_logger("DUTMonitor")


class DutMonitor(QThread):
    """后台线程：用 ioreg 按 location ID 检测 DUT 串口。"""

    dut_detected = Signal(str)
    dut_lost = Signal()

    def __init__(self, location_id: str = "", parent=None):
        super().__init__(parent)
        self.location_id = location_id
        self._paused = False
        self._stop_event = Event()          # 线程安全停止信号
        self._device: str | None = None

    def set_location_id(self, location_id: str):
        self.location_id = location_id

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def stop_monitor(self):
        """请求停止，不阻塞——让线程在下一个循环自行退出。"""
        self._stop_event.set()
        # 不调 wait()——线程每次睡眠最多 0.2s，进程退出时 OS 会回收

    def run(self):
        while not self._stop_event.is_set():
            if self._paused:
                self._sleep(0.5)
                continue

            loc = self.location_id
            if not loc:
                self._sleep(1)
                continue

            search_key = loc.replace("0x", "").replace("0X", "")
            try:
                cmd = f"ioreg -itrc IOSerialBSDClient -w0 | grep -A 15 -i {search_key}"
                p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, _ = p.communicate()

                serial_rex = re.compile(
                    search_key + r'[\s\S]+?"IOCalloutDevice" = "(/dev/cu\.(usbmodem\w+|pencil\w*|Pencil\w*|Configuration\w*))"'
                )
                port_mo = serial_rex.search(stdout.decode(errors="replace")) if stdout else None

                if port_mo:
                    device = port_mo.group(1)
                    if not self._device:
                        self._device = device
                        logger.info(f"DUT 串口检测到: {device} (loc={loc})")
                        self.dut_detected.emit(device)
                else:
                    if self._device:
                        logger.info("DUT 串口已断开")
                        self._device = None
                        self.dut_lost.emit()

            except Exception as e:
                logger.warning(f"DUT 监控异常: {e}")

            self._sleep(0.6)

    def _sleep(self, seconds: float):
        """可分片 sleep——每 0.2s 检查一次停止信号，总延迟不超过 seconds。"""
        elapsed = 0.0
        while elapsed < seconds and not self._stop_event.is_set():
            time.sleep(min(0.2, seconds - elapsed))
            elapsed += 0.2


def create_dut_monitor(location_id: str = "", platform: str | None = None,
                       interface: str = "", vid: str = "", pid: str = ""):
    """按指定平台创建 DUT 监控器。"""
    from app.utils.config import PLATFORM_WINDOWS, get_platform_mode

    mode = platform or get_platform_mode()
    if mode == PLATFORM_WINDOWS:
        from app.controllers.windows_monitor import WindowsDutMonitor

        return WindowsDutMonitor(location_id, interface, vid, pid)
    return DutMonitor(location_id)
