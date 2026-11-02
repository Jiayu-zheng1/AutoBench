"""更新控制器 — sparklehelper 集成（Sparkle 自动更新检查）。

参照 sparklehelper Qt Demo 模式，PySide6 兼容：
- Updater 延迟启动（QTimer.singleShot 在事件循环启动后调用）
- KVO 回调通过 Qt Signal 更新菜单状态
- check_for_updates() 触发原生 Sparkle 更新窗口

注意：sparklehelper 只能在打包后的 .app 内运行，直接 python main.py 会优雅降级。
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from app.utils.logger import get_logger

logger = get_logger("UpdateController")

# 自动更新源 — 留空即禁用「检查更新」，填 Appcast 地址与 Ed25519 公钥后生效
FEED_URL = ""
PUBLIC_KEY = ""


class UpdateController(QObject):
    """sparklehelper 包装器 — 管理 Updater 生命周期 + Qt 信号桥接。"""

    can_check_changed = Signal(bool)  # can_check_for_updates 状态变化
    error_occurred = Signal(str)      # Updater 启动失败

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updater = None
        self._subscription = None
        self._started = False
        self._uses_can_check_observer = True

    def initialize(self):
        """构造 Updater（不启动），延迟到事件循环运行后调用 start()。"""
        if not FEED_URL:
            logger.info("未配置更新源，自动更新已禁用")
            return
        try:
            from sparklehelper import Updater

            self._updater = Updater(
                start=False,
                feed_url=FEED_URL,
                public_key=PUBLIC_KEY,
            )
            logger.info("sparklehelper Updater 已构造")
        except Exception as exc:
            logger.warning(f"sparklehelper 不可用 (非 .app 环境或未安装): {exc}")
            # 优雅降级：菜单项保持灰色
            return

        # KVO 订阅 can_check_for_updates
        try:
            self._subscription = self._updater.observe_can_check_for_updates(
                lambda can_check: self.can_check_changed.emit(bool(can_check))
            )
        except NotImplementedError:
            self._uses_can_check_observer = False
            logger.info("observe_can_check_for_updates 不可用，使用手动模式")

        # QTimer.singleShot(0, ...) 等价于 wx.CallAfter，在 Qt 事件循环启动后执行
        QTimer.singleShot(0, self._start_updater)

    def _start_updater(self):
        """延迟启动 Updater — 必须在 Qt 事件循环运行后调用。"""
        if self._updater is None:
            return
        try:
            self._updater.start()
            self._started = True
            logger.info("sparklehelper Updater 已启动")
            if not self._uses_can_check_observer:
                self.can_check_changed.emit(True)
        except Exception as exc:
            msg = str(exc)
            logger.warning(f"sparklehelper start 失败: {msg}")
            self.error_occurred.emit(msg)

    def check_for_updates(self):
        """触发 Sparkle 原生检查更新窗口。"""
        if self._updater is not None and self._started:
            try:
                self._updater.check_for_updates()
                logger.info("手动触发检查更新")
            except Exception as exc:
                logger.error(f"check_for_updates 失败: {exc}")

    def cleanup(self):
        """退出前清理。"""
        if self._subscription is not None:
            try:
                self._subscription.cancel()
            except Exception:
                pass
        if self._updater is not None:
            try:
                self._updater.cleanup()
            except Exception:
                pass
        logger.info("sparklehelper 已清理")
