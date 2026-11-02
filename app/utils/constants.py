"""Application-wide constants."""

import os

APP_NAME = "AutoBench"
APP_VERSION = "1.0.1"
PRODUCT = ""
SITE = ""

RESOURCE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "resources")
MAIN_CSV = os.path.join(RESOURCE_DIR, "Main.csv")
LIMITS_CSV = os.path.join(RESOURCE_DIR, "Limits.csv")

CSV_DIR = os.path.expanduser("~/Documents/AutoBench/Test_CSV")
CONFIG_DIR = os.path.expanduser("~/Documents/AutoBench")
INSTRUMENT_CONFIG_PATH = os.path.join(CONFIG_DIR, "instrument_config.json")
CHANNEL_CONFIG_PATH = os.path.join(CONFIG_DIR, "channel_config.json")

DEFAULT_BAUDRATE = 115200
SERIAL_TIMEOUT = 0.1
DUT_CONNECT_TIMEOUT = 5

SN_MAX_LENGTH = 10
