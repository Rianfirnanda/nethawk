"""Discover the active network: default interface, local IP/MAC, gateway and the
subnet CIDR to scan. Works on Windows (Npcap) and other platforms.

All heavy scapy imports are done lazily so the GUI can show a friendly message
if Npcap / scapy is missing instead of crashing on import.
"""
import ipaddress
import os
import re
import socket
import subprocess

from .logutil import log

NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def mac_from_cache(ip: str):
    """Resolve a MAC via the OS: ping to populate the ARP cache, then read it.
    Reliable on Wi-Fi where scapy's raw getmacbyip fails."""
    try:
        subprocess.run(["ping", "-n", "1", "-w", "400", ip],
                       capture_output=True, creationflags=NO_WINDOW)
        out = subprocess.run(["arp", "-a", ip], capture_output=True, text=True,
                             creationflags=NO_WINDOW).stdout or ""
        m = re.search(r"([0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})", out)
        if m:
            return m.group(1).lower().replace("-", ":")
    except Exception:
        pass
    return None


def _scapy():
    # Imported lazily; raises a clear error if Npcap/scapy is unavailable.
    from scapy.all import (conf, get_if_addr, get_if_hwaddr, getmacbyip)  # noqa
    return conf, get_if_addr, get_if_hwaddr, getmacbyip


def _iface_name(iface) -> str:
    """scapy may hand us a NetworkInterface object or a plain string."""
    for attr in ("name", "description"):
        val = getattr(iface, attr, None)
        if val:
            return str(val)
    return str(iface)


def _netmask_for(ip: str):
    """Find the IPv4 netmask of the NIC that owns `ip` using psutil."""
    try:
        import psutil
        from socket import AF_INET
        for addrs in psutil.net_if_addrs().values():
            for a in addrs:
                if a.family == AF_INET and a.address == ip and a.netmask:
                    return a.netmask
    except Exception:
        pass
    return "255.255.255.0"  # sane /24 fallback


class NetworkInfo:
    """Snapshot of the current network, refreshable."""

    def __init__(self):
        self.iface = None            # scapy iface (object or name) used for sending
        self.iface_name = "?"        # human readable
        self.local_ip = None
        self.local_mac = None
        self.gateway_ip = None
        self.gateway_mac = None
        self.netmask = None
        self.cidr = None             # e.g. "192.168.1.0/24"
        self.ok = False
        self.error = None

    def refresh(self):
        """Populate all fields. Returns True on success."""
        self.ok = False
        self.error = None
        try:
            conf, get_if_addr, get_if_hwaddr, getmacbyip = _scapy()
        except Exception as e:  # scapy / Npcap missing
            self.error = (
                "Scapy/Npcap belum siap. Pastikan Npcap terpasang dan "
                "aplikasi dijalankan sebagai Administrator.\n\nDetail: %s" % e
            )
            log(self.error, "ERROR")
            return False

        try:
            # Default route -> (interface, outgoing_ip, gateway_ip)
            iface, local_ip, gateway_ip = conf.route.route("0.0.0.0")
            self.iface = iface
            self.iface_name = _iface_name(iface)
            self.local_ip = local_ip
            self.gateway_ip = gateway_ip if gateway_ip not in (None, "0.0.0.0") else None

            try:
                self.local_mac = get_if_hwaddr(iface)
            except Exception:
                self.local_mac = None

            self.netmask = _netmask_for(local_ip)
            self.cidr = self._compute_cidr(local_ip, self.netmask)

            if self.gateway_ip:
                try:
                    self.gateway_mac = getmacbyip(self.gateway_ip)
                except Exception:
                    self.gateway_mac = None
                # Wi-Fi: raw ARP often fails -> fall back to the OS ARP cache.
                if not self.gateway_mac:
                    self.gateway_mac = mac_from_cache(self.gateway_ip)

            if not self.gateway_ip:
                self.error = "Gateway tidak terdeteksi (kamu online lewat Wi-Fi/LAN?)."
                log(self.error, "WARN")
            self.ok = self.local_ip is not None and self.cidr is not None
            log("Interface=%s IP=%s GW=%s (%s) CIDR=%s" % (
                self.iface_name, self.local_ip, self.gateway_ip,
                self.gateway_mac, self.cidr))
            return self.ok
        except Exception as e:
            self.error = "Gagal membaca info jaringan: %s" % e
            log(self.error, "ERROR")
            return False

    @staticmethod
    def _compute_cidr(ip: str, netmask: str):
        try:
            net = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
            # Guard against scanning a huge range by accident.
            if net.num_addresses > 4096:
                net = ipaddress.IPv4Network(f"{ip}/24", strict=False)
            return str(net)
        except Exception:
            return None

    @property
    def my_hostname(self) -> str:
        try:
            return socket.gethostname()
        except Exception:
            return "this-pc"

    def summary(self) -> str:
        return (f"{self.iface_name}  |  IP {self.local_ip}  |  "
                f"GW {self.gateway_ip}  |  {self.cidr}")
