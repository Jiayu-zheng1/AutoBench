"""仪器抽象基类 — 统一连接/断开/身份查询接口。"""

from abc import ABC, abstractmethod


class BaseInstrument(ABC):
    """所有仪器的公共接口。

    子类必须实现:
        connect()       — 建立连接，返回 True/False
        disconnect()    — 断开连接
        get_identity()  — 返回 IDN 字符串，不支持则返回 None
        is_connected    — property，当前是否连接
    """

    @abstractmethod
    def connect(self) -> bool:
        """建立连接。返回 True 表示成功，False 表示失败。"""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """断开连接并释放资源。"""
        ...

    @abstractmethod
    def get_identity(self) -> str | None:
        """查询仪器识别字符串（*IDN?），不支持则返回 None。"""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """当前是否处于连接状态。"""
        ...
