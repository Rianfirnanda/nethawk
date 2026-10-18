"""Unified MITM traffic engine (WinDivert, Windows). EXPERIMENTAL.

When a device is ARP-poisoned in 'mitm' mode its traffic transits this machine.
With Windows IP forwarding on, this engine processes every forwarded packet and:
  * blocks sites   -> inspect DNS query name / TLS SNI / HTTP Host; drop matches
  * throttles      -> per-device token bucket; drop packets over budget
  * monitors       -> per-device up/down bytes + top destination domains
Everything else is reinjected (forwarded), so the device keeps working.

Requires IP forwarding (enable_forwarding; may need a single reboot). If pydivert
/ WinDivert is unavailable or anything throws, the engine logs and no-ops.
"""
import subprocess
import threading
import time
from collections import defaultdict, Counter

from .logutil import log


# ---- lightweight L7 parsers --------------------------------------------
def _dns_qname(data: bytes):
    try:
        if len(data) < 13:
            return None
        i = 12
        labels = []
        while i < len(data):
            n = data[i]
            if n == 0:
                break
            i += 1
            labels.append(data[i:i + n].decode("ascii", "ignore"))
            i += n
        name = ".".join(labels).lower()
        return name or None
    except Exception:
        return None


def _tls_sni(data: bytes):
    try:
        if len(data) < 45 or data[0] != 0x16 or data[5] != 0x01:
            return None  # not a TLS handshake ClientHello
        idx = 5 + 4 + 2 + 32          # record + hs header + version + random
        sid = data[idx]; idx += 1 + sid
        cs = int.from_bytes(data[idx:idx + 2], "big"); idx += 2 + cs
        comp = data[idx]; idx += 1 + comp
        ext_total = int.from_bytes(data[idx:idx + 2], "big"); idx += 2
        end = min(idx + ext_total, len(data))
        while idx + 4 <= end:
            etype = int.from_bytes(data[idx:idx + 2], "big")
            elen = int.from_bytes(data[idx + 2:idx + 4], "big")
            idx += 4
            if etype == 0x0000:        # server_name
                ni = idx + 2 + 1       # list len + name type
                nlen = int.from_bytes(data[ni:ni + 2], "big"); ni += 2
                return data[ni:ni + nlen].decode("ascii", "ignore").lower() or None
            idx += elen
        return None
    except Exception:
        return None


def _http_host(data: bytes):
    try:
        text = bytes(data[:1024]).decode("latin1", "ignore")
        for line in text.split("\r\n"):
            if line.lower().startswith("host:"):
                return line.split(":", 1)[1].strip().lower() or None
        return None
    except Exception:
        return None


