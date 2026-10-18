"""Global configuration and on-disk paths for NetHawk."""
import os

APP_NAME = "NetHawk"
APP_VERSION = "2.0.0"

# How often (seconds) to re-send ARP poison packets while a target is cut/throttled.
SPOOF_INTERVAL = 2.0

# Default ARP scan timeout (seconds).
SCAN_TIMEOUT = 2.5

# Accent / brand color (used by the theme and some widgets).
ACCENT = "#12d6a2"


def data_dir() -> str:
    """Per-user writable folder for the device database, logs, vendor cache."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") \
        or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def devices_db_path() -> str:
    return os.path.join(data_dir(), "devices.json")


def firewall_db_path() -> str:
    return os.path.join(data_dir(), "firewall.json")


def schedule_db_path() -> str:
    return os.path.join(data_dir(), "schedule.json")


def settings_path() -> str:
    return os.path.join(data_dir(), "settings.json")


def log_path() -> str:
    return os.path.join(data_dir(), "nethawk.log")
