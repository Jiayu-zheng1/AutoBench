"""通用测量引擎 — Read_ASCII_CMD / Read_HEX_CMD / Read_IMPEDANCE / Read_VOLTAGE。

从 TestItem 裂变出来，职责单一：按 config 执行测量/指令，提取返回值。
- 不直接持有 dut 引用 — 通过 DutCommunicator 访问
- 不直接操作仪器 — 通过 InstrumentAccessor 访问
- set_attr 回调机制 — 通过 _setattr_target 回写 DUT 标识属性
"""

import re
from typing import Any

from app.utils.logger import get_logger

logger = get_logger("MeasurementEngine")


class MeasurementEngine:
    """通用测量引擎 — config 驱动的 DUT 指令执行 + 仪器测量 + 值提取。

    依赖（构造注入）:
        dut_comm: DutCommunicator     — 提供 dut (Device) 访问 + FGSN/MLBSN 回写
        instruments: InstrumentAccessor — 提供 _get_resistance / _get_voltage

    _setattr_target:  set_attr 配置的回写目标（由 TestItem 设为自身）
    """

    def __init__(self, dut_comm, instruments):
        self._dut_comm = dut_comm
        self._instruments = instruments
        self._setattr_target: Any = None  # TestItem 实例，供 set_attr 回写

    # ── 4个通用测量方法 ─────────────────────────────────────────────────

    def Read_ASCII_CMD(self, method_name: str, config: dict) -> tuple[str, str, Any]:
        """按 config 执行测试，method_name 为 TestName（匹配 TestItem 方法）。
        返回 (raw_hex, ascii_str, result) 元组。

        支持两种 config 格式：
        - 旧格式: {"hex_cmd": "055A...", "regex": "pat", "group": "1"}
        - 新格式: {"action": "hex_cmd", "args": ["055A...", "pat", "1", "1"]}
        """
        action = config.get("action", "")
        new_args = config.get("args", [])

        # ── action dispatch ──
        if action == "method":
            target = new_args[0] if new_args else (config.get("method") or method_name)
            extra = new_args[1:] if len(new_args) > 1 else []
            if extra:
                return "", "", getattr(self._setattr_target, target)(*extra)
            return "", "", getattr(self._setattr_target, target)()

        if action == "connect":
            return "", "", "PASSED" if self._dut_comm.connent_dut() else "FAILED"

        # ── 新格式 args → 旧格式 config dict 兼容 ──
        config = dict(config)  # 不污染原始 config
        if action in ("hex_cmd", "cmd") and new_args:
            config.setdefault(action, new_args[0])
            if len(new_args) > 1:
                config.setdefault("regex", new_args[1])
            if len(new_args) > 2:
                config.setdefault("group", new_args[2])
            if len(new_args) > 3:
                config.setdefault("delay", new_args[3])

        # ── 通用 config 处理器（旧格式和新格式都走这里）──

        # DUT 未连接时直接返回空值，不 crash
        if self._dut_comm.dut is None:
            logger.info(f"{method_name}: DUT 未连接，返回 None")
            return "", "", None

        for cmd in self._as_list(config.get("pre_cmds")):
            self._dut_comm.dut.send_cmd(cmd)

        hex_cmd = config.get("hex_cmd")
        if hex_cmd:
            delay = float(config.get("delay", 0.1))
            raw_hex, data = self._dut_comm.dut.send_hex_cmd(hex_cmd, delay=delay)
            logger.info(f"{method_name} raw response: {data}")
        else:
            cmd = (
                config.get("cmd") or config.get("command") or config.get("instruction")
            )
            data = self._dut_comm.dut.read_Write(cmd) if cmd else ""
            raw_hex = ""

        result = self._extract_config_value(data, config)

        for attr in self._as_list(config.get("set_attr")):
            if self._setattr_target is not None:
                setattr(self._setattr_target, attr, result)

        for cmd in self._as_list(config.get("post_cmds")):
            self._dut_comm.dut.send_cmd(cmd)

        logger.info(f"{method_name} config result: {result}")
        return raw_hex, data, result

    def Read_HEX_CMD(self, method_name: str, config: dict) -> tuple[str, str, Any]:
        """发送 hex 指令，只返回 raw hex 值（不做 ASCII 解码和正则提取）。

        与 Read_ASCII_CMD 的区别：
        - Read_ASCII_CMD → 返回 ASCII 解码后 + 正则提取的值
        - Read_HEX_CMD   → 返回原始 hex 字符串，直接用于 contains / regex 判定
        """
        if self._dut_comm.dut is None:
            logger.info(f"{method_name}: DUT 未连接，返回 None")
            return "", "", None

        hex_cmd = config.get("hex_cmd")
        if not hex_cmd:
            logger.info("Read_HEX_CMD: config 中无 hex_cmd")
            return "", "", None

        delay = float(config.get("delay", 0.05))
        raw_hex, ascii_str = self._dut_comm.dut.send_hex_cmd(hex_cmd, delay=delay)
        logger.info(f"Read_HEX_CMD raw hex: {raw_hex}")

        result = self._extract_config_value(raw_hex, config)
        logger.info(f"Read_HEX_CMD config result: {result}")
        return raw_hex, ascii_str, result

    def Read_IMPEDANCE(self, method_name: str, config: dict) -> tuple[str, str, Any]:
        """通用阻抗测量 — config 指定 channel，从 DMM 直读阻抗值。

        config: {'channel': '101'}
        """
        channel = config.get("channel", "")
        if not channel:
            logger.info("Read_IMPEDANCE: config 中无 channel")
            return "", "", "-9999"

        val = self._instruments._get_resistance(str(channel))
        logger.info(f"Read_IMPEDANCE ch{channel}: {val} Ω")
        return "", str(val), val

    def Read_VOLTAGE(self, method_name: str, config: dict) -> tuple[str, str, Any]:
        """通用电压测量 — config 指定 channel，从 DMM 直读电压值 (mV)。

        config: {'channel': '101'}
        """
        channel = config.get("channel", "")
        if not channel:
            logger.info("Read_VOLTAGE: config 中无 channel")
            return "", "", "-9999"

        val = self._instruments._get_voltage(str(channel))
        logger.info(f"Read_VOLTAGE ch{channel}: {val} mV")
        return "", str(val), val

    # ── 配置值提取 ─────────────────────────────────────────────────

    def _extract_config_value(self, data, config):
        if data is None:
            return None

        contains = config.get("contains")
        if contains:
            pass_value = config.get("pass_value", "PASSED")
            fail_value = config.get("fail_value", "FAILED")
            return pass_value if str(contains) in data else fail_value

        regex = config.get("regex")
        if not regex:
            return self._format_config_value(data, config)

        matches = list(re.finditer(regex, data, re.DOTALL))
        if not matches:
            logger.info(f"regex no match: {regex}")
            return config.get("default")

        match_index = int(config.get("match_index", config.get("index", 0)))
        match = matches[match_index]
        groups = config.get("group")
        if groups:
            if isinstance(groups, list):
                value = [match.group(int(group)) for group in groups]
            else:
                value = match.group(int(groups))
        else:
            group = int(config.get("group", config.get("position", 1)))
            value = match.group(group)
        return self._format_config_value(value, config)

    def _format_config_value(self, value, config):
        if isinstance(value, str) and config.get("strip", True):
            value = value.strip()

        cast = config.get("cast", "str")
        if cast == "int":
            return int(value)
        if cast == "float":
            return float(value)
        if cast == "hex_int":
            return int(value, 16)
        return value

    def _as_list(self, value):
        if not value:
            return []
        if isinstance(value, list):
            return value
        return [value]
