# serial-test-automation — 测试流程说明

> 从点 Start 到测试完成的完整链路，精确到代码模块。

## 目录

1. [触发源头](#1-触发源头)
2. [准备阶段 — _start_test()](#2-准备阶段)
3. [执行阶段 — TestRunner.run()](#3-执行阶段)
4. [通用处理器 — run_read_cmd()](#4-通用处理器)
5. [判定逻辑 — TestConfig.evaluate()](#5-判定逻辑)
6. [收尾阶段](#6-收尾阶段)
7. [多通道分支](#7-多通道分支)
8. [Config 解析链路](#8-config-解析链路)
9. [模块职责总表](#9-模块职责总表)

---

## 1. 触发源头

```
用户点 Start 按钮 或 按 Enter
        │
        ▼
control_bar.start_btn.clicked       ──→  MainWindow._start_test()
control_bar.sn_input.returnPressed  ──→  MainWindow._start_test()
```

**文件**: `app/views/main_window.py:259`

---

## 2. 准备阶段

`MainWindow._start_test(only_channel="")` — `app/views/main_window.py:259`

```
_start_test()
  │
  ├─ 已 testing → return（防重入）
  ├─ 多通道模式 → _start_multi_test() → 跳到 §7
  │
  └─ 单通道:
       ├─ sn = control_bar.sn_input.text()
       │
       ├─ self._testing = True
       ├─ _dut_monitor.pause()             ← 暂停串口监控
       ├─ control_bar.set_running(True)    ← 顶栏变灰
       ├─ status_header.set_running()      ← 状态: "Running"
       ├─ test_table.clear_results()       ← 清空表格
       ├─ log_panel.clear_log()            ← 清空日志
       ├─ control_bar.start_timer()        ← 计时 00:00
       │
       ├─ 创建 TestRunner(csv_rows, log_ctrl, instrument_manager)
       │   ├─ csv_rows = 97 行 Limits.csv 原始数据
       │   └─ instrument_manager = InstrumentManager.instance()
       │
       ├─ runner.ScanSN = sn
       │
       ├─ 连接信号:
       │   signal_value   → test_table.set_value          (表格值)
       │   signal_result  → test_table.set_result          (表格 Pass/Fail)
       │   signal_color   → test_table.set_result_color    (行颜色)
       │   signal_status  → _on_status                     (顶部计数)
       │   signal_stop    → _on_test_completed              (收尾)
       │   signal_display → _on_display_sn                  (底部 FGSN)
       │
       └─ runner.start()  ──→ QThread 后台线程 → run()
```

---

## 3. 执行阶段

`TestRunner.run()` — `app/controllers/test_runner.py:34`

```
TestRunner.run()              ← QThread 后台线程
  │
  ├─ 1. test_unit.ScanSN = ScanSN
  │
  ├─ 2. _load_configs()                     ← test_runner.py:116
  │   │   load_test_configs(csv_rows)       ← test_config.py:69
  │   │   ├─ Running≠"Y" → 跳过
  │   │   └─ Running="Y" → TestConfig(item, name, lower, upper, config)
  │   │       └─ config = parse_config(csv_text)  ← config_parser.py (§8)
  │   │   返回 ≈94 个 TestConfig
  │
  ├─ 3. _log_controller._path_logger()
  │
  ├─ 4. _load_system_config()               ← test_runner.py:78
  │   │   从 system_config.json:
  │   │     fail_stop_test → self._fail_stop
  │   │     sfc_url/sfc_online/sfc_vip → self._sfc_cfg
  │
  ├─ 5. csv_report = CsvReport(...)
  │
  ├─ 6. 遍历 configs:
  │   │
  │   for cfg in self.configs:
  │   │
  │   ├── _run_one(display, method, config)  ← test_runner.py:122
  │   │   │
  │   │   │   分发:
  │   │   ├── method=="run_read_cmd" 或 config 非空:
  │   │   │   └─ test_unit.run_read_cmd(method, config)  → §4
  │   │   │
  │   │   └── 有同名 TestItem 方法:
  │   │       ├─ Info_CheckDUT()          → 连接 DUT 串口
  │   │       ├─ Enable_HWID()            → 发固定 hex 启用 HWID
  │   │       ├─ Disable_HWID()           → 发固定 hex 禁用 HWID
  │   │       ├─ Measure_Impedance_XXX()  → dmm.measure_res(channel) 
  │   │       └─ Measure_Voltage_XXX()    → dmm.measure_dcv(channel, mV)      
  │   │
  │   ├── value ≠ None → _evaluate_result(display, value, cfg)  → §5
  │   │   └─ emit signal_value/result/color → UI 表格实时更新
  │   │
  │   ├── value = None → emit Fail, _test_status = False
  │   │
  │   ├── fail_stop 且不通过 → break（停止后续）
  │   │
  │   └── FGSN 有值 → emit signal_display(scanSN, FGSN)
  │
  ├─ 7. csv_report.set_csv_file()           ← 写入测试结果 CSV
  │
  ├─ 8. _upload_sfc()                        ← test_runner.py:89
  │   │   sfc.connect() → sfc.checkRoute(sn) → sfc.uploadResult(sn, status)
  │
  └─ 9. stop()                               ← test_runner.py:110
        ├─ emit signal_status(passed)        → UI PASS/FAIL
        ├─ test_unit.close_dut()             → 关闭串口
        ├─ emit signal_stop()                → _on_test_completed()  (§6)
        └─ _log_controller.rename_log(FGSN)  → 日志重命名
```

---

## 4. 通用处理器

`TestItem.run_read_cmd(method_name, config)` — `app/models/test_item.py:81`

```
run_read_cmd(method_name, config)
  │
  ├─ action = config.get("action", "")
  │
  ├── action=="connect":
  │     └─ connent_dut() → "PASSED"/"FAILED"
  │
  ├── action=="method":
  │     └─ getattr(self, target)(*args)
  │
  └── 通用 (hex_cmd / cmd):
        │
        ├─ 旧格式 config: {"hex_cmd":"055A...", "regex":"pat", ...} 直接使用
        │  新格式 config: {"action":"hex_cmd", "args":["055A...","pat","1","1"]}
        │    → 展开: hex_cmd=args[0], regex=args[1], group=args[2], delay=args[3]
        │
        ├─ DUT=None → return (None)
        │
        ├─ pre_cmds 循环: dut.send_cmd(cmd)
        │
        ├─ hex_cmd 存在:
        │   └─ dut.send_hex_cmd(hex, delay)     ← 发 HEX 收响应
        │      → (raw_hex, ascii_data)
        │
        ├─ 无 hex_cmd 且有 cmd/command/instruction:
        │   └─ dut.read_Write(cmd)              ← 发 ASCII 命令
        │
        ├─ _extract_config_value(data, config)
        │   │  文件: test_item.py:123
        │   │
        │   ├─ contains → data 中包含子串? → "PASSED"/"FAILED"
        │   ├─ regex+group → re.finditer → match.group(group)
        │   │   └─ _format_config_value() 类型转换 (str/int/float/hex_int)
        │   └─ 无 regex → 返回原始 data
        │
        ├─ set_attr: setattr(self, attr, result)
        │
        ├─ post_cmds 循环: dut.send_cmd(cmd)
        │
        └─ return (raw_hex, ascii_data, result)
```

### _extract_config_value 支持的 config key

| Key | 用途 |
|---|---|
| `hex_cmd` | HEX 指令字符串 |
| `cmd` / `command` / `instruction` | ASCII 文本命令 |
| `regex` | 正则提取模式 |
| `group` | 捕获组编号 (str/int/list) |
| `contains` | 子串包含检查 |
| `delay` | hex_cmd 发送后等待秒数，默认 0.05 |
| `pre_cmds` | 前置 ASCII 命令 (str/list) |
| `post_cmds` | 后置 ASCII 命令 (str/list) |
| `set_attr` | 将结果写入 TestItem 的属性名 |
| `cast` | 类型转换: str/int/float/hex_int |
| `default` | 正则无匹配时默认值 |
| `match_index` / `index` | 取第几个正则匹配 |

---

## 5. 判定逻辑

`TestConfig.evaluate(value)` — `app/models/test_config.py:31`

```
evaluate(value) → (passed, "Pass"/"Fail")
  │
  ├── 特殊 limit (No Empty / PASSED / ON / True / Empty):
  │   ├─ "No Empty" / "Empty":
  │   │   └─ bool(value) → Pass/Fail
  │   └─ "PASSED" / "ON" / "True":
  │       └─ value 不在 [None, False, "FAILED", "FAIL", "ERROR", "FALSE", "0"] → Pass
  │
  └── 数值 limit:
      └─ float(lower) <= float(value) <= float(upper) → Pass/Fail
```

---

## 6. 收尾阶段

```
Runner 线程 finish
  │
  ├─ emit signal_stop()
  │   └─ MainWindow._on_test_completed()    ← main_window.py:342
  │       ├─ self._testing = False
  │       ├─ control_bar.stop_timer()
  │       ├─ control_bar.set_running(False)
  │       ├─ sn_input.clear() + setFocus()
  │       └─ _dut_monitor.resume()          ← 恢复串口监控
  │
  └─ emit signal_status(passed)
      └─ MainWindow._on_status(passed)      ← main_window.py:335
          └─ status_header.add_result()     ← Input/Fail/Yield 更新
```

---

## 7. 多通道分支

`MainWindow._start_multi_test(only_channel="")` — `main_window.py`

```
_start_multi_test(only_channel)
  │
  ├─ 遍历所有通道 (1..channel_count)
  │   │
  │   每个通道创建 ChannelRunner:
  │   ├─ channel_id = f"CH{i}"
  │   ├─ location_id = channel_location_ids[i-1]  ← 精准匹配 DUT 串口
  │   ├─ sn = control_bar.sn + "_CHi"             ← SN 加通道后缀
  │   └─ dmm_index = 解析 channel_instruments[i-1]
  │
  ├─ 信号带 channel_id 前缀:
  │   signal_value(channel, display, value)
  │   signal_result(channel, display, label)
  │   signal_color(channel, display, color)
  │   signal_channel_done(channel, passed)
  │   signal_log(channel, msg)
  │
  ├─ 全部并行启动 → 各线程独立 run()
  │   ChannelRunner.run()  ← 文件: app/controllers/channel_runner.py
  │   逻辑与 TestRunner.run() 一致 (§3)，差异:
  │     - 按 location_id 查找串口 (find_port_by_location)
  │     - 无 SFC 上报
  │     - 完成信号: signal_channel_done
  │
  └─ _on_channel_done(channel, passed)
        ├─ 每完成一个通道 → Summary Tab 卡片更新
        └─ 全部完成 → stop_timer + set_running(False)
```

---

## 8. Config 解析链路

```
Limits.csv config 列文本
  │
  ├─ limits_loader.load_limits_csv()        ← app/utils/limits_loader.py
  │   │   逐行 split("," , 8)，第9列为 config_text
  │   └─ parse_config(config_text)
  │
  └─ parse_config(text)                     ← app/utils/config_parser.py
      │
      ├─ 空/None → {}
      ├─ 已是 dict → 原样返回
      │
      ├─ 旧格式 (以 '(' 或 '{' 开头):
      │   ├─ json.loads()
      │   ├─ ast.literal_eval()
      │   └─ 正则 fallback: re.findall(r"'([^']+)'\s*:\s*'([^']*)'")
      │   → {"hex_cmd":"055A...", "regex":"pat", "group":"1"}
      │
      └─ 新格式 (空格分隔，Atlas2 风格):
          │   分词: _tokenize() — 支持单/双引号，保留反斜杠
          │   token[0] = action
          │   token[1:] = args 列表
          └─ → {"action":"hex_cmd", "args":["055A...","pat","1","1"]}

旧格式示例:
  ('hex_cmd':'055A...','regex':'hw_id\\s\\W\\s(\\w+)','group':'1','delay':'1')
  → {"hex_cmd":"055A...", "regex":"hw_id\\s\\W\\s(\\w+)", "group":"1", "delay":"1"}

新格式示例:
  hex_cmd 055A02000c800D0A
  → {"action":"hex_cmd", "args":["055A02000c800D0A"]}

  hex_cmd 055A... hw_id\s\W\s(\w+) 1 1
  → {"action":"hex_cmd", "args":["055A...","hw_id\\s\\W\\s(\\w+)","1","1"]}
```

---

## 9. 模块职责总表

| 模块 | 文件 | 职责 |
|---|---|---|
| 入口 | `main_window.py:259` | 取 SN、切 UI、建 Runner、连信号 |
| CSV 加载 | `limits_loader.py` | CSV → dict 列表 |
| Config 解析 | `config_parser.py` | config 列文本 → dict（新旧格式兼容） |
| 配置构建 | `test_config.py:69` | dict 列表 → TestConfig 列表（过滤 Running=Y）|
| 判定逻辑 | `test_config.py:31` | 特殊 limit / 数值 limit 判定 |
| 执行引擎 | `test_runner.py:34` | QThread，遍历 configs，调 _run_one，fail-stop，SFC |
| 多通道引擎 | `channel_runner.py` | 每通道独立 QThread，按 location_id 定位 DUT |
| 通用处理器 | `test_item.py:81` | hex_cmd 发送 + 正则提取 + contains 检查 |
| DUT 通信 | `device.py` | 串口打开 / send_hex_cmd / read_Write |
| 仪器管理 | `instrument_manager.py` | 34970A / IT6382 / Relayboard 单例管理 |
| SFC 上报 | `sfc_connector.py` | HTTP connect → checkRoute → uploadResult |
| CSV 报表 | `csv_handler.py` | CsvReport 生成测试结果 CSV |
| 日志 | `logger.py` | 按天轮转 + 日期文件夹归档 + 过期清理 |
| 仪器驱动 | `keysight_34970a.py` | 34970A USB/GPIB 连接 + 电阻/电压扫描 |
| 仪器驱动 | `ps_it6382.py` | IT6382 电源输出 / 电压电流读取 |
| 仪器驱动 | `relay_board.py` | 8 路继电器 (v0/v1 两版硬件) |
| 设置 | `settings_dialog.py` | macOS 风格设置页，5 标签，密码解锁 |
