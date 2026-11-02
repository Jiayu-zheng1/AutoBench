"""双 CSV 加载器 — Main.csv(测试序列) + Limits.csv(判据) 按 SubTestName 合并。

用法:
    from app.utils.limits_loader import load_test_data
    plan = load_test_data()
    for step in plan.active_steps:
        print(step.sub_test_name, step.lower_limit)
"""

import csv
import os

from app.models.test_plan import TestPlan, TestStep
from app.utils.config_parser import parse_config
from app.utils.constants import LIMITS_CSV, MAIN_CSV


class LimitsLoader:
    def __init__(self, logger):
        self.logger = logger

    def load_limits_map(self) -> dict[str, dict]:
        """加载 Limits.csv → {SubTestName: {LowerLimit, UpperLimit, Unit, Visible}}"""
        limits = {}
        if not os.path.exists(LIMITS_CSV):
            return limits
        with open(LIMITS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sub = row.get("SubTestName", "").strip()
                if sub:
                    if sub in limits:
                        self.logger.warning(
                            f"Limits.csv 重复 SubTestName '{sub}' — 后出现的行将覆盖之前的限制值"
                        )
                    limits[sub] = {
                        "LowerLimit": row.get("LowerLimit", "").strip(),
                        "UpperLimit": row.get("UpperLimit", "").strip(),
                        "Unit": row.get("Unit", "").strip(),
                        "Visible": row.get("Visible", "Y").strip(),
                    }
                    self.logger.debug(f"Loaded limits for '{sub}': {limits[sub]}")
        return limits

    def load_test_data(self) -> TestPlan:
        """加载 Main.csv + Limits.csv，合并后返回 TestPlan。

        Main.csv:  TestName, Function, SubTestName, Running, config
        Limits.csv:SubTestName, LowerLimit, UpperLimit, Unit, Visible

        返回 TestPlan(headers=显示列, steps=[TestStep, ...])
        TestStep 支持 .get() dict兼容接口，调用方无需大改。
        """
        if not os.path.exists(MAIN_CSV):
            self.logger.error(f"Main.csv not found: {MAIN_CSV}")
            return TestPlan()

        limits_map = self.load_limits_map()

        with open(MAIN_CSV, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            return TestPlan()

        raw_headers = [h.strip() for h in lines[0].strip().split(",")]
        config_idx = raw_headers.index("config") if "config" in raw_headers else -1
        if config_idx < 0:
            return TestPlan()

        steps = []
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",", config_idx)
            if len(parts) < config_idx + 1:
                parts.extend([""] * (config_idx + 1 - len(parts)))

            row = {}
            for i in range(config_idx):
                row[raw_headers[i]] = parts[i].strip()
            config_text = parts[config_idx].strip().rstrip(",")
            row["config"] = parse_config(config_text)

            # ── 按 SubTestName 合并 Limits ──
            sub = row.get("SubTestName", "")
            limits = limits_map.get(sub, {})
            row["LowerLimit"] = limits.get("LowerLimit", "")
            row["UpperLimit"] = limits.get("UpperLimit", "")
            row["Unit"] = limits.get("Unit", "")
            row["Visible"] = limits.get("Visible", "Y")

            steps.append(TestStep.from_row_dict(row))

        # 供表格显示的列
        hidden = {"Running", "config", "Visible"}
        headers = [h for h in raw_headers if h not in hidden]
        # Limits列 + 运行时动态列
        headers += ["LowerLimit", "UpperLimit", "Unit", "Value", "Result"]

        return TestPlan(headers=headers, steps=steps)
