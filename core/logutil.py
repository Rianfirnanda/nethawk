"""Tiny logging helper: writes to a rotating-ish file and keeps an in-memory
callback so the GUI can show the same lines in its log panel."""
import datetime
import threading

from . import config

_lock = threading.Lock()
_listeners = []  # list of callables(str)


def add_listener(fn):
    _listeners.append(fn)


def log(message: str, level: str = "INFO"):
    stamp = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{stamp}] {level}: {message}"
    with _lock:
        try:
            with open(config.log_path(), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
    for fn in list(_listeners):
        try:
            fn(line)
        except Exception:
            pass
