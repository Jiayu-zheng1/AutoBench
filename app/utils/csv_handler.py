"""CSV 处理器 — 日聚合 CsvReport + 单pcs RecordsCsvWriter。"""
import csv
import os
import threading
import time
from typing import Any

from app.utils.constants import SITE

_CSV_WRITE_LOCK = threading.Lock()


class CsvReport:
    """日聚合 CSV 格式 — 列名 = Site, Product, SerialNumber 等，每条 pcs 一行。"""

    def __init__(self, test_items: list[str], upper_limit: dict, lower_limit: dict,
                 unit_map: dict = None, output_dir: str = ""):
        self.item = test_items
        self.columns = [
            'Site', 'Product', 'SerialNumber', 'Station ID', 'Slot',
            'Test Pass/Fail Status', 'StartTime', 'EndTime', 'Version'
        ] + self.item
        self.header_lines = [
            'Display Name ----->',
            'PDCA Priority ----->',
            'Upper Limit ----->',
            'Lower Limit ----->',
            'Measurement Unit ----->',
        ]
        self.upper_limit = upper_limit
        self.lower_limit = lower_limit
        self.unit_map = unit_map or {}
        self.output_dir = output_dir  # 输出目录，为空则走旧路径
        # 旧路径（兜底）
        self.path = os.path.expanduser('~/Documents/AutoBench/Test_CSV')

    def _filepath(self) -> str:
        """确定 CSV 文件路径。
        有 output_dir → <output_dir>/records.csv
        无 output_dir → 旧路径/YYYYMMDD.csv
        """
        if self.output_dir:
            return os.path.join(self.output_dir, "records.csv")
        filename = time.strftime("%Y%m%d.csv")
        return os.path.join(self.path, filename)

    def write_csv(self):
        filepath = self._filepath()
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.columns)
            writer.writeheader()
            writer.writerow({'Site': self.header_lines[0]})
            row_pdca = {'Site': self.header_lines[1]}
            row_upper = {'Site': self.header_lines[2]}
            row_lower = {'Site': self.header_lines[3]}
            row_meas = {'Site': self.header_lines[4]}
            for item in self.item:
                row_pdca[item] = "-2"
                row_meas[item] = self.unit_map.get(item, 'N/A')
                row_upper[item] = self.upper_limit.get(item, "")
                row_lower[item] = self.lower_limit.get(item, "")
            writer.writerow(row_pdca)
            writer.writerow(row_upper)
            writer.writerow(row_lower)
            writer.writerow(row_meas)

    def _ensure_schema(self, filepath: str):
        """旧版 CSV 缺少 Slot 列时补齐，同时保留已有测试项列。"""
        if not os.path.exists(filepath):
            return
        with open(filepath, 'r', newline='') as f:
            reader = csv.reader(f)
            old_header = next(reader, [])
            if old_header == self.columns:
                return
            old_rows = list(reader)

        if old_header:
            target = list(old_header)
            if 'Slot' not in target:
                try:
                    pos = target.index('Station ID') + 1
                except ValueError:
                    pos = min(4, len(target))
                target.insert(pos, 'Slot')
            for col in self.columns:
                if col not in target:
                    target.append(col)
        else:
            target = list(self.columns)

        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(
                f, fieldnames=target, extrasaction='ignore'
            )
            writer.writeheader()
            for raw in old_rows:
                row = {
                    key: raw[i] if i < len(raw) else ""
                    for i, key in enumerate(old_header)
                }
                writer.writerow({col: row.get(col, "") for col in target})
        self.columns = target

    def set_csv_file(self, serial: str, value_dict: dict,
                     slot: str = "1", status: str = ""):
        with _CSV_WRITE_LOCK:
            filepath = self._filepath()
            if not os.path.exists(filepath):
                self.write_csv()
            else:
                self._ensure_schema(filepath)

            newdata = {
                'Site': SITE,
                'Product': '',
                'SerialNumber': serial,
                'Station ID': '',
                'Slot': slot,
                'Test Pass/Fail Status': status,
                'StartTime': time.strftime("%Y-%m-%d %H:%M:%S"),
                'EndTime': time.strftime("%Y-%m-%d %H:%M:%S"),
                'Version': '1.0.0',
            }
            for key, value in value_dict.items():
                if key in self.item:
                    newdata[key] = value

            with open(filepath, 'a+', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.columns)
                writer.writerow(newdata)


# ═══════════════════════════════════════════════════════════════════════════
#  单 pcs records.csv — 17 列格式（对标 Atlas records.csv）
# ═══════════════════════════════════════════════════════════════════════════

_RECORDS_COLUMNS = [
    "attributeName", "attributeValue", "testName", "subTestName",
    "subSubTestName", "relaxedUpperLimit", "upperLimit", "measurementValue",
    "lowerLimit", "relaxedLowerLimit", "measurementUnits", "priority",
    "status", "failureMessage", "startTime", "stopTime", "timeInterval",
]


class RecordsCsvWriter:
    """单 pcs records.csv — 每行一个测试项或属性，17 列标准格式。

    用法:
        w = RecordsCsvWriter(unit_dir)
        w.write_attribute("PrimaryIdentity", sn)
        w.write_step(
            test_name="DUTInfo", sub_test_name="Read_MLB_SN",
            sub_sub_test="MLB_SN", upper_limit="PASSED", lower_limit="PASSED",
            unit="BOOL", value="PASSED", status="PASS",
            failure_message="No user failure message was provided",
        )
    """

    def __init__(self, output_dir: str):
        self._path = os.path.join(output_dir, "records.csv")
        self._wrote_header = False
        self._start_ts = time.strftime("%Y-%m-%d %H:%M:%S")

    def _ensure_header(self):
        if self._wrote_header:
            return
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=_RECORDS_COLUMNS).writeheader()
        self._wrote_header = True

    def _row(self, **kwargs: Any):
        self._ensure_header()
        row = {k: "" for k in _RECORDS_COLUMNS}
        row.update(kwargs)
        with open(self._path, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=_RECORDS_COLUMNS).writerow(row)

    def write_attribute(self, name: str, value: str):
        """写入属性行（如 SerialNumber、FG_SN、MLB_SN）。"""
        self._row(
            attributeName=name,
            attributeValue=value,
            startTime=self._start_ts,
            stopTime=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

    def write_step(
        self,
        test_name: str = "",
        sub_test_name: str = "",
        sub_sub_test: str = "",
        upper_limit: str = "",
        lower_limit: str = "",
        unit: str = "",
        value: str = "",
        status: str = "PASS",
        failure_message: str = "",
    ):
        """写入测试步骤行。"""
        self._row(
            testName=test_name,
            subTestName=sub_test_name,
            subSubTestName=sub_sub_test or sub_test_name,
            upperLimit=upper_limit,
            lowerLimit=lower_limit,
            measurementValue=value,
            relaxedUpperLimit="NA",
            relaxedLowerLimit="NA",
            measurementUnits=unit or "",
            priority="0",
            status=status,
            failureMessage=failure_message or ("No user failure message was provided" if status == "PASS" else ""),
            startTime=self._start_ts,
            stopTime=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
