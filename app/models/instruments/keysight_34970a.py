# Peng Wu
# For Agilent (Keysight) 34970A.
# v5 2026/05/20 增加：直流电压扫描测量功能

import logging
import threading
import time

import pyvisa

logger = logging.getLogger("KEYSIGHT_34970A")

# FTDI USB转GPIB适配器, 在系统中表现为串口
USB_BAUDRATE = 9600


from app.models.instruments.base import BaseInstrument


class KEYSIGHT_34970A(BaseInstrument):
    def __init__(self, gpipID, serial_port: str = ""):
        self.gpipID = gpipID
        self.serial_port = serial_port
        self.instrument = None
        self._connected = False
        self._lock = threading.Lock()

    # ── BaseInstrument 接口 ──

    def connect(self) -> bool:
        """建立连接。返回 True 表示成功。"""
        result = self.dmm_instrument()
        self._connected = result is not None
        return self._connected

    def disconnect(self) -> None:
        self._connected = False
        self.close()

    def get_identity(self) -> str | None:
        return self.query_IDN()

    @property
    def is_connected(self) -> bool:
        return self._connected

    def dmm_instrument(self):
        with self._lock:
            try:
                port = self.serial_port or str(self.gpipID)

                # ── 判断连接类型 ──
                if "GPIB" in port.upper():
                    # GPIB 资源字符串 (e.g. "GPIB0::11::INSTR") → NI-VISA 直连
                    self._connect_gpib(port)
                elif port.startswith("/"):
                    # 串口路径 (e.g. "/dev/cu.usbserial-xxx") → pyvisa-py ASRL
                    self._connect_usb(port)
                elif port.isdigit():
                    # 纯数字 GPIB 地址 (e.g. "11") → 构造 GPIB0::11::INSTR
                    self._connect_gpib_by_id(int(port))
                else:
                    # 兜底：尝试作为 ASRL 资源名
                    self._connect_usb(port)

                if self.instrument:
                    self._connected = True
                    return self.instrument

                # ── 兜底：扫描 GPIB 资源列表 ──
                gpib_addr = "GPIB0::" + str(self.gpipID) + "::INSTR"
                rm = pyvisa.ResourceManager()
                for res in rm.list_resources():
                    if gpib_addr in res:
                        self.instrument = rm.open_resource(gpib_addr)
                        self._connected = True
                        logger.info(f"34970A GPIB 连接成功: {gpib_addr}")
                        return self.instrument

                logger.warning("34970A 未找到仪器")
                return None
            except Exception as e:
                logger.error(f"34970A init error: {e}")
                return None

    # ── 连接子方法 ──────────────────────────────────────────────────────

    def _connect_usb(self, port: str):
        """USB 串口连接 (FTDI 适配器 via pyvisa-py)。"""
        try:
            rm_usb = pyvisa.ResourceManager("@py")
            self.instrument = rm_usb.open_resource(f"ASRL{port}::INSTR")
            self.instrument.baud_rate = USB_BAUDRATE
            self.instrument.read_termination = "\n"
            self.instrument.write_termination = "\n"
            self.instrument.timeout = 5000
            time.sleep(0.5)
            self.instrument.write("*CLS")
            time.sleep(0.2)
            idn = self.instrument.query("*IDN?").strip()
            self._connected = True
            logger.info(f"34970A USB 连接成功: {port} -> {idn}")
        except Exception as e:
            logger.error(f"34970A USB 连接失败 ({port}): {e}")
            import traceback

            logger.error(traceback.format_exc())
            self.instrument = None
            self._connected = False

    def _connect_gpib(self, resource_str: str):
        """GPIB 资源字符串直连 (NI-VISA)。"""
        try:
            rm = pyvisa.ResourceManager()
            self.instrument = rm.open_resource(resource_str)
            self.instrument.timeout = 5000
            idn = self.instrument.query("*IDN?").strip()
            logger.info(f"34970A GPIB 连接成功: {resource_str} -> {idn}")
        except Exception as e:
            logger.error(f"34970A GPIB 连接失败 ({resource_str}): {e}")
            self.instrument = None

    def _connect_gpib_by_id(self, gpib_id: int):
        """按 GPIB ID 扫描连接 (NI-VISA)。"""
        resource_str = f"GPIB0::{gpib_id}::INSTR"
        try:
            rm = pyvisa.ResourceManager()
            for res in rm.list_resources():
                if resource_str in res:
                    self.instrument = rm.open_resource(resource_str)
                    self.instrument.timeout = 5000
                    idn = self.instrument.query("*IDN?").strip()
                    logger.info(f"34970A GPIB 连接成功: {resource_str} -> {idn}")
                    return
            logger.warning(f"34970A GPIB 未找到资源: {resource_str}")
            self.instrument = None
        except Exception as e:
            logger.error(f"34970A GPIB 连接失败 ({resource_str}): {e}")
            self.instrument = None

    def set_RES(self, channel):
        with self._lock:
            try:
                self.instrument.write(f"CONF:RES (@{channel})")
                time.sleep(0.05)
                self.instrument.write("TRIG:SOUR IMM")
                time.sleep(0.05)
                check_error = self.query_DMMerror()
                if check_error[0]:
                    return True, None
                else:
                    return False, check_error[1]
            except Exception as e:
                print(f"An error occurred: {e}")
                return None

    def set_DCV(self, channel):
        with self._lock:
            try:
                self.instrument.write(f"CONF:VOLT:DC (@{channel})")
                time.sleep(0.1)
                self.instrument.write("TRIG:SOUR IMM")
                time.sleep(0.1)
                check_error = self.query_DMMerror()
                if check_error[0]:
                    return True, None
                else:
                    return False, check_error[1]
            except Exception as e:
                print(f"An error occurred: {e}")
                return None

    def get_DMMvalue(self):
        with self._lock:
            try:
                DMMvalue = float(self.instrument.query("READ?"))
                return str(DMMvalue)
            except Exception as e:
                print(f"读取错误: {e}")
                return "-9999"

    def query_DMMerror(self):
        with self._lock:
            try:
                error = self.instrument.query("SYSTem:ERRor?")
                if "No error" in error:
                    return True, None
                else:
                    return False, error
            except Exception as e:
                print(f"An error occurred: {e}")
                return str(f"An error occurred: {e}")

    def scan_slot_res(self, channels=None):
        """扫描通道电阻, 每批最多10个通道"""
        with self._lock:
            try:
                slot_list = [s.strip() for s in channels.split(",")]
                all_results = {}
                batch_size = 10
                for batch_start in range(0, len(slot_list), batch_size):
                    batch = slot_list[batch_start : batch_start + batch_size]
                    batch_channels = ",".join(batch)
                    self.instrument.write("*RST")
                    time.sleep(0.5)
                    self.instrument.write(f"ROUT:SCAN (@{batch_channels})")
                    time.sleep(0.5)
                    self.instrument.write(f"CONF:RES 10000, 0.1, (@{batch_channels})")
                    time.sleep(0.5)
                    self.instrument.write("ROUT:CHAN:DEL 0")
                    time.sleep(0.5)
                    self.instrument.write("TRIG:SOUR IMM")
                    time.sleep(0.5)
                    self.instrument.write("INIT")
                    time.sleep(1.5)
                    data = self.instrument.query("FETCH?")
                    data_values = data.strip().split(",")
                    for i, slot in enumerate(batch):
                        if i < len(data_values):
                            try:
                                all_results[slot] = float(data_values[i])
                            except ValueError:
                                all_results[slot] = None
                        else:
                            all_results[slot] = None
                return all_results
            except Exception as e:
                print(f"错误: {e}")
                return None

    def scan_slot_dcv(
        self, channels=None, range_val="AUTO", resolution="DEFAULT", delay=0, unit="V"
    ):
        """扫描通道直流电压, 每批最多10个通道"""
        with self._lock:
            try:
                slot_list = [s.strip() for s in channels.split(",")]
                all_results = {}
                batch_size = 10
                for batch_start in range(0, len(slot_list), batch_size):
                    batch = slot_list[batch_start : batch_start + batch_size]
                    batch_channels = ",".join(batch)
                    self.instrument.write("*RST")
                    time.sleep(0.3)
                    self.instrument.write(f"ROUT:SCAN (@{batch_channels})")
                    time.sleep(0.1)
                    if range_val == "AUTO":
                        self.instrument.write(f"CONF:VOLT:DC (@{batch_channels})")
                    else:
                        self.instrument.write(
                            f"CONF:VOLT:DC {range_val}, {resolution}, (@{batch_channels})"
                        )
                    time.sleep(0.1)
                    self.instrument.write(f"ROUT:CHAN:DEL {delay}")
                    time.sleep(0.05)
                    self.instrument.write("TRIG:SOUR IMM")
                    time.sleep(0.05)
                    self.instrument.write("INIT")
                    time.sleep(1.5)
                    data = self.instrument.query("FETCH?")
                    data_values = data.strip().split(",")
                    for i, slot in enumerate(batch):
                        if i < len(data_values):
                            try:
                                val = float(data_values[i])
                                if unit == "mV":
                                    val = round(val * 1000, 3)
                                all_results[slot] = val
                            except ValueError:
                                all_results[slot] = None
                        else:
                            all_results[slot] = None
                return all_results
            except Exception as e:
                print(f"错误: {e}")
                import traceback

                traceback.print_exc()
                return None

    def scan_slot_dcv_fast(
        self, channels=None, range_val="AUTO", resolution="DEFAULT", delay=0
    ):
        """快速扫描通道直流电压 (不重置仪器, 保持上一次配置)"""
        with self._lock:
            try:
                slot_list = [s.strip() for s in channels.split(",")]
                all_results = {}
                batch_size = 10
                for batch_start in range(0, len(slot_list), batch_size):
                    batch = slot_list[batch_start : batch_start + batch_size]
                    batch_channels = ",".join(batch)
                    self.instrument.write(f"ROUT:SCAN (@{batch_channels})")
                    time.sleep(0.1)
                    if range_val == "AUTO":
                        self.instrument.write(f"CONF:VOLT:DC (@{batch_channels})")
                    else:
                        self.instrument.write(
                            f"CONF:VOLT:DC {range_val}, {resolution}, (@{batch_channels})"
                        )
                    time.sleep(0.1)
                    self.instrument.write(f"ROUT:CHAN:DEL {delay}")
                    time.sleep(0.05)
                    self.instrument.write("TRIG:SOUR IMM")
                    time.sleep(0.05)
                    self.instrument.write("INIT")
                    time.sleep(1.5)
                    data = self.instrument.query("FETCH?")
                    data_values = data.strip().split(",")
                    for i, slot in enumerate(batch):
                        if i < len(data_values):
                            try:
                                all_results[slot] = float(data_values[i])
                            except ValueError:
                                all_results[slot] = None
                        else:
                            all_results[slot] = None
                return all_results
            except Exception as e:
                print(f"错误: {e}")
                import traceback

                traceback.print_exc()
                return None

    def measure_res(self, channel, unit="Ω"):
        """单通道阻抗测量 (MEAS:RES? 一键完成, 不卡死)。"""
        with self._lock:
            try:
                value = float(self.instrument.query(f"MEAS:RES? (@{channel})"))
                return str(value)
            except Exception as e:
                print(f"测量错误: {e}")
                return "-9999"

    def measure_dcv(self, channel, unit="V"):
        """一键测量直流电压, unit='V'或'mV'"""
        with self._lock:
            try:
                value = float(self.instrument.query(f"MEAS:VOLT:DC? (@{channel})"))
                if unit == "mV":
                    value = round(value * 1000, 3)
                return value
            except Exception as e:
                print(f"测量错误: {e}")
                return None

    def set_DMMcls(self):
        with self._lock:
            try:
                self.instrument.write("*CLS")
                return "Clear DMM Errors OK"
            except Exception as e:
                print(f"An error occurred: {e}")
                return None

    def set_DMMreset(self):
        with self._lock:
            try:
                self.instrument.write("*RST")
                return
            except Exception as e:
                print(f"An error occurred: {e}")
                return

    def query_IDN(self):
        with self._lock:
            try:
                idntext = self.instrument.query("*IDN?")
                return idntext
            except Exception as e:
                print(f"An error occurred: {e}")
                return None

    def close(self):
        with self._lock:
            try:
                if self.instrument:
                    self.instrument.close()
                    self.instrument = None
                self._connected = False
            except Exception as e:
                print(f"An error occurred: {e}")
