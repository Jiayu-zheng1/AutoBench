"""Test runner — 单通道测试执行引擎。"""

import re as _re
import time as _time

from PySide6.QtCore import Signal

from app.utils.logger import (
    begin_unit_log,
    end_unit_log,
    get_logger,
    make_unit_folder,
)

logger = get_logger("TestRunner")
from app.controllers.base_runner import BaseTestRunner
from app.models.sfc_connector import SFCConnector
from app.models.test_config import TestConfig, load_test_configs
from app.models.test_item import TestItem
from app.models.test_plan import TestStep
from app.utils.config import load_config
from app.utils.csv_handler import CsvReport, RecordsCsvWriter

# 去除 HTML 标签（单pcs test.log 不用 XML 格式）
_STRIP_HTML = _re.compile(r"<[^>]+>")


class TestRunner(BaseTestRunner):
    """单通道测试线程：顺序执行 CSV 测试项，支持 SFC 上报和 CSV 报表。"""

    signal_value = Signal(str, str)
    signal_result = Signal(str, str)
    signal_color = Signal(str, str)
    signal_status = Signal(bool)
    signal_stop = Signal()
    signal_display = Signal(str, str)

    def __init__(
        self, csv_rows: list[TestStep], log_controller, instrument_manager=None
    ):
        super().__init__()
        self._csv_rows = csv_rows
        self._log_controller = log_controller
        self.ScanSN: str = None
        self.test_unit = TestItem(instrument_manager=instrument_manager)
        self.configs: list[TestConfig] = []
        self.test_items: list[str] = []
        self.lower_limit_map: dict = {}
        self.upper_limit_map: dict = {}
        self.unit_map: dict = {}

    # ── 钩子实现 ──

    def _emit_value(self, test_item: str, value: str):
        self.signal_value.emit(test_item, value)

    def _emit_result(self, test_item: str, label: str):
        self.signal_result.emit(test_item, label)

    def _emit_color(self, test_item: str, color: str):
        self.signal_color.emit(test_item, color)

    def _log(self, msg: str):
        # 送给 loguru 前去除 HTML 标签（单pcs test.log 不用 XML 格式）
        logger.info(_STRIP_HTML.sub("", msg).strip())

    # ── 主循环 ──

    def run(self):
        logger.info("Starting test")
        self._test_status = True
        self.test_unit.ScanSN = self.ScanSN
        self._load_configs()
        self._log_controller._path_logger()
        self._load_system_config()

        # ── 创建单pcs 日志文件夹 ──
        unit_dir = make_unit_folder(scan_sn=self.ScanSN)
        _unit_handler = begin_unit_log(unit_dir)

        # unit 目录写 records.csv（17列格式）
        unit_records = RecordsCsvWriter(str(unit_dir))

        # 总的日聚合 CSV（Test_CSV/YYYYMMDD.csv）
        csv_report = CsvReport(
            self.test_items,
            self.upper_limit_map,
            self.lower_limit_map,
            self.unit_map,
        )
        self._test_values: dict[str, str] = {}

        for cfg in self.configs:
            display = cfg.sub_test_name
            method = cfg.function
            step_passed = True
            step_value_str = ""
            step_failure = ""

            try:
                self._log(
                    f'<span style="font-size:15px; font-weight:700;">Start Run [{display}]</span>'
                )
                value = self._run_one(display, method, cfg.config)

                if value is not None:
                    self._test_values[display] = str(value)
                    step_value_str = str(value)
                    self._evaluate_result(display, str(value), cfg)
                else:
                    self._test_values[display] = "None"
                    step_value_str = "None"
                    step_passed = False
                    display_value = "FAILED" if cfg.is_special_limit() else "None"
                    self.signal_value.emit(display, display_value)
                    self.signal_result.emit(display, "Fail")
                    self.signal_color.emit(display, "Fail")
                    self._test_status = False

            except Exception as e:
                logger.info(f"Error running test item {cfg.sub_test_name}: {e}")
                self._test_values[cfg.sub_test_name] = "Error"
                step_value_str = "Error"
                step_passed = False
                step_failure = str(e)
                display_value = "FAILED" if cfg.is_special_limit() else str(e)
                self.signal_value.emit(cfg.sub_test_name, display_value)
                self.signal_result.emit(cfg.sub_test_name, "Fail")
                self.signal_color.emit(cfg.sub_test_name, "Fail")
                self._test_status = False

            # ── 写入单pcs records.csv ──
            unit_records.write_step(
                test_name=cfg.test_name,
                sub_test_name=cfg.sub_test_name,
                sub_sub_test=cfg.sub_test_name,
                upper_limit=cfg.upper_limit_raw,
                lower_limit=cfg.lower_limit_raw,
                unit=cfg.unit,
                value=step_value_str,
                status="PASS" if step_passed else "FAIL",
                failure_message=step_failure if not step_passed else "",
            )

            if self._fail_stop and not self._test_status:
                logger.info("Fail-stop 已启用，停止后续测试")
                break

            if self.test_unit.FGSN:
                self.signal_display.emit(self.ScanSN, self.test_unit.FGSN)

        # ── 写入属性行（SN 信息） ──
        if self.ScanSN:
            unit_records.write_attribute("PrimaryIdentity", self.ScanSN)
        if self.test_unit.FGSN:
            unit_records.write_attribute("FG_SN", self.test_unit.FGSN)
        if getattr(self.test_unit, "MLBSN", None):
            unit_records.write_attribute("MLB_SN", self.test_unit.MLBSN or "")

        # SN 优先级: MLBSN → FGSN → ScanSN → 时间戳
        final_sn = (
            getattr(self.test_unit, "MLBSN", None)
            or self.test_unit.FGSN
            or self.ScanSN
            or _time.strftime("%Y%m%d_%H%M%S")
        )

        # 总的日聚合 CSV（Test_CSV/YYYYMMDD.csv）
        csv_report.set_csv_file(final_sn, self._test_values)

        self._upload_sfc()
        self.stop()

    def _load_system_config(self):
        cfg = load_config()
        self._fail_stop = cfg.get("fail_stop_test", True)
        self._sfc_cfg = {
            "url": cfg.get("sfc_url", ""),
            "online": cfg.get("sfc_online", False),
            "vip": cfg.get("sfc_vip", ""),
        }
        logger.info(
            f"系统配置已加载: fail_stop={self._fail_stop}, sfc_online={self._sfc_cfg.get('online')}"
        )

    def _upload_sfc(self):
        if not self._sfc_cfg.get("online") or not self._sfc_cfg.get("url"):
            return
        sn = self.ScanSN or self.test_unit.FGSN or ""
        if not sn:
            logger.info("SFC 上传跳过：无 SN")
            return
        try:
            sfc = SFCConnector(
                url=self._sfc_cfg["url"],
                vip=self._sfc_cfg["vip"],
                online=True,
            )
            sfc.connect()
            sfc.check_route(sn)
            sfc.upload_result(sn, self._test_status)
            logger.info(
                f"SFC 上传完成: SN={sn}, status={'PASS' if self._test_status else 'FAIL'}"
            )
        except Exception as e:
            logger.error(f"SFC 上传失败: {e}")

    def stop(self):
        self.signal_status.emit(self._test_status)
        self.test_unit.close_dut()
        self.signal_stop.emit()
        self._log_controller.rename_log(self.test_unit.FGSN)
        end_unit_log(_unit_handler)

    def _load_configs(self):
        self.configs = load_test_configs(self._csv_rows)
        self.test_items = [c.sub_test_name for c in self.configs]
        self.lower_limit_map = {
            c.sub_test_name: c.lower_limit_raw for c in self.configs
        }
        self.upper_limit_map = {
            c.sub_test_name: c.upper_limit_raw for c in self.configs
        }
        self.unit_map = {c.sub_test_name: c.unit for c in self.configs}
