# AutoBench

串口测试自动化桌面工具。通过串口与被测设备（DUT）通信，控制测试仪器 —— Keysight 34970A 数字万用表、IT6382 程控电源、Relayboard 继电器板 —— 按测试序列自动执行测量与判定，实时显示 Pass/Fail，生成 CSV 报表，可选把结果上报 SFC 系统。

**设计取向**

- **数据驱动** — 测试序列（`Main.csv`）、判据（`Limits.csv`）、测量方法全部由配置定义，增删测试项只改表、不改代码
- **一套引擎两种模式** — `BaseTestRunner` 模板方法供单通道与最多 8 通道并行复用，差异只在钩子实现
- **可回放** — 每颗 DUT 的每步测量值、判定结果、耗时都落到 CSV，日志按天归档

| 项 | 说明 |
|---|---|
| 界面 | PySide6 + qfluentwidgets（Fluent / macOS 风格） |
| 运行环境 | macOS 10.15+，Python 3.12+ |
| 入口 | `python main.py` |
| 测试模式 | 手动单通道 / DUT 插拔自动 / 多通道并行（1–8） |

## 目录

[快速开始](#快速开始) · [特性](#特性) · [项目结构](#项目结构) · [架构设计](#架构设计) · [配置系统](#配置系统) · [使用说明](#使用说明) · [仪器](#仪器) · [打包](#打包) · [维护](#维护) · [关于](#关于)

## 技术栈

| 层 | 技术 |
|---|------|
| UI | PySide6 + qfluentwidgets（Fluent Design 控件） |
| 串口 | pyserial（DUT + 继电器板） |
| 仪器通信 | pyvisa + pyvisa-py（GPIB 用 NI-VISA，USB 串口用 pyvisa-py） |
| 日志 | loguru — 按模块分文件，每天午夜轮转，历史归档到日期文件夹 |
| SFC | urllib（HTTP 方式上报 PASS/FAIL） |
| 配置 | JSON（system_config.json + instrument_config.json）+ 双 CSV（Main.csv + Limits.csv） |

## 快速开始

### 环境要求

- macOS 10.15+ / Windows 10+
- Python 3.12+
- NI-VISA（GPIB 仪器需要，USB 模式可选）
- FTDI USB 转串口驱动（34970A USB 连接需要）

### 安装与启动

推荐使用 uv（Windows PowerShell / macOS 终端相同）：

```bash
uv sync
uv run main.py
```

> 不使用 uv 时：`pip install -r requirements.txt && python main.py`。

Windows 配置文件写入 `%APPDATA%\AutoBench\`；macOS 写入 `~/Documents/AutoBench/`。

设置页可修改“数据保存路径”，日志和 CSV 会自动生成到该目录下：`unit-archive/` 与 `Test_CSV/`。

### 首次使用

1. 连好仪器后**重启软件**，等待仪器自动检测完成
2. 顶栏状态圆点变绿表示就绪：●34970A ●IT6382 ●Relay ●DUT
3. 输入 SN → 点 **Start** 或按回车开始测试

## 特性

- **双测试模式** — 手动输入 SN 点 Start / 自动模式监控 DUT 串口插拔即测
- **多通道并行测试** — 最多 8 个通道同时测试独立 DUT，每通道独立串口（当前阶段多通道暂不使用仪器）
- **双 CSV 架构** — Main.csv（测试序列） + Limits.csv（判据），按 SubTestName 合并
- **5 通用测量方法** — Read_ASCII_CMD（hex+正则提取）、Read_HEX_CMD（raw hex）、Read_IMPEDANCE（阻抗）、Read_VOLTAGE（电压）、反射调用（自定义方法），无需注册表
- **Config 驱动测试** — 测试逻辑完全由 CSV config 列定义，新增测试项只需改 CSV 无需写代码
- **Config 新旧兼容** — 同时支持 `('key':'val')` 旧格式和 `hex_cmd <指令>` Atlas2 风格空格分隔新格式
- **Pass/Fail 判定链** — No Empty → EQUAL(字符串匹配) → PASSED(无失败标志) → 数值比较 → hex精确匹配 → 空limit(有值即Pass)
- **Value 列显示规则** — PASSED limit 显示 PASSED/FAILED，有limit 显示提取值，空 limit 显示原始值
- **Limits Visible 控制** — Limits.csv Visible=N 的项后台静默判定，UI 不显示上下限
- **Tab 分页布局** — 单通道：测试信息 | Log；多通道：Summary + 各通道独立 Tab
- **Fail 即停** — 失败后跳过后续项（可开关）
- **SFC 上报** — 在线模式下 connect → checkRoute → uploadResult（OK/NG）
- **模块化面向对象架构** — DutCommunicator / InstrumentAccessor / MeasurementEngine / TestItem 门面 / TestPlan 数据模型，单一职责
- **模板方法模式** — BaseTestRunner 定义测试算法骨架，TestRunner / ChannelRunner 实现钩子（信号发射、日志、DUT 定位）
- **macOS 风格设置页** — 左侧标签栏 + 右侧滚动卡片，滚动联动高亮，密码 "123" 解锁

## 项目结构

```
AutoBench/
├── main.py                          # 入口
├── requirements.txt                 # Python 依赖
├── resources/
│   ├── Main.csv                     # 测试序列（TestName, Function, SubTestName, Running, config）
│   ├── Limits.csv                   # 判据（SubTestName, LowerLimit, UpperLimit, Unit, Visible）
│   └── Error_Code.csv               # 错误码映射
└── app/
    ├── application.py               # QApplication 启动
    ├── controllers/
    │   ├── base_runner.py            # 测试执行引擎基类（模板方法模式）
    │   ├── test_runner.py            # 单通道测试执行（SFC + CSV）
    │   ├── channel_runner.py         # 多通道测试执行（独立 DUT 串口；暂不使用仪器）
    │   ├── instrument_manager.py     # 仪器管理器单例
    │   ├── dut_monitor.py            # DUT 插拔监控（macOS ioreg / 平台工厂）
    │   ├── windows_monitor.py         # Windows 串口轮询 + Hub 端口 Slot 映射
    │   └── log_controller.py         # loguru → Qt 信号桥接
    ├── models/
    │   ├── test_plan.py              # TestStep + TestPlan 类型化数据模型（替代裸 dict）
    │   ├── test_item.py              # 测试项门面（组合 DutCommunicator + InstrumentAccessor + MeasurementEngine）
    │   ├── dut_communicator.py       # DUT 串口连接/断开/检查
    │   ├── instrument_accessor.py    # 仪器访问门面（DMM/PS/Relay，优先直接注入，回退 manager）
    │   ├── measurement_engine.py     # 4 通用测量方法（Read_ASCII/HEX/IMPEDANCE/VOLTAGE） + 正则值提取
    │   ├── test_config.py            # CSV 行解析 + Pass/Fail 判定
    │   ├── device.py                 # DUT 串口 Device + USB 端口定位
    │   ├── sfc_connector.py          # SFC HTTP 上报
    │   └── instruments/
    │       ├── base.py               # BaseInstrument ABC
    │       ├── keysight_34970a.py    # 34970A DMM（USB 串口/GPIB，批量扫描 + 单点测量）
    │       ├── ps_it6382.py          # IT6382 可编程电源（3 通道）
    │       └── relay_board.py        # 继电器板（v0/v1 两版）
    ├── views/
    │   ├── main_window.py            # 主窗口（菜单栏 + QStackedWidget）
    │   ├── control_bar.py            # 顶栏（仪器状态/SN/Start/计时器）
    │   ├── status_header.py          # 状态卡片（Pass/Fail计数/状态）
    │   ├── test_table.py             # 测试结果表格（锚点模式处理重复 SubTestName）
    │   ├── log_panel.py              # 实时日志面板（macOS Cmd+C 可用）
    │   ├── settings_dialog.py        # macOS 风格设置（5 标签页）
    │   ├── channel_tab.py            # 多通道单通道 Tab（SN+表格+日志）
    │   ├── summary_tab.py            # 多通道汇总 Tab（网格 PASS/FAIL）
    │   ├── about_dialog.py           # 关于窗口（版本/简介/仓库地址）
    │   ├── animations.py             # 脉冲呼吸 / 淡入淡出
    │   └── theme.py                  # Apple HIG 主题（色彩/字体/QSS）
    └── utils/
        ├── config.py                 # 系统配置读写
        ├── config_parser.py          # Config 列解析（旧/新格式兼容 + 破损格式兜底）
        ├── constants.py              # 全局常量
        ├── limits_loader.py          # Main.csv + Limits.csv 双CSV 加载合并
        ├── logger.py                 # 模块化日志（按天轮转+归档+过期清理）
        └── csv_handler.py            # 测试结果 CSV 生成
```

## 架构设计

### 模块分层

```
┌──────────────────────────────────────────────────────────┐
│  UI 层 (views/)                                           │
│  MainWindow → TestTable / LogPanel / ControlBar / ...    │
│  信号连接: signal_value → test_table.set_value()          │
├──────────────────────────────────────────────────────────┤
│  控制层 (controllers/)                                    │
│  TestRunner / ChannelRunner — QThread 子类               │
│  BaseTestRunner — 模板方法基类                            │
│  _run_one() 分发 + _evaluate_result() 判定 + 钩子发射     │
├──────────────────────────────────────────────────────────┤
│  领域层 (models/)                                         │
│  TestItem (门面) → DutCommunicator + InstrumentAccessor  │
│                   + MeasurementEngine + 专属测试方法       │
│  TestPlan / TestStep (数据模型)                           │
│  TestConfig (evaluate 判定链)                             │
├──────────────────────────────────────────────────────────┤
│  基础设施 (utils/ + models/instruments/)                   │
│  limits_loader / config_parser / logger / csv_handler     │
│  BaseInstrument → 34970A / IT6382 / Relayboard           │
└──────────────────────────────────────────────────────────┘
```

### 测试执行链路（单通道）

```
用户在 UI 输入 SN → 点 Start
  → MainWindow._start_test()
    → TestRunner(signals connected to TestTable + LogPanel)
      → run()
        → load_test_configs(steps)     # 从 TestPlan 解析 85 条 TestConfig
        → for cfg in configs:
            → _run_one(method, config, display)
              ├─ method == "Read_ASCII_CMD"  → MeasurementEngine.Read_ASCII_CMD()
              ├─ method == "Read_HEX_CMD"    → MeasurementEngine.Read_HEX_CMD()
              ├─ method == "Read_IMPEDANCE" → MeasurementEngine.Read_IMPEDANCE()
              ├─ method == "Read_VOLTAGE"   → MeasurementEngine.Read_VOLTAGE()
              └─ 其他 → getattr(TestItem, method)() 反射调用
            → _evaluate_result(display, value, cfg)
              ├─ cfg.evaluate(value) 判定 Pass/Fail
              ├─ 确定 display_value（PASSED/FAILED or 原始值）
              └─ 发射 signals → UI 表格更新 + 行着色
        → CSV 报表生成 + SFC 上报
```

### Value 列显示规则

| Limits 类型 | Value 列显示 |
|-------------|-------------|
| PASSED | `PASSED`（Pass）或 `FAILED`（Fail） |
| 有上下限数值/字符串 | 正则提取后的原始值 |
| 空 limits | 原始值 / `None` |

## 配置系统

### 双 CSV 测试配置

**Main.csv** — 测试序列（99 项）：

| 列 | 说明 |
|---|---|
| `TestName` | 测试分组名（如 `DUTInfo`、`VoltageCheck_OVP`） |
| `Function` | 对应的方法名（`Read_ASCII_CMD` / `Read_HEX_CMD` / `Read_IMPEDANCE` / `Read_VOLTAGE` / 自定义方法）|
| `SubTestName` | 表格显示名，关联 Limits.csv 的 key |
| `Running` | `Y` = 加入测试序列，`N` = 跳过 |
| `config` | 驱动参数（见下文）。仓库内的 `hex_cmd` 均已置空，按被测产品自行填写 |

**Limits.csv** — 判据（99 项）：

| 列 | 说明 |
|---|---|
| `SubTestName` | 关联 Main.csv 同名字段 |
| `LowerLimit` / `UpperLimit` | 判定范围（数值 / `PASSED` / `No Empty` / `EQUAL` / 空=有值即Pass） |
| `Unit` | 单位（`Ω` / `mV` / 空） |
| `Visible` | `Y` = UI 显示上下限列，`N` = 后台静默判定 |

加载时 `limits_loader.py` 按 SubTestName 合并两张表，生成 `TestPlan`（含 100 条 `TestStep`）。

### 5 通用测量方法

| Function | 用途 | 返回 | config 关键字段 |
|----------|------|------|----------------|
| `Read_ASCII_CMD` | hex 指令 → ASCII 解码 → 正则提取值 | (raw_hex, ascii_str, value) | `hex_cmd`, `regex`, `group`, `set_attr` |
| `Read_HEX_CMD` | hex 指令 → 原始 hex 返回值（不做 ASCII 解码） | (raw_hex, ascii_str, hex_value) | `hex_cmd`, `contains`, `regex` |
| `Read_IMPEDANCE` | DMM 直读阻抗 | ("", str(Ω), float) | `channel`（101-217） |
| `Read_VOLTAGE` | DMM 直读电压 (mV) | ("", str(mV), float) | `channel`（101-217） |
| 自定义方法 | 反射调用 TestItem 方法 | 方法返回值 | 无 config 或 config 含 `action: "method"` |

### Pass/Fail 判定链

`TestConfig.evaluate(value)` 按优先级依次尝试：

| 优先级 | 条件 | 逻辑 |
|--------|------|------|
| 1 | LowerLimit ∈ {No Empty, Empty} | `bool(value)` |
| 2 | LowerLimit 或 UpperLimit = `EQUAL` | 字符串精确匹配（忽略大小写） |
| 3 | LowerLimit 或 UpperLimit = `PASSED`/`ON`/`True` | 检查失败标志（FAILED/Error/None/False） |
| 4 | 上下限可转 float | `lo ≤ val ≤ hi` 数值比较 |
| 5 | 非数值非特殊字符串 | hex/字符串精确匹配 |
| 6 | 空 limit | value 非 None 即 Pass |

### config 列格式

支持两种格式，自动识别：

```python
# 旧格式 — dict/paren 风格
('hex_cmd':'<HEX 指令>')
('hex_cmd':'<HEX 指令>', 'regex':'hw_id\\s\\W\\s(\\w+)', 'group':'1', 'delay':'1')

# 新格式 — Atlas2 风格空格分隔
hex_cmd <HEX 指令>
hex_cmd <HEX 指令> hw_id\s\W\s(\w+) 1 1

# 特殊 action
connect                               # 连接 DUT
method Check_USB_Ready                # 反射调用 TestItem 方法
```

config 字段一览：
| 字段 | 说明 |
|------|------|
| `hex_cmd` | 要发送的 hex 指令字符串 |
| `cmd` / `command` | ASCII 命令 |
| `regex` | 正则表达式提取值 |
| `group` | 正则捕获组编号（默认 1） |
| `delay` | 指令间延时（秒，默认 0.05-0.1） |
| `contains` | 检查返回值是否包含指定文本 |
| `pass_value` / `fail_value` | contains 模式的通过/失败值 |
| `set_attr` | 执行后设置 TestItem 属性（如 `MLBSN`、`FGSN`） |
| `pre_cmds` / `post_cmds` | 前置/后置命令 |

### 数据目录

配置文件位置按平台区分：

- macOS：`~/Documents/AutoBench/`
- Windows：`%APPDATA%\AutoBench\`（如 `C:\Users\<user>\AppData\Roaming\AutoBench\`）

Windows 首次升级会自动把旧 `Documents\AutoBench` 下的配置文件复制到 AppData。

日志与测试结果 CSV 仍位于 `~/Documents/AutoBench/`：

```
~/Documents/AutoBench/
├── TopLevelLog/                     # 日志
│   ├── InstrumentManager.log        # 今天活跃日志
│   ├── TestRunner.log
│   ├── ChannelRunner.log
│   ├── 2026-06-02/                  # 历史日志（每天一个文件夹）
│   │   ├── InstrumentManager.log
│   │   └── ...
│   └── 2026-06-01/
│       └── ...
└── Test_CSV/                        # 测试结果 CSV
```

配置文件（macOS `~/Documents/AutoBench/`，Windows `%APPDATA%\AutoBench\`）：

```
system_config.json                   # 系统配置（双平台 profile）
instrument_config.json               # 仪器连接配置
channel_config.json                  # 多通道配置（双平台 profile）
```

### 系统配置键名说明

`system_config.json` 按平台分为两套 profile：

```json
{
  "platform_mode": "macos",
  "profiles": { "macos": { ... }, "windows": { ... } }
}
```

- 设置页最上方 → **运行平台** 可切换 `macOS` / `Windows`，切换后需重启。
- 旧版扁平配置会自动迁移到当前平台 profile。
- `channel_config.json` 同样按平台保存两套通道配置，两套的 JSON 结构完全一致（`location_ids` / `dmm_modes` / `dmm_ports` / `ps_modes` / `ps_ports` / `relay_ports` / `channels_enabled`）；macOS 存 Location ID，Windows 存 Location path。
- 仪器配置暂保持全局共享。

| 键 | 默认值 | 说明 |
|---|---|---|
| `log_retention_days` | 90 | 日志保留天数，过期自动删除 |
| `log_path` | `~/Documents/AutoBench` | 数据根目录：日志写入 `unit-archive/`，CSV 写入 `Test_CSV/` |
| `dut_baud_rate` | 921600 | DUT 串口波特率 |
| `dut_location_id` | `""` | DUT USB Location ID / Location path（单通道模式） |
| `dut_interface` | `""` | Windows 复合设备串口接口，如 `MI_02`；空=任意 |
| `dut_vid` | `""` | Windows DUT VID 过滤，如 `290B` |
| `dut_pid` | `""` | Windows DUT PID 过滤，如 `092F` |
| `auto_test_mode` | false | 自动测试模式，监控 DUT 插拔即测 |
| `auto_connect_instruments` | true | 启动时自动检测并连接仪器；关闭后需手动连接 |
| `fail_stop_test` | true | 测试项失败后停止后续测试 |
| `auto_scroll_log` | true | 日志面板自动滚动 |
| `sfc_url` | `""` | SFC 服务器 URL |
| `sfc_online` | false | 是否启用 SFC 在线上报 |
| `sfc_vip` | `""` | SFC 终端 IP 地址 |
| `multi_channel_mode` | false | 启用多通道测试模式 |
| `channel_count` | 4 | 通道数量（1–8） |
| `channel_test_enabled` | `[true,…]` | 每通道是否参与测试（也可在 channel_config.json 的 `channels_enabled` 中配置） |
| `channel_location_ids` | `["","","",""]` | 每通道的 DUT Location ID |

## 使用说明

### 基本操作

1. **连接仪器** — 默认启动软件后自动检测仪器，顶栏状态圆点 ●34970A / ●IT6382 / ●Relay / ●DUT 变绿表示连接成功；设置页 → 仪器设置可关闭“自动连接仪器”，关闭后需在下方逐台手动连接
2. **设置** — 点击“设置”按钮进入设置页，输入密码 `123` 解锁编辑
3. **单通道测试** — 关闭多通道模式，输入 SN → 点 **Start**
4. **多通道测试** — 设置页 → 串口设置 → 开启多通道测试模式 → 配置通道数量（通道 1-N 收纳在“多通道设置”分组中，整组折叠/展开）+ 各通道 Location ID / path，逐通道勾选“是否测试”→ 保存重启 → 在主页各通道卡片输入 SN 后点全局 Start；当前多通道阶段暂不使用仪器

### 手动模式

1. 确保仪器已连接
2. 输入 SN
3. 点 **Start** 或按 Enter 开始测试
4. 结果实时显示在表格中，完成后生成 CSV 报表

### 自动模式

1. macOS：设置页 → 串口设置 → 填入 DUT Location ID
2. Windows：可在设置里填 Location path（如 `1-3.4`）；留空则按 Hub 下游端口号自动映射 Slot
   复合设备若同时暴露 `MI_00` / `MI_02`，在“DUT 串口接口”选择实际测试口（如 `MI_02`）
3. 打开"自动测试模式"开关
4. 插入 DUT → 自动开始测试；测试中拔出 → 立即中止并判定 Fail，后续测试项跳过
5. 重新插入 → 再次自动测试

### 多通道测试

1. **配置**：设置页 → 串口设置 → 开启"多通道测试模式" → 选择通道数量（通道 1-N 统一收纳在“多通道设置”分组，默认折叠）→ 展开分组后为每个通道勾选“是否测试”（macOS 填 Location ID；Windows 填 Location path，如 `1-3.4`，留空则按 Hub 端口尾号）→ 保存并重启。多通道阶段暂不使用仪器
2. **查看 DUT**：macOS 点击"可用 DUT 设备"查看 Location ID；Windows 在"可用 DUT 设备"里填 VID/PID 查询，复制 `Location path` 填入通道配置
3. **测试**：Windows 插入 DUT 后按 Slot 自动触发；也可在主页各通道卡片内输入 SN 后点 **全局 Start**；各通道 Tab 仅显示结果和日志
4. **拔出处理**：测试中拔出 DUT 立即中止，判定 Fail，后续测试项不再执行，并按正常 Fail 统计
5. **查看汇总**：Summary Tab 每个通道卡片显示独立的 SN 输入、状态和 Input / Pass / Fail 计数（按整次测试单元统计，多次 Start 连续累计），未勾选通道显示“不测试”

### 检查 DUT Location ID

```bash
system_profiler SPUSBDataType | grep -A 10 "FTDI\|USB-Serial\|CP210"
```

或点击设置页的"可用 DUT 设备"按钮查看。  
Windows 下该按钮会列出 `COMx` 与对应 `Location path`（如 `1-3.4`），可直接填入通道配置。

## 仪器

### 34970A 数字万用表

- **USB 模式**：FTDI 适配器串口连接，波特率 9600
- **GPIB 模式**：NI-VISA 连接，需安装 NI-VISA 驱动
- **功能**：2 线电阻测量、直流电压测量、批量扫描（每批最多 10 通道）

### IT6382 程控电源

- **GPIB 模式**：NI-VISA 连接
- **USB 模式**：串口连接，支持自动检测
- **功能**：3 路独立输出、电压/电流读取

### Relayboard 继电器板

- 串口直连，支持 v0（19200 baud）和 v1（9600 baud + 校验）两版
- 8 路独立控制、批量控制、电源保护自动断电

## 打包

使用 PyInstaller（`*.spec` 为本地打包配置，已 gitignore）：

```bash
pyinstaller --windowed --name AutoBench --add-data "resources:resources" main.py
```

输出 `dist/AutoBench.app`。

自动更新基于 `sparklehelper`，`app/controllers/update_controller.py` 中的 `FEED_URL` 留空即关闭「Check for Updates」；填入自己的 Appcast 地址与 Ed25519 公钥后启用。

## 维护

- **日志查看**：`~/Documents/AutoBench/TopLevelLog/`，历史按日期归档
- **CSV 报表**：`~/Documents/AutoBench/Test_CSV/`；日聚合 CSV 含 `Slot` 列（单通道固定 1，多通道为通道号）和 `Test Pass/Fail Status`（PASS/FAIL）
- **修改测试项**：编辑 `resources/Main.csv` + `resources/Limits.csv`
- **新增测试项**：在两张 CSV 中增加行，SubTestName 对应即可，无需改代码
- **修改仪器端口**：设置页中修改或直接编辑 `~/Documents/AutoBench/instrument_config.json`
- **重置配置**：删除 `~/Documents/AutoBench/system_config.json`，重启即恢复默认

## 关于

AutoBench 是面向产线/实验室的串口测试上位机。所有测试逻辑由 `resources/Main.csv` 与 `resources/Limits.csv` 驱动，仓库内只保留示例结构，实际指令与判据需要按被测产品自行填写。

- **版本**：`1.0.1`（`APP_VERSION`，定义在 `app/utils/constants.py`）
- **许可**：Apache License 2.0
- **仓库**：<https://github.com/Jiayu-zheng1/AutoBench>

程序内「菜单栏 → AutoBench → 关于 AutoBench」可查看同一份信息。
