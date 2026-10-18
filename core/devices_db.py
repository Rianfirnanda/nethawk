"""Persistent device registry (keyed by MAC): custom name/alias, first/last seen.
Lets the UI flag brand-new devices and remember names across sessions.
"""
import json
import threading
import time

from . import config
from .logutil import log


class DeviceDB:
    def __init__(self):
        self._path = config.devices_db_path()
        self._lock = threading.Lock()
        self._data = {}   # mac -> {"name": str, "first_seen": ts, "last_seen": ts}
        self._load()

    def _load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            self._data = {}

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            log("Gagal simpan devices.json: %s" % e, "WARN")

    def name_of(self, mac: str) -> str:
        with self._lock:
            return self._data.get(mac.lower(), {}).get("name", "")

    def set_name(self, mac: str, name: str):
        mac = mac.lower()
        with self._lock:
            entry = self._data.setdefault(mac, {})
            entry["name"] = name
            self._save()
        log("Nama device %s diset: %s" % (mac, name))

    def role_of(self, mac: str) -> str:
        with self._lock:
            return self._data.get(mac.lower(), {}).get("role", "guest")

    def set_role(self, mac: str, role: str):
        mac = mac.lower()
        with self._lock:
            entry = self._data.setdefault(mac, {})
            entry["role"] = role
            self._save()
        log("Role device %s: %s" % (mac, role))

    def is_known(self, mac: str) -> bool:
        with self._lock:
            return mac.lower() in self._data

    def seen(self, mac: str) -> bool:
        """Record a sighting. Returns True if this MAC is brand new."""
        mac = mac.lower()
        now = time.time()
        with self._lock:
            new = mac not in self._data
            entry = self._data.setdefault(mac, {"name": "", "first_seen": now})
            entry["last_seen"] = now
            self._save()
        return new
