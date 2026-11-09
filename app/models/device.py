"""DUT serial communication module."""

import time

import serial
from serial.tools import list_ports

from app.utils.logger import get_logger

logger = get_logger("DUT")

READ_TIMEOUT = 3.0


class DutDisconnected(Exception):
    """DUT 串口句柄失效（拔出、驱动重置或端口被关闭）。"""


def list_dut_devices(vid: str = "", pid: str = "") -> list[dict]:
    """列出所有可用的 DUT 串口设备及其 location 信息。
    用于设置页显示可选设备列表，帮助用户配置每通道 Location ID / path。
    Windows 可按 VID/PID 过滤。
    """
    import sys

    if sys.platform.startswith("win"):
        return _list_windows_dut_devices(vid, pid)

    import re as _re
    import subprocess

    result = []
    try:
        raw = subprocess.run(
            ["ioreg", "-itrc", "IOSerialBSDClient", "-w0"],
            capture_output=True, text=True, timeout=3,
        ).stdout

        for block in raw.split("+-o "):
            sm = _re.search(r'"IOTTYSuffix"\s*=\s*"(\d+)"', block)
            dm = _re.search(r'"IOCalloutDevice"\s*=\s*"(/dev/cu\.\S+)"', block)
            if sm and dm and "BLTH" not in dm.group(1) and "Bluetooth" not in dm.group(1):
                result.append({
                    "device": dm.group(1),
                    "suffix": sm.group(1),
                    "location_id": f"0x{sm.group(1)}",
                })
    except Exception:
        pass
    return result


def _list_windows_dut_devices(vid: str = "", pid: str = "") -> list[dict]:
    """Windows：用 pyserial 列出 USB 串口及 Location path。"""
    import re as _re
    from serial.tools import list_ports

    target_vid = vid.upper().replace("0X", "").strip()
    target_pid = pid.upper().replace("0X", "").strip()

    def _interface(location: str) -> str:
        text = location or ""
        match = _re.search(r"USBMI\((\d+)\)", text, _re.IGNORECASE)
        if match:
            return f"MI_{int(match.group(1)):02d}"
        if ":" in text:
            match = _re.search(r"\.(\d+)\s*$", text.split(":", 1)[1])
            if match:
                return f"MI_{int(match.group(1)):02d}"
        return ""

    result = []
    for port in list_ports.comports():
        if getattr(port, "vid", None) is None:
            continue
        port_vid = f"{port.vid:04X}"
        port_pid = f"{port.pid:04X}" if port.pid is not None else ""
        if target_vid and port_vid.upper() != target_vid:
            continue
        if target_pid and port_pid.upper() != target_pid:
            continue
        location = port.location or ""
        result.append({
            "device": port.device,
            "suffix": port.serial_number or "",
            "location_id": location,
            "interface": _interface(location),
            "vid": port_vid,
            "pid": port_pid,
        })
    result.sort(key=lambda d: (d["location_id"], d["device"]))
    return result


def get_ports():
    ports = list(
        list_ports.grep(r"/dev/cu\.(usbmodem\w+|pencil\w*|Pencil\w*|Configuration\w*)")
    )
    # 按端口名排序，确保同名系列中编号最小的排最前（如 usbmodem146331301 优先于 usbmodem146331303）
    ports.sort(key=lambda p: p.device)
    if ports:
        logger.info(f"get_ports:{ports[0].device}")
    return ports


