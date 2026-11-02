"""DUT 串口通信层 — 连接/断开/检查 + 设备状态。

从 TestItem 裂变出来，职责单一：管理单个 DUT 的串口连接生命周期。
"""

import time

from app.models.device import Device, get_ports
from app.utils.logger import get_logger

logger = get_logger("DUT")


class DutCommunicator:
    """DUT 串口通信 — 管理 DUT 连接状态。

    属性（外部可读写）:
        ScanSN: str      扫描序列号
        FGSN: str        固件序列号（从 DUT 读取后写入）
        MLBSN: str       MLB 序列号（从 DUT 读取后写入）
        dut: Device|None  DUT 设备实例
        _dut_port: str|None  DUT 串口路径
                              "__unset__" = 自动探测
                              None = DUT 不存在（多通道未检测到）
                              str = 指定串口路径
    """

    def __init__(self):
        self.ScanSN: str = None
        self.FGSN: str = None
        self.MLBSN: str = None
        self.dut: Device | None = None
        self._dut_port: str | None = "__unset__"

    def connent_dut(self, timeout: float = 5) -> bool:
        """连接 DUT 串口。

        _dut_port=None 时跳过（多通道未检测到 DUT 场景）。
        _dut_port="__unset__" 时自动探测第一个可用串口。
        返回 True/False。
        """
        # DUT 串口明确不存在（多通道模式下 location_id 搜不到）
        if self._dut_port is None:
            logger.info("DUT 串口不存在（多通道未检测到该通道 DUT），跳过连接")
            return False

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if self._dut_port and self._dut_port != "__unset__":
                    port_path = self._dut_port  # 指定端口
                else:
                    ports = get_ports()
                    port_path = ports[0].device if ports else None

                if not port_path:
                    time.sleep(0.1)
                    continue
                dut = Device()
                dut.open_get_port(port=port_path, baudrate=921600)
                if dut.ser and dut.ser.is_open:
                    logger.info(f"DUT 连接成功: {port_path}")
                    self.dut = dut
                    return True
            except Exception as e:
                logger.info(f"open serial Fail: {e}")
            time.sleep(0.1)
        logger.info("连接超时")
        return False

    def close_dut(self):
        """断开 DUT 串口。"""
        if self.dut is not None:
            self.dut.close_port()
            logger.info("DUT has been shut down ")
            self.dut = None

    def Info_CheckDUT(self) -> bool:
        """检查 DUT 连接状态，未连接则尝试连接。返回 True/False。"""
        if self.dut is None:
            self.connent_dut()
            if self.dut:
                return True
            else:
                logger.info("DUT connection Fail")
                return False
