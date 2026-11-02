# Peng Wu
# For IT6382 Power supply.
# v2 增加电压电流读取,3通道同时输出/关闭,优化代码

import threading

import pyvisa

from app.models.instruments.base import BaseInstrument


class IT6382(BaseInstrument):
    def __init__(self, gpipID):
        self.gpipID = gpipID
        self.instrument = None
        self._connected = False
        self._lock = threading.Lock()

    # ── BaseInstrument 接口 ──

    def connect(self) -> bool:
        result = self.ps_instrument()
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

    # ── 原有方法 ──

    def ps_instrument(self):
        try:
            rm = pyvisa.ResourceManager()
            IT6382Res = None
            for res in rm.list_resources():
                if "USB0::0xFFFF::0x6300" in res or "USB0::0xFFFF::0x6900" in res or f"GPIB0::{self.gpipID}::INSTR" in res:
                    IT6382Res = res
            if IT6382Res is None:
                print("IT6382 未找到仪器")
                return None
            self.instrument = rm.open_resource(IT6382Res)
            self._connected = True
            self.output_off_all()
            return self.instrument
        except Exception as e:
            print(f"IT6382 init error: {e}")
            self._connected = False
            return None

    def query_IDN(self):
        try:
            idntext = self.instrument.query('*IDN?')
            return idntext
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    def output_on(self, channel, vol, curr):
        with self._lock:
            try:
                if channel > 3 or channel < 0:
                    return False
                else:
                    self.instrument.write(f"APPLy CH{channel!s},{vol!s}V,{curr!s}A")
                    self.instrument.write('OUTP ON')
                    return True
            except Exception as e:
                print(f"An error occurred: {e}")
                return False

    def output_off(self, channel):
        with self._lock:
            vol, curr = 0, 0
            try:
                if channel > 3 or channel < 0:
                    return False
                else:
                    self.instrument.write(f"APPLy CH{channel!s},{vol!s}V,{curr!s}A")
                    self.instrument.write('OUTP OFF')
                    return True
            except Exception as e:
                print(f"An error occurred: {e}")
                return False

    def read_current(self, channel):
        with self._lock:
            try:
                if channel > 3 or channel < 0:
                    return "-9999"
                else:
                    result = self.instrument.query(f"MEAS:CURR? CH{channel!s}").strip()
                    result = str(int(float(result) * 1000))
                    return result
            except Exception as e:
                print(f"An error occurred: {e}")
                return "-9999"

    def read_voltage(self, channel):
        with self._lock:
            try:
                if channel > 3 or channel < 0:
                    return "-9999"
                else:
                    result = self.instrument.query(f"MEAS:VOLt? CH{channel!s}").strip()
                    result = str(int(float(result) * 1000))
                    return result
            except Exception as e:
                print(f"An error occurred: {e}")
                return "-9999"

    def output_on_all(self, vol1, vol2, vol3, curr1, curr2, curr3):
        with self._lock:
            try:
                self.instrument.write(f"APP:VOLT {vol1!s},{vol2!s},{vol3!s}")
                self.instrument.write(f"APP:CURR {curr1!s},{curr2!s},{curr3!s}")
                self.instrument.write("OUTPut:ALL ON")
                return True
            except Exception as e:
                print(f"An error occurred: {e}")
                return False

    def output_off_all(self):
        with self._lock:
            vol1, vol2, vol3, curr1, curr2, curr3 = 0, 0, 0, 0, 0, 0
            try:
                self.instrument.write(f"APP:VOLT {vol1!s},{vol2!s},{vol3!s}")
                self.instrument.write(f"APP:CURR {curr1!s},{curr2!s},{curr3!s}")
                self.instrument.write("OUTPut:ALL OFF")
                return True
            except Exception as e:
                print(f"An error occurred: {e}")
                return False

    def close(self):
        try:
            if self.instrument:
                self.instrument.close()
                self.instrument = None
        except Exception as e:
            print(f"An error occurred: {e}")
