"""Bandwidth throttling via WinDivert (Windows only, EXPERIMENTAL).

How it works:
  1. The spoofer poisons the target in "throttle" mode so the target's traffic
     transits THIS machine.
  2. Windows must route that transit traffic (IP forwarding). enable_forwarding()
     sets the registry flag and (re)starts the RemoteAccess service; a reboot may
     still be required on some systems.
  3. WinDivert captures forwarded packets to/from each throttled IP and applies a
     per-IP token bucket. Packets over budget are dropped (not re-injected), which
     makes TCP back off -> effective rate limiting. Packets within budget are
     re-injected so the device still works, just slower.

This module is defensive by construction: if pydivert is missing, we lack admin,
or anything throws, it logs a warning and becomes a no-op instead of crashing.
"""
import subprocess
import threading
import time

from .logutil import log


class ThrottleManager:
    def __init__(self):
        self._limits = {}          # ip -> bytes_per_sec (0 = unlimited)
        self._tokens = {}          # ip -> current token balance (bytes)
        self._last = {}            # ip -> last refill timestamp
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self._forwarding_enabled = False

    @property
    def active(self) -> bool:
        return self._running

    # ---- limits ---------------------------------------------------------
    def set_limit(self, ip: str, kbps: float):
        """kbps = kilobits/sec. 0 removes the limit."""
        bps = max(0.0, kbps) * 1000 / 8.0  # -> bytes/sec
        with self._lock:
            if bps <= 0:
                self._limits.pop(ip, None)
                self._tokens.pop(ip, None)
            else:
                self._limits[ip] = bps
                self._tokens.setdefault(ip, bps)
                self._last.setdefault(ip, time.time())
            any_left = bool(self._limits)
        log("Throttle %s -> %s kbps" % (ip, kbps))
        if any_left:
            self.start()
        elif not any_left:
            self.stop()

    def remove(self, ip: str):
        self.set_limit(ip, 0)

    def limited_ips(self):
        with self._lock:
            return dict(self._limits)

    # ---- engine ---------------------------------------------------------
    def start(self):
        if self._running:
            return
        self.enable_forwarding()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def enable_forwarding(self):
        """Turn on Windows IP forwarding so transit packets are routed to us."""
        if self._forwarding_enabled:
            return
        try:
            subprocess.run([
                "reg", "add",
                r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                "/v", "IPEnableRouter", "/t", "REG_DWORD", "/d", "1", "/f",
            ], capture_output=True, shell=False)
            # Try to start routing without a reboot.
            subprocess.run(["sc", "config", "RemoteAccess", "start=", "auto"],
                           capture_output=True, shell=False)
            subprocess.run(["net", "start", "RemoteAccess"],
                           capture_output=True, shell=False)
            self._forwarding_enabled = True
            log("IP forwarding diaktifkan (mungkin perlu reboot bila throttle "
                "tidak langsung bekerja).")
        except Exception as e:
            log("Gagal mengaktifkan IP forwarding: %s" % e, "WARN")

    def _run(self):
        try:
            import pydivert
        except Exception as e:
            log("Throttle nonaktif (pydivert/WinDivert tidak tersedia): %s" % e,
                "WARN")
            self._running = False
            return
        try:
            # Capture forwarded (transit) IP packets.
            with pydivert.WinDivert("ip", layer=pydivert.Layer.NETWORK_FORWARD) as w:
                for packet in w:
                    if not self._running:
                        w.send(packet)
                        break
                    if self._allow(packet):
                        w.send(packet)
                    # else: drop -> throttle
        except Exception as e:
            log("Engine throttle berhenti: %s" % e, "WARN")
            self._running = False

    def _allow(self, packet) -> bool:
        ip = None
        for cand in (getattr(packet, "src_addr", None),
                     getattr(packet, "dst_addr", None)):
            if cand in self._limits:
                ip = cand
                break
        if ip is None:
            return True  # not throttled -> pass straight through
        size = len(packet.raw)
        now = time.time()
        with self._lock:
            rate = self._limits.get(ip, 0)
            if rate <= 0:
                return True
            tokens = self._tokens.get(ip, rate)
            last = self._last.get(ip, now)
            tokens = min(rate, tokens + (now - last) * rate)  # refill (1s burst)
            self._last[ip] = now
            if tokens >= size:
                tokens -= size
                self._tokens[ip] = tokens
                return True
            self._tokens[ip] = tokens
            return False
