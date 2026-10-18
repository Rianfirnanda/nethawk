"""Shared application state + high-level actions, wrapping all core engines.
Pages talk to this; main_window owns the single instance and the timers."""
from PySide6.QtCore import QObject, QThread, Signal

from core import scanner, vendor, devicetype
from core.network import NetworkInfo
from core.devices_db import DeviceDB
from core.firewall import Firewall
from core.spoofer import Spoofer
from core.protection import ArpProtector
from core.monitor import Throughput
from core.engine import Engine
from core.scheduler import Scheduler
from core.logutil import add_listener

from .theme import ACCENT, ACCENT2, DANGER, WARN, DIM, MUTED


class ScanWorker(QThread):
    device = Signal(dict)
    done = Signal(int)
    error = Signal(str)

    def __init__(self, net):
        super().__init__()
        self.net = net

    def run(self):
        try:
            found = scanner.arp_scan(self.net.cidr, self.net.iface,
                                     local_ip=self.net.local_ip,
                                     local_mac=self.net.local_mac)
        except Exception as e:
            self.error.emit(str(e))
            return
        for dev in found:
            scanner.enrich(dev, self.net.iface, do_os=False)
            typ, emoji = devicetype.guess(dev.get("vendor", ""),
                                          dev.get("hostname", ""))
            dev["type"] = typ
            dev["emoji"] = emoji
            self.device.emit(dev)
        self.done.emit(len(found))


class AppState(QObject):
    sig_log = Signal(str)
    sig_attack = Signal(str, str)
    sig_block = Signal(str, str)        # dev_ip, domain
    devices_updated = Signal()

    def __init__(self):
        super().__init__()
        self.net = NetworkInfo()
        self.db = DeviceDB()
        self.firewall = Firewall()
        self.spoofer = Spoofer(self.net)
        self.protector = ArpProtector(self.net, on_attack=self._on_attack)
        self.throughput = Throughput()
        self.engine = Engine(self.firewall)
        self.engine.on_block = lambda ip, d: self.sig_block.emit(ip, d)
        self.scheduler = Scheduler(on_apply=self._sched_apply,
                                   on_clear=self._sched_clear)
        self.devices = {}        # mac -> device dict
        add_listener(lambda line: self.sig_log.emit(line))

    # ---- network --------------------------------------------------------
    def refresh_network(self):
        ok = self.net.refresh()
        return ok

    def is_protected(self, dev):
        return dev["ip"] in (self.net.local_ip, self.net.gateway_ip)

    # ---- actions --------------------------------------------------------
    def cut(self, dev):
        if self.is_protected(dev):
            return
        self.spoofer.add(dev["ip"], dev["mac"], mode="cut")

    def restore(self, dev):
        self.spoofer.remove(dev["ip"])
        self.engine.unmanage(dev["ip"])

    def manage(self, dev):
        if self.is_protected(dev):
            return
        self.spoofer.add(dev["ip"], dev["mac"], mode="mitm")
        self.engine.manage(dev["ip"], dev["mac"])

    def set_throttle(self, dev, kbps):
        if kbps and kbps > 0:
            self.manage(dev)
            self.engine.set_limit(dev["ip"], kbps)
        else:
            self.engine.set_limit(dev["ip"], 0)

    def is_managed(self, dev):
        return self.engine.is_managed(dev["ip"])

    def is_cut(self, dev):
        t = self.spoofer.targets().get(dev["ip"])
        return bool(t and t.get("mode") == "cut")

    def status_of(self, dev):
        """Return (label, color) for a device's current control state."""
        ip = dev["ip"]
        if self.is_protected(dev):
            return ("\U0001F512 Aman", MUTED)
        if self.is_cut(dev):
            return ("✂ Diputus", DANGER)
        if self.engine.is_managed(ip):
            if ip in self.engine.limited_ips():
                return ("\U0001F422 Dibatasi", WARN)
            return ("\U0001F441 Dikelola", ACCENT2)
        return ("● Online", ACCENT)

    # ---- scheduler callbacks -------------------------------------------
    def _sched_apply(self, rule):
        dev = {"ip": rule["ip"], "mac": rule["mac"]}
        if self.is_protected(dev):
            return
        if rule["action"] == "cut":
            self.spoofer.add(rule["ip"], rule["mac"], mode="cut")
        else:  # block sites -> manage so firewall applies
            self.spoofer.add(rule["ip"], rule["mac"], mode="mitm")
            self.engine.manage(rule["ip"], rule["mac"])

    def _sched_clear(self, rule):
        self.spoofer.remove(rule["ip"])
        self.engine.unmanage(rule["ip"])

    def _on_attack(self, mac, ip):
        self.sig_attack.emit(mac, ip)

    # ---- cleanup --------------------------------------------------------
    def shutdown(self):
        try:
            self.spoofer.clear()
            self.protector.stop()
            self.engine.stop()
            self.scheduler.stop()
        except Exception:
            pass
