"""LAN scanner.

On Windows + Wi-Fi, raw ARP injection/capture via Npcap is unreliable (the
wireless driver drops injected L2 frames and won't surface other stations' ARP
replies). So the PRIMARY discovery method is OS-based and works on both Wi-Fi
and Ethernet:

  1. Fast parallel ICMP sweep over the subnet -> this forces Windows to ARP-
     resolve every reachable host (a host replies to ARP even if it drops ICMP),
     populating the system ARP cache.
  2. Read the system ARP cache (`arp -a`) and keep entries inside our subnet.

Enrichment (vendor / hostname / rough OS) is unchanged.
"""
import ipaddress
import os
import re
import socket
import subprocess
import time

from . import vendor
from .logutil import log

NO_WINDOW = 0x08000000 if os.name == "nt" else 0

_ARP_LINE = re.compile(
    r"\s*([0-9]{1,3}(?:\.[0-9]{1,3}){3})\s+([0-9a-fA-F]{2}(?:[-:][0-9a-fA-F]{2}){5})\s+(\w+)")
_IFACE_LINE = re.compile(r"Interface:\s+([0-9.]+)")


def _poke(ip: str):
    """Send a tiny UDP datagram so the OS ARP-resolves this on-link host.
    No subprocess, no listener needed -- ARP happens before the UDP is sent."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            s.sendto(b"\x00", (ip, 9))   # port 9 = discard
        finally:
            s.close()
    except Exception:
        pass


def _ping_sweep(cidr: str, wait: float = 1.3):
    """Populate the ARP cache fast: poke every host, then let replies land."""
    try:
        net = ipaddress.ip_network(cidr, strict=False)
    except Exception:
        return
    hosts = [str(h) for h in net.hosts()]
    if len(hosts) > 1024:          # safety cap for large subnets
        hosts = hosts[:1024]
    for ip in hosts:
        _poke(ip)
    time.sleep(wait)


def _os_neighbors(cidr: str, local_ip: str = None):
    try:
        net = ipaddress.ip_network(cidr, strict=False)
    except Exception:
        return []
    try:
        out = subprocess.run(["arp", "-a"], capture_output=True, text=True,
                             creationflags=NO_WINDOW).stdout or ""
    except Exception as e:
        log("Gagal baca ARP table: %s" % e, "WARN")
        return []
    devices = []
    cur_iface = None
    for line in out.splitlines():
        mi = _IFACE_LINE.search(line)
        if mi:
            cur_iface = mi.group(1)
            continue
        # When we know our own interface IP, only read that interface's block.
        if local_ip and cur_iface and cur_iface != local_ip:
            continue
        m = _ARP_LINE.match(line)
        if not m:
            continue
        ip = m.group(1)
        mac = m.group(2).lower().replace("-", ":")
        try:
            if ipaddress.ip_address(ip) not in net:
                continue
        except Exception:
            continue
        if (mac.startswith("ff:ff") or mac.startswith("01:00:5e")
                or mac.startswith("33:33") or mac == "00:00:00:00:00:00"):
            continue
        if ip.endswith(".255") or ip.endswith(".0"):
            continue
        devices.append({"ip": ip, "mac": mac})
    return devices


def arp_scan(cidr: str, iface=None, timeout: float = 2.5,
             local_ip: str = None, local_mac: str = None):
    """Discover devices on the subnet. Returns a list of {ip, mac}."""
    _ping_sweep(cidr)
    found = {}
    for d in _os_neighbors(cidr, local_ip):
        found[d["mac"]] = d
    # Always include this machine itself.
    if local_ip and local_mac:
        found.setdefault(local_mac.lower(),
                         {"ip": local_ip, "mac": local_mac.lower()})
    log("Scan %s -> %d perangkat" % (cidr, len(found)))
    return list(found.values())


def resolve_hostname(ip: str) -> str:
    try:
        socket.setdefaulttimeout(0.6)
        name = socket.gethostbyaddr(ip)[0]
        return name.split(".")[0]
    except Exception:
        return ""


def guess_os(ip: str, iface=None) -> str:
    """Rough OS guess from the ICMP echo TTL. Best effort, may be empty."""
    try:
        out = subprocess.run(["ping", "-n", "1", "-w", "500", ip],
                             capture_output=True, text=True,
                             creationflags=NO_WINDOW).stdout or ""
        m = re.search(r"TTL=(\d+)", out, re.IGNORECASE)
        if not m:
            return ""
        ttl = int(m.group(1))
        if ttl >= 250:
            return "Router/Net"
        if ttl >= 128:
            return "Windows"
        if ttl >= 64:
            return "Linux/Android/Apple"
        return ""
    except Exception:
        return ""


def enrich(device: dict, iface=None, do_os: bool = False) -> dict:
    """Fill vendor/hostname/os onto a {ip,mac} dict (mutates and returns it)."""
    device.setdefault("vendor", "")
    device.setdefault("hostname", "")
    device.setdefault("os", "")
    device["vendor"] = vendor.lookup(device["mac"])
    device["hostname"] = resolve_hostname(device["ip"])
    if do_os:
        device["os"] = guess_os(device["ip"], iface)
    return device
