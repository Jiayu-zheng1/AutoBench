"""BaseTestRunner — 测试执行引擎基类，提供 _run_one / _evaluate_result 公共实现。

子类:
    TestRunner  — 单通道，SFC/CSV
    ChannelRunner — 多通道，通道日志/串口定位
"""

from PySide6.QtCore import QThread

from app.utils.logger import get_logger

logger = get_logger("BaseRunner")


class BaseTestRunner(QThread):
    """测试执行引擎基类。

    子类需提供的属性:
        self.test_unit: TestItem   — 测试业务对象
        self._test_status: bool    — 当前测试是否通过
        self._last_value: Any      — 上一次测量值（可选）

    子类需重写的钩子方法:
        _emit_value(test_item, value)     — 发射测量值信号
        _emit_result(test_item, label)    — 发射 Pass/Fail 信号
        _emit_color(test_item, color)     — 发射行颜色信号
        _log(msg: str)                    — 日志输出
    """

    # ── 子类必须实现 ──

    def _emit_value(self, test_item: str, value: str):
        raise NotImplementedError

    def _emit_result(self, test_item: str, label: str):
        raise NotImplementedError

    def _emit_color(self, test_item: str, color: str):
        raise NotImplementedError

    def _log(self, msg: str):
        logger.info(msg)

    # ── 公共实现 ──

    def _run_one(self, display: str, method: str, config: dict):
        """统一分发：config 驱动 / 反射调用 TestItem 方法。"""
        # self._log(f'<span style="font-size:20px; font-weight:700;">Start Run [{method}]</span>')
        # ── config 驱动路径 ──
        if method == "Read_ASCII_CMD":
            raw_hex, ascii_str, value = self.test_unit.Read_ASCII_CMD(method, config)
        elif method == "Read_HEX_CMD":
            raw_hex, ascii_str, value = self.test_unit.Read_HEX_CMD(method, config)
        elif method == "Read_IMPEDANCE":
            raw_hex, ascii_str, value = self.test_unit.Read_IMPEDANCE(method, config)
        elif method == "Read_VOLTAGE":
            raw_hex, ascii_str, value = self.test_unit.Read_VOLTAGE(method, config)
        elif config:
            # 旧格式兼容：有 config 但 method 不是标准名
            raw_hex, ascii_str, value = self.test_unit.Read_ASCII_CMD(method, config)
        elif hasattr(self.test_unit, method):
            test_function = getattr(self.test_unit, method)
            value = test_function()
            raw_hex, ascii_str = "", ""
        else:
            self._log(f"No config and no method '{method}' — skipping")
            value = None
            raw_hex, ascii_str = "", ""

        if config.get("hex_cmd") and raw_hex:
            self._log(f"[{display}] raw: {raw_hex} | ascii: {ascii_str}")

        self._last_value = value
        return value

    def _evaluate_result(self, test_item: str, value: str, cfg):
        """判定结果并发射信号。

        Value列显示规则:
        - PASSED类型 → 显示 PASSED/FAILED
        - 有上下限   → 显示正则提取后的原始值
        - 空limits   → 显示原始值 / None
        """
        passed, label = cfg.evaluate(value)
        # 确定 Value 列显示内容
        if cfg.is_special_limit() and "PASSED" in {
            cfg.lower_limit_raw,
            cfg.upper_limit_raw,
        }:
            display_value = "PASSED" if passed else "FAILED"
        else:
            display_value = value
        self._emit_value(test_item, display_value)
        self._emit_result(test_item, label)
        self._emit_color(test_item, label)
        if not passed:
            self._test_status = False
