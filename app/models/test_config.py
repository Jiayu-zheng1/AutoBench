"""Test configuration model — CSV row parsing and validation."""
from app.models.test_plan import TestStep
from app.utils.logger import get_logger

logger = get_logger("Config")


class TestConfig:
    """Parsed state from a Limits.csv row.

    Fields:
        test_name:      测试分组名（新增列，如 "Impedance Check"）
        function:       对应 TestItem 的方法名（原 TestName）
        sub_test_name:  表格显示名（原 TestItem）
    """

    def __init__(self, test_name: str, function: str, sub_test_name: str,
                 lower_limit: str, upper_limit: str, config: dict, unit: str = ""):
        self.test_name = test_name                # 测试分组名
        self.function = function                  # TestItem 方法名
        self.sub_test_name = sub_test_name        # 表格显示名
        self.lower_limit_raw = lower_limit
        self.upper_limit_raw = upper_limit
        self.config = config
        self.unit = unit                          # 单位 (Ω / mV / 空)

    @property
    def lower_limit(self):
        return _limit_format(self.lower_limit_raw)

    @property
    def upper_limit(self):
        return _limit_format(self.upper_limit_raw)

    def is_special_limit(self):
        specials = {"No Empty", "Empty", "True", "ON", "PASSED", "EQUAL"}
        return self.lower_limit_raw in specials or self.upper_limit_raw in specials

    def evaluate(self, value) -> tuple[bool, str]:
        """判定 value 是否在 limit 范围内。

        返回 (是否通过, Pass/Fail 标签)。
        特殊 limit：
        - No Empty：检查 value 非空
        - PASSED/ON/True：检查是否有失败标志（FAILED/False/None）
        - EQUAL：字符串精确匹配 (忽略大小写)
        数值 limit：统一转 float 做 <= 比较。
        非数值非特殊的 hex 串 → 字符串精确匹配。
        """
        if self.is_special_limit():
            specials = {self.lower_limit_raw, self.upper_limit_raw}
            if "No Empty" in specials or "Empty" in specials:
                ok = bool(value)
                return ok, "Pass" if ok else "Fail"

            # EQUAL → 字符串精确匹配（hex值比较用）
            if "EQUAL" in specials:
                expected = self.upper_limit_raw if self.lower_limit_raw == "EQUAL" else self.lower_limit_raw
                ok = str(value).strip().upper() == str(expected).strip().upper()
                return ok, "Pass" if ok else "Fail"

            # PASSED / ON / True → 检查是否有失败标志
            if value is None:
                return False, "Fail"
            # 显式失败标志
            value_str = str(value).strip().upper()
            if value_str in ("FAILED", "FAIL", "ERROR", "FALSE", "0"):
                return False, "Fail"
            # 布尔值 False
            if value is False:
                return False, "Fail"
            # 其他情况（包括原始响应、PASSED、True 等）视为 Pass
            return True, "Pass"

        # ── 尝试数值比较 ──
        try:
            val = float(value)
            lo = float(self.lower_limit)
            if self.upper_limit_raw.strip() == "":
                passed = lo <= val
            else:
                hi = float(self.upper_limit)
                passed = lo <= val <= hi
            return passed, "Pass" if passed else "Fail"
        except (ValueError, TypeError):
            pass

        # ── 非数值非特殊 → hex/字符串精确匹配 ──
        if self.lower_limit_raw.strip():
            ok = str(value).strip().upper() == self.lower_limit_raw.strip().upper()
            return ok, "Pass" if ok else "Fail"

        # ── 无 limit → 有返回值即 Pass，None 则 Fail ──
        if value is not None and str(value).strip() and str(value).strip().upper() != "NONE":
            return True, "Pass"
        return False, "Fail"


def load_test_configs(csv_rows: list[TestStep]) -> list[TestConfig]:
    """Parse TestStep list into TestConfig list, filtering Running='Y'."""
    configs = []
    for row in csv_rows:
        if row.get("Running", "") != "Y":
            continue
        configs.append(TestConfig(
            test_name=row.get("TestName", ""),
            function=row.get("Function", "") or row.get("SubTestName", ""),
            sub_test_name=row.get("SubTestName", ""),
            lower_limit=row.get("LowerLimit", ""),
            upper_limit=row.get("UpperLimit", ""),
            config=row.get("config", {}),
            unit=row.get("Unit", ""),
        ))
    return configs


def _limit_format(limit: str):
    if limit in ("No Empty", "Empty", "True", "PASSED", "ON"):
        return limit
    if limit.startswith("0x"):
        return limit
    try:
        return int(limit)
    except (ValueError, TypeError):
        return limit
