"""仪器访问层 — DMM/PS/Relay 的统一入口。

从 TestItem 裂变出来，职责单一：管理仪器访问路径。
- 优先使用直接注入的仪器（多通道模式每通道独立实例）
- 回退到 InstrumentManager 单例（单通道模式共享实例）
"""

from app.utils.logger import get_logger

logger = get_logger("InstrumentAccessor")


class InstrumentAccessor:
    """仪器访问门面 — DMM、程控电源、继电器板 的统一入口。

    构造参数:
        instrument_manager: InstrumentManager | None  单例管理器（回退用）
        dmm: KEYSIGHT_34970A | None    直接注入 DMM（多通道模式，优于 manager）
        ps: IT6382 | None              直接注入程控电源
        relay: RELAYBOARD | None       直接注入继电器板
    """

    def __init__(self, instrument_manager=None, *, dmm=None, ps=None, relay=None):
        self._mgr = instrument_manager  # 由调用方注入（向后兼容）
        self._injected_dmm = dmm  # 直接注入仪器（优先于 _mgr）
        self._injected_ps = ps
        self._injected_relay = relay
        self._scan_cache: dict[str, dict[str, float]] = {}

    # ═══════════════════════════════════════════════════════════════════════
    #  仪器访问属性 — 优先直接注入，回退到 _mgr
    # ═══════════════════════════════════════════════════════════════════════

    @property
    def _dmm(self):
        if self._injected_dmm is not None:
            return self._injected_dmm
        return self._mgr.dmm if self._mgr else None

    @property
    def _ps(self):
        if self._injected_ps is not None:
            return self._injected_ps
        return self._mgr.ps if self._mgr else None

    @property
    def _relay(self):
        if self._injected_relay is not None:
            return self._injected_relay
        return self._mgr.relay if self._mgr else None

    @property
    def _dmm_ok(self) -> bool:
        if self._injected_dmm is not None:
            return self._injected_dmm.is_connected
        return self._mgr.dmm_connected if self._mgr else False

    @property
    def _ps_ok(self) -> bool:
        if self._injected_ps is not None:
            return self._injected_ps.is_connected
        return self._mgr.ps_connected if self._mgr else False

    @property
    def _relay_ok(self) -> bool:
        if self._injected_relay is not None:
            return self._injected_relay.is_connected
        return self._mgr.relay_connected if self._mgr else False

    # ═══════════════════════════════════════════════════════════════════════
    #  批量扫描 — 数据存入 _scan_cache，供后续独立测量方法读取
    # ═══════════════════════════════════════════════════════════════════════

    def scan_resistance_slot1(self):
        """批量扫描 Slot 1 (101–120) 电阻值，结果缓存到 _scan_cache['resistance']"""
        if not self._dmm_ok:
            logger.info("34970A 未连接，无法扫描电阻")
            return "FAILED"
        channels = ",".join(str(i) for i in range(101, 121))
        result = self._dmm.scan_slot_res(channels)
        if result is None:
            logger.info("scan_resistance slot1 返回 None")
            return "FAILED"
        self._scan_cache["resistance"] = {str(k): v for k, v in result.items()}
        logger.info(f"slot1 电阻扫描完成: {len(self._scan_cache['resistance'])} 个通道")
        return "PASSED"

    def scan_resistance_slot2(self):
        """批量扫描 Slot 2 (201–217) 电阻值，合并到 _scan_cache['resistance']"""
        if not self._dmm_ok:
            logger.info("34970A 未连接，无法扫描电阻")
            return "FAILED"
        channels = ",".join(str(i) for i in range(201, 218))
        result = self._dmm.scan_slot_res(channels)
        if result is None:
            logger.info("scan_resistance slot2 返回 None")
            return "FAILED"
        cache = self._scan_cache.setdefault("resistance", {})
        cache.update({str(k): v for k, v in result.items()})
        logger.info(f"slot2 电阻扫描完成: {len(result)} 个通道")
        return "PASSED"

    def scan_voltage(self):
        """批量扫描 Slot 1 (101–109) 直流电压 (mV)，结果缓存到 _scan_cache['voltage']"""
        if not self._dmm_ok:
            logger.info("34970A 未连接，无法扫描电压")
            return "FAILED"
        channels = ",".join(str(i) for i in range(101, 110))
        result = self._dmm.scan_slot_dcv(channels, unit="mV")
        if result is None:
            logger.info("scan_voltage 返回 None")
            return "FAILED"
        self._scan_cache["voltage"] = {str(k): v for k, v in result.items()}
        logger.info(f"电压扫描完成: {len(self._scan_cache['voltage'])} 个通道")
        return "PASSED"

    # ═══════════════════════════════════════════════════════════════════════
    #  单点测量 — 直接通过 DMM（不走缓存）
    # ═══════════════════════════════════════════════════════════════════════

    def _get_resistance(self, channel: str):
        """直接通过 DMM 测量单通道阻抗（MEAS:RES? 一键完成，不走缓存）。"""
        dmm = self._dmm
        if dmm is None:
            logger.info(f"DMM 未连接，ch{channel} 返回 -9999")
            return "-9999"
        val = dmm.measure_res(int(channel))
        logger.info(f"[RAW] 阻抗 ch{channel} = {val} Ω")
        return val

    def _get_voltage(self, channel: str):
        """直接通过 DMM 测量单通道直流电压 (mV)（不走缓存）。"""
        dmm = self._dmm
        if dmm is None:
            logger.info(f"DMM 未连接，ch{channel} 返回 -9999")
            return "-9999"
        val = dmm.measure_dcv(int(channel), unit="mV")
        if val is not None:
            logger.info(f"[RAW] 电压 ch{channel} = {val} mV")
            return str(val)
        return "-9999"

    # ═══════════════════════════════════════════════════════════════════════
    #  继电器控制
    # ═══════════════════════════════════════════════════════════════════════

    def relay_ON(self, channel: int):
        """闭合指定继电器通道 (1–8)"""
        if not self._relay_ok:
            logger.info("Relayboard 未连接")
            return "FAILED"
        self._relay.relay_ON(channel)
        return "PASSED"

    def relay_OFF(self, channel: int):
        """断开指定继电器通道 (1–8)"""
        if not self._relay_ok:
            logger.info("Relayboard 未连接")
            return "FAILED"
        self._relay.relay_OFF(channel)
        return "PASSED"

    def relay_on_range(self, start: int, end: int):
        """闭合指定范围继电器 (含两端)"""
        if not self._relay_ok:
            logger.info("Relayboard 未连接")
            return "FAILED"
        self._relay.turn_on_relays(range(start, end + 1))
        return "PASSED"

    def relay_off_range(self, start: int, end: int):
        """断开指定范围继电器 (含两端)"""
        if not self._relay_ok:
            logger.info("Relayboard 未连接")
            return "FAILED"
        self._relay.turn_off_relays(range(start, end + 1))
        return "PASSED"

    def relay_on_all(self):
        """闭合全部 8 路继电器"""
        return self.relay_on_range(1, 8)

    def relay_off_all(self):
        """断开全部 8 路继电器"""
        return self.relay_off_range(1, 8)

    # ═══════════════════════════════════════════════════════════════════════
    #  程控电源 IT6382
    # ═══════════════════════════════════════════════════════════════════════

    def ps_output_on_all(
        self,
        vol1: float = 0,
        vol2: float = 0,
        vol3: float = 0,
        curr1: float = 0,
        curr2: float = 0,
        curr3: float = 0,
    ):
        """三通道同时输出。参数: CH1/CH2/CH3 电压(V) + 电流(A)"""
        if not self._ps_ok:
            logger.info("IT6382 未连接")
            return "FAILED"
        self._ps.output_on_all(vol1, vol2, vol3, curr1, curr2, curr3)
        return "PASSED"

    def ps_output_off_all(self):
        """三通道同时关闭"""
        if not self._ps_ok:
            logger.info("IT6382 未连接")
            return "FAILED"
        self._ps.output_off_all()
        return "PASSED"

    def ps_output_on(self, channel: int, vol: float, curr: float):
        """单通道输出。channel: 1/2/3"""
        if not self._ps_ok:
            logger.info("IT6382 未连接")
            return "FAILED"
        self._ps.output_on(channel, vol, curr)
        return "PASSED"

    def ps_output_off(self, channel: int):
        """单通道关闭"""
        if not self._ps_ok:
            logger.info("IT6382 未连接")
            return "FAILED"
        self._ps.output_off(channel)
        return "PASSED"

    def ps_read_voltage(self, channel: int):
        """读取指定通道电压 (mV)"""
        if not self._ps_ok:
            return "-9999"
        return self._ps.read_voltage(channel)

    def ps_read_current(self, channel: int):
        """读取指定通道电流 (mA)"""
        if not self._ps_ok:
            return "-9999"
        return self._ps.read_current(channel)
