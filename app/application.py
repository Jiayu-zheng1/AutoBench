"""QApplication bootstrap and lifecycle."""

import sys

from PySide6.QtWidgets import QApplication

from app.controllers.update_controller import UpdateController
from app.utils.constants import APP_NAME, APP_VERSION
from app.views.main_window import MainWindow


class Application:
    """Manages QApplication lifecycle."""

    def __init__(self):
        self._qapp = None
        self._window = None
        self._updater: UpdateController | None = None

    def create(self):
        self._qapp = QApplication(sys.argv)
        self._qapp.setApplicationName(APP_NAME)
        self._qapp.setApplicationDisplayName(APP_NAME)
        self._qapp.setApplicationVersion(APP_VERSION)
        self._qapp.setOrganizationName(APP_NAME)
        self._window = MainWindow()

        # sparklehelper 更新控制器 — 延迟初始化（在事件循环启动后 start）
        self._updater = UpdateController()
        self._updater.can_check_changed.connect(self._window.set_update_enabled)
        self._window.check_update_triggered.connect(self._on_check_for_updates)
        self._updater.initialize()

    def show(self):
        self._window.show()

    def run(self):
        exit_code = self._qapp.exec()
        if self._updater:
            self._updater.cleanup()
        return sys.exit(exit_code)

    def _on_check_for_updates(self):
        if self._updater:
            self._updater.check_for_updates()
