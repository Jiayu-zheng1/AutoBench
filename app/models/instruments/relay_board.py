# Peng Wu
# For relay board.
# v1.5 增加断电重连

import threading
import time

import serial

from app.models.instruments.base import BaseInstrument


class RELAYBOARD(BaseInstrument):
    def __init__(self, boardVER, port):
        self.hex_values = {}
        self.boardVER = boardVER
        self.port = port
        self.baudrate = ''
        self.ser = None
        self._connected = False
        self._lock = threading.Lock()

    # ── BaseInstrument 接口 ──

    def connect(self) -> bool:
        result = self.init_board()
        self._connected = result is not None
        return self._connected

    def disconnect(self) -> None:
        self._connected = False
        self.close()

    def get_identity(self) -> str | None:
        return None  # 继电器板不支持 IDN 查询

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── 原有方法 ──

    def init_board(self):
        """初始化继电器板，按照版本加载命令表"""
        if self.boardVER == '1':
            boardcmds = {
                0: ['FF', 'FF'],
                1: ['A00100A1', 'A00101A2'],
                2: ['A00200A2', 'A00201A3'],
                3: ['A00300A3', 'A00301A4'],
                4: ['A00400A4', 'A00401A5'],
                5: ['A00500A5', 'A00501A6'],
                6: ['A00600A6', 'A00601A7'],
                7: ['A00700A7', 'A00701A8'],
                8: ['A00800A8', 'A00801A9'],
            }
            self.baudrate = '9600'
        elif self.boardVER == '0':
            boardcmds = {
                0: ['6E', '64'],
                1: ['6F', '65'],
                2: ['70', '66'],
                3: ['71', '67'],
                4: ['72', '68'],
                5: ['73', '69'],
                6: ['74', '6A'],
                7: ['75', '6B'],
                8: ['76', '6C'],
            }
            self.baudrate = '19200'

        for key, cmd_pair in boardcmds.items():
            self.hex_values[key] = [bytes.fromhex(cmd) for cmd in cmd_pair]

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self._connected = True
            return self.ser
        except Exception as e:
            print(f"Relayboard init error: {e}")
            self._connected = False
            return None

    def relay_ON(self, channel):
        time.sleep(0.01)
        try:
            if not self.ser:
                print("Error: Serial connection is not established.")
                return
            if channel not in self.hex_values:
                raise ValueError("Invalid slot value. Please provide 1-8.")
            # 用于断电重连
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self.ser.write(self.hex_values[channel][1])
        except Exception as e:
            print(f"An error occurred while turning on relay {channel}: {e}")
            return

    def relay_OFF(self, channel):
        time.sleep(0.01)
        try:
            if not self.ser:
                print("Error: Serial connection is not established.")
                return
            if channel not in self.hex_values:
                raise ValueError("Invalid slot value. Please provide 1-8.")
            self.ser.write(self.hex_values[channel][0])
        except Exception as e:
            print(f"An error occurred while turning off relay {channel}: {e}")
            return

    def turn_on_relays(self, channels):
        with self._lock:
            for channel in channels:
                try:
                    self.relay_ON(channel)
                except Exception as e:
                    print(f"An error occurred while turning on relay {channel}: {e}")

    def turn_off_relays(self, channels):
        with self._lock:
            for channel in channels:
                try:
                    self.relay_OFF(channel)
                except Exception as e:
                    print(f"An error occurred while turning off relay {channel}: {e}")
                    return False
            return True

    def close(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
                self.ser = None
        except Exception as e:
            print(f"An error occurred: {e}")