def find_port_by_location(location_id: str):
    """按 location ID 查找 DUT 串口。

    匹配优先级：
    1. IOTTYSuffix 精准匹配（如 1463301 → usbmodem1463301）
    2. IOTTYSuffix 前缀匹配（如 14633 → 1463301）
    3. 公共前缀匹配（如 hub 0x14633000 → 1463301，取公共前缀 146330）
    4. pyserial location / device 名匹配
    5. 未设 location_id → get_ports() 兜底
    """
    import re as _re
    import subprocess

    if not location_id:
        ports = get_ports()
        return ports[0].device if ports else None

    loc_id = location_id.lower().replace("0x", "")

    # ── ioreg 匹配（按优先级逐层扫描，避免第一命中误判）──
    try:
        raw = subprocess.run(
            ["ioreg", "-itrc", "IOSerialBSDClient", "-w0"],
            capture_output=True, text=True, timeout=3,
        ).stdout

        devices = []  # [(suffix, device)]
        for block in raw.split("+-o "):
            sm = _re.search(r'"IOTTYSuffix"\s*=\s*"(\d+)"', block)
            dm = _re.search(r'"IOCalloutDevice"\s*=\s*"(/dev/cu\.\S+)"', block)
            if sm and dm:
                devices.append((sm.group(1), dm.group(1)))

        # L1: 精准匹配
        for suffix, device in devices:
            if suffix == loc_id:
                logger.info(f"DUT 精准匹配: {device} (IOTTYSuffix={suffix})")
                return device

        # L2: loc_id 是 suffix 的前缀
        if len(loc_id) >= 3:
            for suffix, device in devices:
                if suffix.startswith(loc_id):
                    logger.info(f"DUT 前缀匹配: {device} ({suffix} ← {loc_id})")
                    return device

        # L3: suffix 是 loc_id 的前缀（反向，如 1463301 是 14633001 的前缀）
        for suffix, device in devices:
            if loc_id.startswith(suffix) and len(suffix) >= 5:
                logger.info(f"DUT 反向前缀匹配: {device} ({suffix} ⊂ {loc_id})")
                return device

        # L4: 公共前缀 ≥ 5 位，且必须唯一匹配
        if len(loc_id) >= 5:
            matched = []
            for suffix, device in devices:
                common = _common_prefix(suffix, loc_id)
                if len(common) >= 5:
                    matched.append((device, common))
            if len(matched) == 1:
                d, c = matched[0]
                logger.info(f"DUT 公共前缀唯一匹配: {d} (common={c})")
                return d
            elif len(matched) > 1:
                logger.info(
                    f"DUT 公共前缀匹配到 {len(matched)} 个设备 (loc={loc_id})，"
                    f"请用更精确的 ID: {[s for s,_ in devices]}"
                )
    except Exception:
        pass

    # ── pyserial / device 名 fallback ──
    for p in list_ports.comports():
        d = p.device or ""
        if "cu." not in d or "BLTH" in d or "Bluetooth" in d:
            continue
        p_loc = (getattr(p, "location", "") or "").lower()
        m = _re.search(r"usbmodem(\d+)", d)
        dev_loc = m.group(1) if m else ""

        if loc_id in p_loc or loc_id in dev_loc or p_loc in loc_id or (dev_loc and loc_id in dev_loc):
            logger.info(f"DUT fallback 匹配: {d}")
            return d

    return None


def _common_prefix(a: str, b: str) -> str:
    """返回两个字符串的最长公共前缀。"""
    i = 0
    for i, (ca, cb) in enumerate(zip(a, b)):
        if ca != cb:
            return a[:i]
    return a[:i + 1]


class Device:
    """Serial device under test."""

    def __init__(self):
        self.ser: serial.Serial = None

    def open_get_port(self, port, baudrate=921600):
        self.ser = serial.Serial(port=port, baudrate=baudrate, timeout=0.1)
        time.sleep(0.01)
        self.ser.write(b"\n")

    def _handle_serial_error(self, exc):
        logger.warning(f"DUT 串口句柄失效: {exc}")
        try:
            self.close_port()
        except Exception:
            pass
        self.ser = None
        raise DutDisconnected(str(exc)) from exc

    def read_cmd(self):
        buffr = b""
        deadline = time.time() + READ_TIMEOUT
        try:
            while time.time() < deadline:
                data = self.ser.read_all()
                if data:
                    buffr += data
                    if data.endswith(b"[3G"):
                        logger.info(f"read_data:{buffr.decode(errors='replace')}")
                        break
                else:
                    time.sleep(0.01)
        except (serial.SerialException, OSError) as exc:
            self._handle_serial_error(exc)
        return buffr.decode(errors="replace")

    def clear_data(self):
        deadline = time.time() + 0.5
        try:
            while time.time() < deadline:
                data = self.ser.read_all()
                logger.debug(f"clear {data}")
                if not data:
                    break
                time.sleep(0.005)
        except (serial.SerialException, OSError) as exc:
            self._handle_serial_error(exc)

    def send_cmd(self, cmd):
        try:
            self.clear_data()
            self.ser.write((cmd + "\n").encode())
            logger.debug(f"send_cmd:{cmd}")
        except (serial.SerialException, OSError) as exc:
            self._handle_serial_error(exc)

    def close_port(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def read_Write(self, cmd):
        self.send_cmd(cmd)
        time.sleep(0.01)
        return self.read_cmd()

    def send_hex_cmd(self, hex_str: str, delay: float = 0.05) -> tuple[str, str]:
        """发送 Hex 指令，返回 (原始hex值, ASCII解码结果)。"""
        rx = b""
        try:
            self.ser.reset_input_buffer()
            raw = hex_str.strip().replace(" ", "")
            data = bytes.fromhex(raw)
            self.ser.write(data)
            time.sleep(delay)
            rx = self.ser.read_all()
        except (serial.SerialException, OSError) as exc:
            self._handle_serial_error(exc)
        logger.info(f"send_hex_cmd sent: {hex_str}, received raw: {rx.hex()}")
        if not rx:
            return "", ""
        # 原始 hex 值
        raw_hex = rx.hex()
        # ASCII 解码结果
        ascii_str = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in rx)
        return raw_hex, ascii_str
