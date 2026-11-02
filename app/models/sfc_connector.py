"""SFC 上传模块 — HTTP 方式向 SFC 系统上报测试结果（PASS/FAIL）。"""
import urllib.request
from datetime import datetime

from app.utils.logger import get_logger

logger = get_logger("SFC")


class SFCConnector:
    """SFC 连接器 — 在线/离线模式切换，URL + VIP 方式通信。"""

    def __init__(self, url: str = "", vip: str = "", online: bool = False):
        self.url = url
        self.vip = vip
        self.online = online  # UOP 在线模式

    def _execute(self, p_cmd: str, p_data: str) -> str:
        """执行 SFC 命令，返回响应文本。"""
        full_url = f"{self.url}vip={self.vip}&p_cmd={p_cmd}&p_data={p_data}"
        logger.debug(f"SFC 请求: {full_url}")
        start = datetime.now()

        try:
            req = urllib.request.Request(full_url)
            fd = urllib.request.urlopen(req, timeout=5).read()
            resp = fd.decode("utf-8")
            # 提取 <string ...>...</string> 之间的内容
            import re
            match = re.search(r"org/['\"]?\s*>\s*(.+?)\s*</string", resp, re.DOTALL)
            result = match.group(1).strip() if match else resp
            elapsed = (datetime.now() - start).total_seconds()
            logger.info(f"SFC 返回: {result} ({elapsed:.2f}s)")
            return result
        except Exception as e:
            logger.error(f"SFC 请求异常: {e}")
            return str(e)

    # ── 核心 API ────────────────────────────────────────────────────────

    def connect(self) -> str:
        """连接 SFC 服务器。"""
        if not self.online:
            return "OK"
        return self._execute("1", f"{self.vip};")

    def check_route(self, sn: str) -> str:
        """检查 SN 是否在当站。"""
        if not self.online:
            return "OK"
        return self._execute("2", f"{sn};")

    def upload_result(self, sn: str, passed: bool, error_code: str = "ATE_NG") -> str:
        """上传测试结果 (PASS/FAIL)。"""
        if not self.online:
            return "OK"
        if passed:
            return self._execute("53", f"{self.vip};{sn};OK;")
        return self._execute("53", f"{self.vip};{sn};NG;{error_code}")
