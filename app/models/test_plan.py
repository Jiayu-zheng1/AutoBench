"""测试计划数据模型 — TestStep + TestPlan 替代裸 dict 数据流。

用法:
    from app.utils.limits_loader import load_test_data
    plan = load_test_data()
    for step in plan.active_steps:
        print(step.sub_test_name, step.lower_limit)

向后兼容:
    TestStep 实现了 .get() 和 [] 接口，现有 row.get("Running","") 代码无需修改。
"""

from dataclasses import dataclass, field
from typing import Any

# ── CSV 列名 → dataclass 属性名 ──
_FIELD_MAP: dict[str, str] = {
    "TestName":    "test_name",
    "Function":    "function",
    "SubTestName": "sub_test_name",
    "Running":     "running",
    "config":      "config",
    "LowerLimit":  "lower_limit",
    "UpperLimit":  "upper_limit",
    "Unit":        "unit",
    "Visible":     "visible",
}


@dataclass
class TestStep:
    """单条测试步骤 — 对应 Main.csv 一行 + Limits.csv 合并后的完整数据。

    CSV 列名映射:
        TestName    → test_name      测试分组名
        Function    → function       TestItem 方法名
        SubTestName → sub_test_name  表格显示名
        Running     → running        Y/N 是否执行
        config      → config         已解析的配置 dict
        LowerLimit  → lower_limit    判据下限
        UpperLimit  → upper_limit    判据上限
        Unit        → unit           单位 (Ω/mV等)
        Visible     → visible        Y/N 是否在 UI 显示 limits
    """
    test_name: str = ""
    function: str = ""
    sub_test_name: str = ""
    running: str = "Y"
    config: dict[str, Any] = field(default_factory=dict)
    lower_limit: str = ""
    upper_limit: str = ""
    unit: str = ""
    visible: str = "Y"

    # ── 向后兼容：dict 接口 ──

    def get(self, key: str, default: Any = None) -> Any:
        """dict-like .get() — 使 row.get('Running','') 等代码无需修改。"""
        attr = _FIELD_MAP.get(key)
        if attr is not None:
            return getattr(self, attr)
        return default

    def __getitem__(self, key: str) -> Any:
        """dict-like [] 访问。"""
        attr = _FIELD_MAP.get(key)
        if attr is not None:
            return getattr(self, attr)
        raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        return key in _FIELD_MAP

    # ── 显式转换 ──

    def to_row_dict(self) -> dict[str, Any]:
        """显式转回裸 dict — 未迁移代码的逃生舱。"""
        return {
            "TestName": self.test_name,
            "Function": self.function,
            "SubTestName": self.sub_test_name,
            "Running": self.running,
            "config": self.config,
            "LowerLimit": self.lower_limit,
            "UpperLimit": self.upper_limit,
            "Unit": self.unit,
            "Visible": self.visible,
        }

    @classmethod
    def from_row_dict(cls, d: dict[str, Any]) -> "TestStep":
        """从 legacy 裸 dict 构造 TestStep。"""
        return cls(
            test_name=d.get("TestName", ""),
            function=d.get("Function", ""),
            sub_test_name=d.get("SubTestName", ""),
            running=d.get("Running", "Y"),
            config=d.get("config", {}),
            lower_limit=d.get("LowerLimit", ""),
            upper_limit=d.get("UpperLimit", ""),
            unit=d.get("Unit", ""),
            visible=d.get("Visible", "Y"),
        )


@dataclass
class TestPlan:
    """测试计划 — 替代 (headers, rows) 元组。

    Attributes:
        headers: 表格显示的列名（已排除 Running/config/Visible 等隐藏列）
        steps:   所有测试步骤
    """
    headers: list[str] = field(default_factory=list)
    steps: list[TestStep] = field(default_factory=list)

    @property
    def active_steps(self) -> list[TestStep]:
        """Running='Y' 的步骤（过滤后）。"""
        return [s for s in self.steps if s.running == "Y"]

    def to_legacy(self) -> tuple[list[str], list[dict[str, Any]]]:
        """转回 (headers, rows) 元组 — 向后兼容逃生舱。"""
        return self.headers, [s.to_row_dict() for s in self.steps]

    @classmethod
    def from_legacy(cls, headers: list[str], rows: list[dict[str, Any]]) -> "TestPlan":
        """从旧格式 (headers, rows) 构造 TestPlan。"""
        return cls(headers=headers, steps=[TestStep.from_row_dict(r) for r in rows])