class Engine:
    def __init__(self, firewall=None):
        self.firewall = firewall
        self._managed = {}           # ip -> mac
        self._limits = {}            # ip -> bytes/sec
        self._tokens = {}
        self._last = {}
        self._up = defaultdict(int)
        self._down = defaultdict(int)
        self._snap = {}
        self._flows = defaultdict(Counter)   # ip -> Counter(domain -> bytes)
        self._blocked_hits = defaultdict(int)
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._fwd_on = False
        self.on_block = None         # callback(dev_ip, domain)

    # ---- management -----------------------------------------------------
    def manage(self, ip, mac):
        with self._lock:
            self._managed[ip] = (mac or "").lower()
        self.start()

    def unmanage(self, ip):
        with self._lock:
            self._managed.pop(ip, None)
            self._limits.pop(ip, None)
            empty = not self._managed
        if empty:
            self.stop()

    def is_managed(self, ip):
        return ip in self._managed

    def managed_ips(self):
        with self._lock:
            return dict(self._managed)

    def set_limit(self, ip, kbps):
        bps = max(0.0, float(kbps)) * 1000 / 8.0
        with self._lock:
            if bps <= 0:
                self._limits.pop(ip, None)
            else:
                self._limits[ip] = bps
                self._tokens.setdefault(ip, bps)
                self._last.setdefault(ip, time.time())

    def limited_ips(self):
        with self._lock:
            return dict(self._limits)

    # ---- telemetry ------------------------------------------------------
    def rates(self):
        """Return {ip: (up_Bps, down_Bps)} since the previous call."""
        now = time.time()
        out = {}
        with self._lock:
            ips = set(self._up) | set(self._down) | set(self._managed)
            for ip in ips:
                up, down = self._up[ip], self._down[ip]
                pu, pd, pt = self._snap.get(ip, (up, down, now))
                dt = max(now - pt, 1e-3)
                out[ip] = ((up - pu) / dt, (down - pd) / dt)
                self._snap[ip] = (up, down, now)
        return out

    def totals(self):
        with self._lock:
            return {ip: (self._up[ip], self._down[ip]) for ip in
                    (set(self._up) | set(self._down))}

    def flows(self, ip, top=6):
        with self._lock:
            return self._flows.get(ip, Counter()).most_common(top)

    def blocked_hits(self, ip=None):
        with self._lock:
            if ip is None:
                return sum(self._blocked_hits.values())
            return self._blocked_hits.get(ip, 0)

    # ---- lifecycle ------------------------------------------------------
    @property
    def active(self):
        return self._running

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
        if self._fwd_on:
            return
        try:
            subprocess.run([
                "reg", "add",
                r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                "/v", "IPEnableRouter", "/t", "REG_DWORD", "/d", "1", "/f",
            ], capture_output=True, shell=False)
            subprocess.run(["sc", "config", "RemoteAccess", "start=", "auto"],
                           capture_output=True, shell=False)
            subprocess.run(["net", "start", "RemoteAccess"],
                           capture_output=True, shell=False)
            self._fwd_on = True
            log("IP forwarding diaktifkan (bila fitur belum bekerja, reboot 1x).")
        except Exception as e:
            log("Gagal aktifkan IP forwarding: %s" % e, "WARN")

    def _run(self):
        try:
            import pydivert
        except Exception as e:
            log("Engine nonaktif (pydivert/WinDivert tak tersedia): %s" % e, "WARN")
            self._running = False
            return
        try:
            with pydivert.WinDivert(
                    "ip", layer=pydivert.Layer.NETWORK_FORWARD) as w:
                log("Engine MITM: AKTIF")
                for packet in w:
                    if not self._running:
                        try:
                            w.send(packet)
                        except Exception:
                            pass
                        break
                    try:
                        self._handle(packet, w)
                    except Exception:
                        try:
                            w.send(packet)
                        except Exception:
                            pass
        except Exception as e:
            log("Engine berhenti: %s" % e, "WARN")
        finally:
            self._running = False
            log("Engine MITM: nonaktif")

    def _handle(self, packet, w):
        src = packet.src_addr
        dst = packet.dst_addr
        managed = self._managed
        if src in managed:
            dev_ip, dev_mac, outbound = src, managed[src], True
        elif dst in managed:
            dev_ip, dev_mac, outbound = dst, managed[dst], False
        else:
            w.send(packet)
            return

        size = len(packet.raw)
        if outbound:
            self._up[dev_ip] += size
        else:
            self._down[dev_ip] += size

        # --- deep visibility (always) + optional blocking ---
        # Parse the domain for every outbound device->internet request so the
        # Activity view shows what each device is opening, regardless of whether
        # any block rule is set. Blocking is applied only if the firewall matches.
        if outbound:
            domain = None
            try:
                if packet.udp is not None and packet.dst_port == 53:
                    domain = _dns_qname(bytes(packet.payload or b""))
                elif packet.tcp is not None and packet.dst_port == 443:
                    domain = _tls_sni(bytes(packet.payload or b""))
                elif packet.tcp is not None and packet.dst_port == 80:
                    domain = _http_host(bytes(packet.payload or b""))
            except Exception:
                domain = None
            if domain:
                self._flows[dev_ip][domain] += size
                if self.firewall is not None and self.firewall.is_blocked(domain, dev_mac):
                    self._blocked_hits[dev_ip] += 1
                    if self.on_block:
                        try:
                            self.on_block(dev_ip, domain)
                        except Exception:
                            pass
                    return  # DROP -> site blocked

        # --- throttle ---
        if not self._allow(dev_ip, size):
            return  # DROP -> over budget

        w.send(packet)

    def _allow(self, ip, size):
        now = time.time()
        with self._lock:
            rate = self._limits.get(ip, 0)
            if rate <= 0:
                return True
            tokens = min(rate, self._tokens.get(ip, rate)
                         + (now - self._last.get(ip, now)) * rate)
            self._last[ip] = now
            if tokens >= size:
                self._tokens[ip] = tokens - size
                return True
            self._tokens[ip] = tokens
            return False
