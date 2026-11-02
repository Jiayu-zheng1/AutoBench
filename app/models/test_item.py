"""TestItem 门面 — 组合 DutCommunicator + InstrumentAccessor + MeasurementEngine。

对外 API 不变：所有公开方法/属性通过委托暴露，外部调用方零改动。
领域专属 DUT 测试方法保留在此类中。
"""

import re
import subprocess as sub
import time

from app.models.dut_communicator import DutCommunicator
from app.models.instrument_accessor import InstrumentAccessor
from app.models.measurement_engine import MeasurementEngine
from app.utils.logger import get_logger

logger = get_logger("DUT")


class TestItem:
    """测试项门面 — 组合 DutCommunicator + InstrumentAccessor + MeasurementEngine。

    职责：
        DutCommunicator    — DUT 串口连接/断开/检查
        InstrumentAccessor — 仪器访问（DMM/PS/Relay 统一入口）
        MeasurementEngine  — 4个通用测量方法（Read_ASCII_CMD 等）
        TestItem 自身        — 领域专属 DUT 测试方法
    """

    def __init__(self, instrument_manager=None, *, dmm=None, ps=None, relay=None):
        self._dut_comm = DutCommunicator()
        self._instruments = InstrumentAccessor(
            instrument_manager, dmm=dmm, ps=ps, relay=relay
        )
        self._measurement = MeasurementEngine(self._dut_comm, self._instruments)
        self._measurement._setattr_target = self  # set_attr 回写到 TestItem

    # ═══════════════════════════════════════════════════════════════════════
    #  DutCommunicator 属性委托
    # ═══════════════════════════════════════════════════════════════════════

    @property
    def dut(self):
        return self._dut_comm.dut

    @dut.setter
    def dut(self, value):
        self._dut_comm.dut = value

    @property
    def ScanSN(self):
        return self._dut_comm.ScanSN

    @ScanSN.setter
    def ScanSN(self, value):
        self._dut_comm.ScanSN = value

    @property
    def FGSN(self):
        return self._dut_comm.FGSN

    @FGSN.setter
    def FGSN(self, value):
        self._dut_comm.FGSN = value

    @property
    def MLBSN(self):
        return self._dut_comm.MLBSN

    @MLBSN.setter
    def MLBSN(self, value):
        self._dut_comm.MLBSN = value

    @property
    def _dut_port(self):
        return self._dut_comm._dut_port

    @_dut_port.setter
    def _dut_port(self, value):
        self._dut_comm._dut_port = value

    # ── DutCommunicator 方法委托 ──

    def connent_dut(self, timeout=5):
        return self._dut_comm.connent_dut(timeout)

    def close_dut(self):
        self._dut_comm.close_dut()

    def Info_CheckDUT(self):
        return self._dut_comm.Info_CheckDUT()

    # ═══════════════════════════════════════════════════════════════════════
    #  MeasurementEngine 方法委托
    # ═══════════════════════════════════════════════════════════════════════

    def Read_ASCII_CMD(self, method_name, config):
        return self._measurement.Read_ASCII_CMD(method_name, config)

    def Read_HEX_CMD(self, method_name, config):
        return self._measurement.Read_HEX_CMD(method_name, config)

    def Read_IMPEDANCE(self, method_name, config):
        # return "PASS"
        return self._measurement.Read_IMPEDANCE(method_name, config)

    def Read_VOLTAGE(self, method_name, config):
        # return "PASS"
        return self._measurement.Read_VOLTAGE(method_name, config)

    # ═══════════════════════════════════════════════════════════════════════
    #  InstrumentAccessor 属性委托
    # ═══════════════════════════════════════════════════════════════════════

    @property
    def _dmm(self):
        return self._instruments._dmm

    @property
    def _ps(self):
        return self._instruments._ps

    @property
    def _relay(self):
        return self._instruments._relay

    @property
    def _dmm_ok(self) -> bool:
        return self._instruments._dmm_ok

    @property
    def _ps_ok(self) -> bool:
        return self._instruments._ps_ok

    @property
    def _relay_ok(self) -> bool:
        return self._instruments._relay_ok

    # ── InstrumentAccessor 方法委托 ──

    def scan_resistance_slot1(self):
        return self._instruments.scan_resistance_slot1()

    def scan_resistance_slot2(self):
        return self._instruments.scan_resistance_slot2()

    def scan_voltage(self):
        return self._instruments.scan_voltage()

    def _get_resistance(self, channel: str):
        return self._instruments._get_resistance(channel)

    def _get_voltage(self, channel: str):
        return self._instruments._get_voltage(channel)

    def relay_ON(self, channel: int):
        return self._instruments.relay_ON(channel)

    def relay_OFF(self, channel: int):
        return self._instruments.relay_OFF(channel)

    def relay_on_range(self, start: int, end: int):
        return self._instruments.relay_on_range(start, end)

    def relay_off_range(self, start: int, end: int):
        return self._instruments.relay_off_range(start, end)

    def relay_on_all(self):
        return self._instruments.relay_on_all()

    def relay_off_all(self):
        return self._instruments.relay_off_all()

    def ps_output_on_all(
        self,
        vol1: float = 0,
        vol2: float = 0,
        vol3: float = 0,
        curr1: float = 0,
        curr2: float = 0,
        curr3: float = 0,
    ):
        return self._instruments.ps_output_on_all(vol1, vol2, vol3, curr1, curr2, curr3)

    def ps_output_off_all(self):
        return self._instruments.ps_output_off_all()

    def ps_output_on(self, channel: int, vol: float, curr: float):
        return self._instruments.ps_output_on(channel, vol, curr)

    def ps_output_off(self, channel: int):
        return self._instruments.ps_output_off(channel)

    def ps_read_voltage(self, channel: int):
        return self._instruments.ps_read_voltage(channel)

    def ps_read_current(self, channel: int):
        return self._instruments.ps_read_current(channel)

    # ═══════════════════════════════════════════════════════════════════════
    #  领域专属 DUT 测试方法（保留在 TestItem 中，通过属性委托访问 dut 和仪器）
    # ═══════════════════════════════════════════════════════════════════════

    def Enable_HWID(self):
        """启用 HWID 显示（某些机型默认隐藏）"""
        if self.dut is None:
            logger.info("DUT 未连接，无法启用 HWID")
            return "FAILED"
        hex_data, ASCII_data = self.dut.send_hex_cmd(
            "055A2600920F41542B454750494F3D4750494F5F5345545F414C4C3A33392C302C312C312C322C300D0A",
            delay=0.05,
        )
        logger.info(f"Enable_HWID raw response: {ASCII_data}")
        if "di=1" in ASCII_data:
            logger.info("HWID 显示已启用")
            return "PASSED"
        else:
            logger.info("启用 HWID 失败")
            return "FAILED"

    def Disable_HWID(self):
        """禁用 HWID 显示（某些机型默认显示）"""
        if self.dut is None:
            logger.info("DUT 未连接，无法禁用 HWID")
            return "FAILED"
        hexdata, ASCII_data = self.dut.send_hex_cmd(
            "055A2600920F41542B454750494F3D4750494F5F5345545F414C4C3A33392C302C312C302C322C300D0A",
            delay=0.05,
        )
        logger.info(f"Disable_HWID raw response: {ASCII_data}")
        if "di=0" in ASCII_data:
            logger.info("HWID 显示已禁用")
            return "PASSED"
        else:
            logger.info("禁用 HWID 失败")
            return "FAILED"

    def Check_R_L_board(self):
        if self.dut is None:
            logger.info("DUT 未连接")
            return None
        hexdata, ASCII_data = self.dut.send_hex_cmd(
            "055a06001080534944450D0A",
            delay=0.05,
        )
        L_R_Board = hexdata[-2:]
        if L_R_Board == "01":
            return "R"
        elif L_R_Board == "02":
            return "L"
        logger.info(
            f"Check_R_L_board raw response: {ASCII_data}, L_R_Board={L_R_Board}"
        )
        return L_R_Board

    # ═══════════════════════════════════════════════════════════════════════
    #  USB-C 端口就绪检查 (J174)
    # ═══════════════════════════════════════════════════════════════════════

    def Check_USB_Ready(self, timeout=5.0):
        """检查 USB-C 串口配对是否就绪（usbmodem*01 + usbmodem*03 同号成对）。

        对标 Lua checkUSBReady：ls /dev/cu.* → 匹配 usbmodem*01 + usbmodem*03 同号配对。
        累积 3 次稳定就绪后返回 PASSED，超时返回 FAILED。

        Args:
            timeout: 超时时间 (秒)

        Returns:
            "PASSED" | "FAILED"
        """
        logger.info(f"Check_USB_Ready: 开始检测 USB-C 端口配对 (timeout={timeout}s)")
        is_ready = 0
        start_time = time.time()
        while time.time() - start_time <= float(timeout):
            result = sub.run(
                "ls /dev/cu.*",
                shell=True,
                capture_output=True,
                text=True,
            )
            output = result.stdout

            # 搜所有 usbmodem*01 → 提取编号，检查同编号 03 是否存在
            for m in re.finditer(r"usbmodem(\d+)01", output):
                num = m.group(1)
                if f"usbmodem{num}03" in output:
                    is_ready += 1
                    logger.info(
                        f"Check_USB_Ready: 配对就绪 usbmodem{num}01/03 ({is_ready}/3)"
                    )
                    break  # 有一对就够

            if is_ready >= 3:
                logger.info("Check_USB_Ready PASSED: USB-C 端口配对已稳定")
                return "PASSED"
            time.sleep(0.2)

        logger.info("Check_USB_Ready FAILED: 超时未检测到 USB-C 端口配对")
        return "FAILED"

    # ═══════════════════════════════════════════════════════════════════════
    #  Fixture 初始化 / 收尾
    # ═══════════════════════════════════════════════════════════════════════

    def Fixture_init(self):
        """Fixture 初始化：关闭所有电源输出 + DMM 清错 + 断开全部继电器"""
        try:
            if self._ps_ok:
                self._ps.output_off_all()
            if self._dmm_ok:
                self._dmm.set_DMMcls()
            if self._relay_ok:
                self._relay.turn_off_relays(range(1, 9))
            return "PASSED"
        except Exception as e:
            logger.info(f"Fixture_init 异常: {e}")
            return "FAILED"

    def Finished(self):
        """测试完成收尾：关闭所有电源 + DMM 清错 + 断开全部继电器"""
        try:
            if self._ps_ok:
                self._ps.output_off_all()
            if self._dmm_ok:
                self._dmm.set_DMMcls()
            if self._relay_ok:
                self._relay.turn_off_relays(range(1, 9))
            return True
        except Exception as e:
            logger.info(f"Finished 异常: {e}")
            return False
