"""HIG-compliant main window — 原生菜单栏 + 键盘快捷键 + 仪器副窗口 + 多通道支持。"""

from app.utils.logger import get_logger

logger = get_logger("MainWindow")
from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.controllers.channel_runner import ChannelRunner
from app.controllers.dut_monitor import create_dut_monitor
from app.controllers.instrument_manager import InstrumentManager
from app.controllers.log_controller import LogController
from app.controllers.multi_channel_monitor import create_multi_channel_monitor
from app.controllers.test_runner import TestRunner
from app.models.test_plan import TestPlan
from app.utils.config import (
    PLATFORM_WINDOWS,
    get_platform_mode,
    load_channel_config,
    load_config,
)
from app.utils.constants import APP_NAME
from app.utils.limits_loader import LimitsLoader
from app.views.about_dialog import AboutDialog
from app.views.channel_tab import ChannelTab
from app.views.control_bar import ControlBar
from app.views.log_panel import LogPanel
from app.views.settings_dialog import SettingsDialog
from app.views.status_header import StatusHeader
from app.views.summary_tab import SummaryTab
from app.views.test_table import TestTable
from app.views.theme import Colors, stylesheet


class MainWindow(QMainWindow):
    """Primary application window with native macOS menu bar."""

    check_update_triggered = Signal()  # 触发检查更新

    def __init__(self):
        super().__init__()
        self._test_plan: TestPlan = TestPlan()
        self._runner: TestRunner | None = None
        self._runners: list[ChannelRunner] = []  # 多通道 runners
        self._multi_testing_channels: set[str] = set()  # 正在测试的通道
        self._batch_channels: set[str] = set()  # 本轮启动的通道
        self._log_ctrl = LogController()
        self._testing = False

        self._instr_mgr = InstrumentManager.instance()
        self._instr_dialog: SettingsDialog | None = None
        self._slot_ports: dict[str, str] = {}
        self._runner_by_channel: dict[str, ChannelRunner] = {}
        self._single_dut_port: str | None = None
        self._platform = get_platform_mode()

        # 从配置读取
        cfg = load_config()
        loc = cfg.get("dut_location_id", "")
        self._multi_mode = cfg.get("multi_channel_mode", False)

        # DUT 监控线程 — 用 ioreg + location_id 检测串口（单通道模式用）
        self._dut_monitor = create_dut_monitor(
            location_id=loc,
            platform=self._platform,
            interface=cfg.get("dut_interface", ""),
            vid=cfg.get("dut_vid", ""),
            pid=cfg.get("dut_pid", ""),
        )
        self._dut_monitor.dut_detected.connect(self._on_dut_detected)
        self._dut_monitor.dut_lost.connect(self._on_dut_lost)

        # 多通道 DUT 监控 — 每个通道独立监控其 location_id
        self._multi_monitor = None
        self._channel_flags: list[bool] = []

        self.setWindowTitle(APP_NAME)
        self.resize(1024, 768)
        self.setMinimumSize(1300, 640)
        self.setUnifiedTitleAndToolBarOnMac(True)
        self.setStyleSheet(stylesheet())

        self._build_ui()
        self._build_menu_bar()
        self._load_csv()
        self._init_log()
        self._connect_signals()
        # 启动时是否自动检测仪器，可在设置 → 仪器设置中关闭
        if cfg.get("auto_connect_instruments", True):
            self._instr_mgr.start_auto_check()

        # 启动监控线程（单通道模式）
        if not self._multi_mode:
            self._dut_monitor.start()

        # 多通道模式：初始化 tab + 多通道 DUT 监控
        if self._multi_mode:
            self._rebuild_multi_channel_tabs()
            self._stacked.setCurrentIndex(1)
            self._init_multi_monitor()

    # ── UI 构建 ──────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.control_bar = ControlBar()
        root.addWidget(self.control_bar)

        self.status_header = StatusHeader()
        root.addWidget(self.status_header)

        # ── QStackedWidget：单通道(索引0) / 多通道(索引1) ──
        self._stacked = QStackedWidget()

        # 页0: 单通道布局 (QTabWidget: 测试信息 | Log)
        single_page = QWidget()
        single_layout = QVBoxLayout(single_page)
        single_layout.setContentsMargins(0, 0, 0, 0)
        single_layout.setSpacing(0)

        single_tabs = QTabWidget()
        single_tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; }}
            QTabBar::tab {{
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
                color: {Colors.TEXT_SECONDARY};
                border: none;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {Colors.PRIMARY};
                border-bottom: 2px solid {Colors.PRIMARY};
            }}
        """)

        self.test_table = TestTable()
        self.log_panel = LogPanel()

        single_tabs.addTab(self.test_table, "测试信息")
        single_tabs.addTab(self.log_panel, "Log")

        single_layout.addWidget(single_tabs)
        self._stacked.addWidget(single_page)

        # 页1: 多通道布局 (QTabWidget) — 占位，运行时 rebuild
        self._multi_page = QWidget()
        self._multi_page_layout = QVBoxLayout(self._multi_page)
        self._multi_page_layout.setContentsMargins(0, 0, 0, 0)
        self._multi_page_layout.setSpacing(0)
        self._tab_widget: QTabWidget | None = None
        self._summary_tab: SummaryTab | None = None
        self._channel_tabs: dict[str, ChannelTab] = {}
        self._stacked.addWidget(self._multi_page)

        root.addWidget(self._stacked, 1)

    # ── 原生菜单栏 (macOS HIG Rule 1.1) ────────────────────────────────

    def _build_menu_bar(self):
        mb = self.menuBar()

        app_menu = mb.addMenu(APP_NAME)
        about_action = QAction(f"关于 {APP_NAME}", self)
        about_action.triggered.connect(self._show_about)
        app_menu.addAction(about_action)

        app_menu.addSeparator()
        # Check for Updates…（sparklehelper 集成）
        self._check_update_action = QAction("Check for Updates…", self)
        self._check_update_action.setEnabled(False)
        self._check_update_action.triggered.connect(
            lambda: self.check_update_triggered.emit()
        )
        app_menu.addAction(self._check_update_action)

        settings_action = QAction("仪器设置…", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self._show_instrument_settings)
        app_menu.addAction(settings_action)

        app_menu.addSeparator()
        quit_action = QAction(f"退出 {APP_NAME}", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        app_menu.addAction(quit_action)

        file_menu = mb.addMenu("文件")
        export_action = QAction("导出日志…", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        file_menu.addAction(export_action)
        file_menu.addSeparator()
        close_action = QAction("关闭窗口", self)
        close_action.setShortcut(QKeySequence.Close)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)

        edit_menu = mb.addMenu("编辑")
        undo_action = QAction("撤销", self)
        undo_action.setShortcut(QKeySequence.Undo)
        edit_menu.addAction(undo_action)
        redo_action = QAction("重做", self)
        redo_action.setShortcut(QKeySequence.Redo)
        edit_menu.addAction(redo_action)
        edit_menu.addSeparator()
        cut_action = QAction("剪切", self)
        cut_action.setShortcut(QKeySequence.Cut)
        edit_menu.addAction(cut_action)
        copy_action = QAction("复制", self)
        copy_action.setShortcut(QKeySequence.Copy)
        edit_menu.addAction(copy_action)
        paste_action = QAction("粘贴", self)
        paste_action.setShortcut(QKeySequence.Paste)
        edit_menu.addAction(paste_action)
        select_all = QAction("全选", self)
        select_all.setShortcut(QKeySequence.SelectAll)
        edit_menu.addAction(select_all)

        view_menu = mb.addMenu("视图")
        instr_action = QAction("仪器设置…", self)
        instr_action.setShortcut(QKeySequence("Ctrl+,"))
        instr_action.triggered.connect(self._show_instrument_settings)
        view_menu.addAction(instr_action)

        window_menu = mb.addMenu("窗口")
        minimize_action = QAction("最小化", self)
        minimize_action.setShortcut(QKeySequence("Ctrl+M"))
        minimize_action.triggered.connect(self.showMinimized)
        window_menu.addAction(minimize_action)

    # ── CSV 加载 ───────────────────────────────────────────────────────

    def _load_csv(self):
        try:
            self._test_plan = LimitsLoader(logger).load_test_data()
            print(self._test_plan.headers)
            self.test_table.load_config(self._test_plan.steps, self._test_plan.headers)
        except FileNotFoundError:
            QMessageBox.warning(
                self, "Config Error", "Limits.csv not found in resources/"
            )

    def _init_log(self):
        self._log_ctrl.initialize()
        self._log_ctrl.bind_signal(self.log_panel.append_log)

    # ── 信号连接 ──────────────────────────────────────────────────────

    def _connect_signals(self):
        self.control_bar.start_btn.clicked.connect(self._start_test)
        self.control_bar.sn_input.returnPressed.connect(self._start_test)
        self.control_bar.signal_gear_clicked.connect(self._show_instrument_settings)
        self._instr_mgr.signal_device_status.connect(self.control_bar.set_device_status)
        self._instr_mgr.signal_all_checked.connect(self._on_all_instruments_checked)
        self._sync_auto_mode()

    def _show_about(self):
        """打开"关于"窗口。"""
        AboutDialog(self).exec()

    def _show_instrument_settings(self):
        if self._instr_dialog is None:
            dlg = SettingsDialog(self)
            dlg.signal_reconnect.connect(self._on_instr_reconnect)
            dlg.signal_disconnect.connect(self._on_instr_disconnect)
            dlg.finished.connect(self._sync_auto_mode)  # 关闭后同步模式
            self._instr_mgr.signal_device_status.connect(dlg.set_device_status)
            self._instr_dialog = dlg
        self._instr_dialog.show()
        self._instr_dialog.raise_()
        self._instr_dialog.activateWindow()

    def _on_instr_reconnect(self, device_name: str):
        if device_name:
            self._instr_mgr.reconnect_device(device_name)
        else:
            self._instr_mgr.reconnect_all()

    def _on_instr_disconnect(self, device_name: str):
        self._instr_mgr.disconnect_device(device_name)

    def _on_all_instruments_checked(self):
        mgr = self._instr_mgr
        parts = []
        parts.append("34970A 已连接" if mgr.dmm_connected else "34970A 未连接")
        parts.append("IT6382 已连接" if mgr.ps_connected else "IT6382 未连接")
        parts.append("Relayboard 已连接" if mgr.relay_connected else "Relayboard 未连接")
        logger.info(f"仪器检测完成: {' | '.join(parts)}")

    # ── 测试流程 ──────────────────────────────────────────────────────

    def _start_test(self, only_channel: str = ""):
        if self._testing:
            return
        if self._instr_mgr.is_checking:
            self.log_panel.append_log("仪器检测中，请稍候…")
            return
        if self._multi_mode:
            self._start_multi_test(only_channel=only_channel)
            return

        sn = self.control_bar.sn_input.text().strip()

        self._testing = True
        self.control_bar.set_running(True)
        self.status_header.set_running()
        self.test_table.clear_results()
        self.log_panel.clear_log()
        self.control_bar.start_timer()

        self._runner = TestRunner(
            self._test_plan.steps, self._log_ctrl, instrument_manager=self._instr_mgr
        )
        self._runner.ScanSN = sn
        if self._single_dut_port:
            self._runner.test_unit._dut_port = self._single_dut_port
        self._runner.signal_value.connect(self.test_table.set_value)
        self._runner.signal_result.connect(self.test_table.set_result)
        self._runner.signal_color.connect(self.test_table.set_result_color)
        self._runner.signal_status.connect(self._on_status)
        self._runner.signal_stop.connect(self._on_test_completed)
        self._runner.signal_display.connect(self._on_display_sn)
        self._runner.start()

    def _sync_auto_mode(self):
        """关闭设置页后同步：更新多通道/单通道模式、location、控制栏等。"""
        cfg = load_config()
        auto = cfg.get("auto_test_mode", False)
        loc = cfg.get("dut_location_id", "")
        new_multi = cfg.get("multi_channel_mode", False)

        # 多通道模式变化 → 提示重启
        if new_multi != self._multi_mode:
            self._multi_mode = new_multi
            if new_multi:
                self._rebuild_multi_channel_tabs()
                self._stacked.setCurrentIndex(1)
                self._dut_monitor.pause()
                self._init_multi_monitor()
            else:
                self._stacked.setCurrentIndex(0)
                self.control_bar.set_multi_mode(False)
                self._dut_monitor.set_location_id(loc)
                self._dut_monitor.resume()
                if self._multi_monitor:
                    self._multi_monitor.stop_monitor()
                    self._multi_monitor = None

        self.control_bar.set_auto_mode(auto)
        self._dut_monitor.set_location_id(loc)
        self.log_panel.set_auto_scroll(cfg.get("auto_scroll_log", True))
        self.test_table.set_auto_scroll(cfg.get("auto_scroll_log", True))

        if auto:
            self.log_panel.append_log(f"自动测试模式 — location={loc}")
        else:
            self.log_panel.append_log("手动测试模式")

        if self._multi_mode:
            self.log_panel.append_log(f"多通道模式: {cfg.get('channel_count', 4)} 通道")

    def _on_dut_detected(self, device: str):
        """DUT 串口检测到 → 状态灯亮绿，自动模式才触发测试。"""
        self._single_dut_port = device
        self.control_bar.set_dut_status(True)
        self.log_panel.append_log(f"DUT 已连接: {device}")
        cfg = load_config()
        if cfg.get("auto_test_mode", False):
            self._start_test()

    def _on_dut_lost(self):
        """DUT 串口断开 → 中止测试并判定 Fail。"""
        self._single_dut_port = None
        self.control_bar.set_dut_status(False)
        self.log_panel.append_log("DUT 已断开")
        if self._runner and self._runner.isRunning():
            self._runner.abort()
            self.log_panel.append_log("DUT 已拔出，中止测试并判定 Fail")

    # ── 多通道 DUT 监控 ──────────────────────────────────────────────

    def _init_multi_monitor(self):
        """初始化多通道 DUT 监控（从 channel_config 读取各通道 location_id）。"""
        ch_cfg = load_channel_config()
        loc_ids = ch_cfg.get("location_ids", [])
        channel_loc_map: dict[str, str] = {}
        cfg = load_config()
        channel_count = cfg.get("channel_count", 4)
        if self._platform == PLATFORM_WINDOWS:
            # Windows 使用 Location path（如 1-3.4）匹配 Slot；留空则按 Hub 端口尾号
            for i in range(channel_count):
                ch = f"CH{i + 1}"
                channel_loc_map[ch] = loc_ids[i] if i < len(loc_ids) else ""
        else:
            for i in range(channel_count):
                ch = f"CH{i + 1}"
                loc = loc_ids[i] if i < len(loc_ids) else ""
                if loc:
                    channel_loc_map[ch] = loc

        if self._multi_monitor:
            self._multi_monitor.stop_monitor()
            self._multi_monitor.channel_dut_detected.disconnect()
            self._multi_monitor.channel_dut_lost.disconnect()

        self._multi_monitor = create_multi_channel_monitor(
            channel_loc_map,
            platform=self._platform,
            interface=cfg.get("dut_interface", ""),
            vid=cfg.get("dut_vid", ""),
            pid=cfg.get("dut_pid", ""),
        )
        self._multi_monitor.channel_dut_detected.connect(self._on_channel_dut_detected)
        self._multi_monitor.channel_dut_lost.connect(self._on_channel_dut_lost)
        self._multi_monitor.start()

    def _on_channel_dut_detected(self, channel_id: str, device: str):
        """多通道模式下某通道 DUT 检测到 → 自动模式触发测试。"""
        self._slot_ports[channel_id] = device
        ct = self._channel_tabs.get(channel_id)
        if ct:
            ct.append_log(f"DUT 已连接: {device}")
        cfg = load_config()
        if cfg.get("auto_test_mode", False):
            if not self._is_channel_enabled(channel_id):
                self.log_panel.append_log(
                    f"[{channel_id}] 未勾选“是否测试”，跳过自动测试"
                )
                return
            self.log_panel.append_log(f"[{channel_id}] DUT 已连接，自动开始测试")
            self._start_test(only_channel=channel_id)

    def _on_channel_dut_lost(self, channel_id: str):
        """多通道模式下某通道 DUT 断开。"""
        self._slot_ports.pop(channel_id, None)
        runner = self._runner_by_channel.get(channel_id)
        if runner and runner.isRunning():
            runner.abort()
            self.log_panel.append_log(f"[{channel_id}] DUT 已拔出，中止测试并判定 Fail")
        ct = self._channel_tabs.get(channel_id)
        if ct:
            ct.append_log("DUT 已断开")

    def _on_status(self, passed: bool):
        self.status_header.add_result(passed)
        if passed:
            self.status_header.set_pass()
        else:
            self.status_header.set_fail()

    def _on_test_completed(self):
        self._testing = False
        self.control_bar.stop_timer()
        self.control_bar.set_running(False)
        self.control_bar.sn_input.clear()
        self.control_bar.sn_input.setFocus()
        self._dut_monitor.resume()

    def _on_display_sn(self, scan_sn: str, fgsn: str):
        self.statusBar().showMessage(f"ScanSN: {scan_sn}  |  FGSN: {fgsn}")

    def set_update_enabled(self, enabled: bool):
        """sparklehelper 回调：启用/禁用 Check for Updates 菜单项。"""
        if hasattr(self, "_check_update_action"):
            self._check_update_action.setEnabled(enabled)

    # ── 多通道测试 ──────────────────────────────────────────────────

    def _channel_enabled_flags(self, count: int | None = None,
                               refresh: bool = False) -> list[bool]:
        """读取每个通道的“是否测试”勾选状态，缺省视为勾选。

        首次读取后缓存，设置变更需重启后重新加载。
        """
        cfg = load_config()
        if count is None:
            count = cfg.get("channel_count", 4)
        if not refresh and self._channel_flags:
            return self._channel_flags[:count]
        ch_cfg = load_channel_config()
        flags = ch_cfg.get("channels_enabled")
        if flags is None:
            flags = cfg.get("channel_test_enabled", [])
        self._channel_flags = [
            flags[i] if i < len(flags) else True for i in range(8)
        ]
        return self._channel_flags[:count]

    def _is_channel_enabled(self, channel_id: str) -> bool:
        try:
            index = int(channel_id.upper().replace("CH", "")) - 1
        except ValueError:
            return False
        flags = self._channel_enabled_flags()
        return 0 <= index < len(flags) and flags[index]

    def _rebuild_multi_channel_tabs(self):
        """重建多通道 TabWidget（Summary + 各通道 Tab）。"""
        cfg = load_config()
        channel_count = cfg.get("channel_count", 4)
        flags = self._channel_enabled_flags(channel_count, refresh=True)

        # 清除旧 tab
        if self._tab_widget:
            self._multi_page_layout.removeWidget(self._tab_widget)
            self._tab_widget.deleteLater()

        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; }}
            QTabBar::tab {{
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
                color: {Colors.TEXT_SECONDARY};
                border: none;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {Colors.PRIMARY};
                border-bottom: 2px solid {Colors.PRIMARY};
            }}
        """)

        # Summary Tab
        self._summary_tab = SummaryTab(channel_count, flags)
        self._summary_tab.channel_selected.connect(self._on_summary_channel_selected)
        self._tab_widget.addTab(self._summary_tab, "Summary")

        # 通道 Tabs
        self._channel_tabs = {}
        for i in range(channel_count):
            ch = f"CH{i + 1}"
            ct = ChannelTab(ch)
            ct.load_config(self._test_plan.steps, self._test_plan.headers)
            ct.set_auto_scroll(cfg.get("auto_scroll_log", True))
            ct.set_test_enabled(flags[i])
            self._channel_tabs[ch] = ct
            self._tab_widget.addTab(ct, ch)

        self._multi_page_layout.addWidget(self._tab_widget)
        self.control_bar.set_multi_mode(True)

    def _start_multi_test(self, only_channel: str = ""):
        """多通道并行测试。only_channel 为空=全通道启动，指定=只启动该通道。"""

        cfg = load_config()
        channel_count = cfg.get("channel_count", 4)
        flags = self._channel_enabled_flags(channel_count)
        enabled_channels = {
            f"CH{i + 1}" for i in range(channel_count) if flags[i]
        }
        if self._platform == PLATFORM_WINDOWS:
            # Windows 必须由 Slot 监控给出明确 COM 口，避免多个通道抢占同一串口
            enabled_channels = {
                ch for ch in enabled_channels if self._slot_ports.get(ch)
            }

        if only_channel:
            if only_channel not in enabled_channels:
                self.log_panel.append_log(
                    f"{only_channel} 未勾选或未检测到 DUT，已跳过"
                )
                return
            ct = self._channel_tabs.get(only_channel)
            if ct:
                ct.set_running(True)
            if self._summary_tab:
                card = self._summary_tab.get_card(only_channel)
                if card:
                    card.set_running()
            self.log_panel.append_log(f"{only_channel} 手动启动…")
            self._batch_channels.add(only_channel)
        else:
            if not enabled_channels:
                self.log_panel.append_log(
                    "没有可启动的通道（需勾选且已检测到 DUT），已取消启动"
                )
                return
            self._batch_channels = set(enabled_channels)
            self.control_bar.set_running(True)
            self.status_header.reset()
            self.control_bar.start_timer()
            if self._summary_tab:
                self._summary_tab.reset_all(clear_counts=False)
                for ch_id, card in self._summary_tab.cards.items():
                    if ch_id in enabled_channels:
                        card.set_running()
            self.status_header.set_running()
            self.log_panel.append_log(
                f"全局 Start — 启动 {len(enabled_channels)} 个通道"
            )

        ch_cfg = load_channel_config()
        loc_ids = ch_cfg.get(
            "location_ids", cfg.get("channel_location_ids", ["", "", "", ""])
        )
        fail_stop = cfg.get("fail_stop_test", True)

        for i in range(channel_count):
            ch = f"CH{i + 1}"

            # 未勾选“是否测试” → 仅展示，不参与测试
            if not flags[i]:
                continue

            # Windows 未检测到 Slot 串口或未勾选 → 跳过
            if ch not in enabled_channels:
                continue

            # only_channel 模式：只启动指定通道
            if only_channel and ch != only_channel:
                continue

            # 该通道已在跑 → 跳过
            if ch in self._multi_testing_channels:
                continue

            ct = self._channel_tabs.get(ch)
            if ct:
                ct.clear_results()
                ct.set_running(True)

            sn = ""
            if self._summary_tab:
                card = self._summary_tab.get_card(ch)
                if card:
                    sn = card.get_sn()

            loc_id = loc_ids[i] if i < len(loc_ids) else ""

            runner = ChannelRunner(
                channel_id=ch,
                csv_rows=self._test_plan.steps,
                location_id=loc_id,
                sn=sn,
                fail_stop=fail_stop,
                dut_port=self._slot_ports.get(ch),
            )
            runner.signal_value.connect(self._on_channel_value)
            runner.signal_result.connect(self._on_channel_result)
            runner.signal_color.connect(self._on_channel_color)
            runner.signal_channel_done.connect(self._on_channel_done)
            runner.signal_log.connect(self._on_channel_log)
            runner.signal_display.connect(self._on_channel_display)
            self._runners.append(runner)
            self._runner_by_channel[ch] = runner
            self._multi_testing_channels.add(ch)
            runner.start()

    def _on_channel_value(self, ch: str, display: str, value: str):
        ct = self._channel_tabs.get(ch)
        if ct:
            ct.set_value(ch, display, value)

    def _on_channel_result(self, ch: str, display: str, result: str):
        ct = self._channel_tabs.get(ch)
        if ct:
            ct.set_result(ch, display, result)

    def _on_channel_color(self, ch: str, display: str, result: str):
        ct = self._channel_tabs.get(ch)
        if ct:
            ct.set_result_color(ch, display, result)

    def _on_channel_log(self, ch: str, msg: str):
        ct = self._channel_tabs.get(ch)
        if ct:
            ct.append_log(msg)

    def _on_channel_done(self, ch: str, overall_pass: bool):
        self._multi_testing_channels.discard(ch)
        self._runner_by_channel.pop(ch, None)
        card = self._summary_tab.get_card(ch) if self._summary_tab else None
        if card:
            card.set_finished(overall_pass)
            card.clear_sn()
        ct = self._channel_tabs.get(ch)
        if ct:
            ct.set_done(overall_pass)
        # 检查是否全部完成
        if not self._multi_testing_channels:
            self._on_all_channels_done()

    def _on_channel_display(self, ch: str, scan_sn: str, fgsn: str):
        self.statusBar().showMessage(f"[{ch}] ScanSN: {scan_sn}  |  FGSN: {fgsn}")

    def _on_all_channels_done(self):
        self.control_bar.stop_timer()
        self.control_bar.set_running(False)
        self._dut_monitor.resume()
        # 汇总最终结果（只统计本轮实际启动的通道）
        if self._summary_tab:
            flags = self._channel_enabled_flags()
            channels = (
                self._batch_channels
                if self._batch_channels
                else {
                    f"CH{i + 1}" for i, flag in enumerate(flags) if flag
                }
            )
            any_fail = False
            for ch in channels:
                card = self._summary_tab.get_card(ch)
                if card and (not card._finished or not card._overall_pass):
                    any_fail = True
                    break
            self._batch_channels.clear()
            if any_fail:
                self.status_header.set_fail()
            else:
                self.status_header.set_pass()

    def _on_summary_channel_selected(self, channel_id: str):
        """Summary 页点击通道卡片 → 切换到对应 Tab。"""
        if self._tab_widget and channel_id in self._channel_tabs:
            for i in range(self._tab_widget.count()):
                if self._tab_widget.tabText(i) == channel_id:
                    self._tab_widget.setCurrentIndex(i)
                    break

    # ── 退出 ─────────────────────────────────────────────────────────

    def closeEvent(self, event):
        # 停止所有多通道 runner
        for runner in self._runners:
            if runner.isRunning():
                runner.test_unit.close_dut()
                runner.running = False  # 标记停止，run() 循环下次迭代退出
                runner.quit()  # 兼容 event-loop 线程
                runner.wait(3000)  # 最多等3秒
                if runner.isRunning():
                    runner.terminate()  # 兜底强制终止
                    runner.wait(1000)
        self._dut_monitor.stop_monitor()
        if self._multi_monitor:
            self._multi_monitor.stop_monitor()
        self._instr_mgr.shutdown()
        event.accept()
