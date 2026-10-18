"""ARP protection (anti-NetCut).

Sniffs ARP replies on the LAN. If someone claims the GATEWAY IP belongs to a MAC
that isn't the real gateway MAC, that's an ARP spoofing attack aimed (at least)
at the subnet -- we raise an alert and can re-assert a static ARP entry for the
gateway so our own machine keeps working.
"""
import subprocess
import threading

from .logutil import log


class ArpProtector:
    def __init__(self, netinfo, on_attack=None):
        self.net = netinfo
        self.on_attack = on_attack      # callable(attacker_mac, claimed_ip)
        self._thread = None
        self._running = False
        self._alerted = set()

    def start(self):
        if self._running:
            return
        if not (self.net.gateway_ip and self.net.gateway_mac):
            log("Proteksi ARP butuh info gateway yang lengkap.", "WARN")
            return
        self._running = True
        self._thread = threading.Thread(target=self._sniff, daemon=True)
        self._thread.start()
        log("Mode proteksi ARP: AKTIF (memantau gateway %s)" % self.net.gateway_ip)

    def stop(self):
        self._running = False
        log("Mode proteksi ARP: nonaktif")

    @property
    def active(self) -> bool:
        return self._running

    def _sniff(self):
        try:
            from scapy.all import sniff, ARP
        except Exception as e:
            log("Proteksi ARP gagal start: %s" % e, "ERROR")
            self._running = False
            return

        def handle(pkt):
            if not self._running:
                return True  # stop sniffing
            if not pkt.haslayer(ARP):
                return
            arp = pkt[ARP]
            if arp.op == 2 and arp.psrc == self.net.gateway_ip:
                claimed = (arp.hwsrc or "").lower()
                real = (self.net.gateway_mac or "").lower()
                if claimed and real and claimed != real:
                    self._handle_attack(claimed)

        kwargs = dict(filter="arp", prn=handle, store=0,
                      stop_filter=lambda p: not self._running)
        if self.net.iface is not None:
            kwargs["iface"] = self.net.iface
        try:
            sniff(**kwargs)
        except Exception as e:
            log("Proteksi ARP berhenti: %s" % e, "WARN")
            self._running = False

    def _handle_attack(self, attacker_mac: str):
        if attacker_mac not in self._alerted:
            self._alerted.add(attacker_mac)
            log("SERANGAN ARP terdeteksi! Penyerang MAC=%s meniru gateway %s"
                % (attacker_mac, self.net.gateway_ip), "ALERT")
            if self.on_attack:
                try:
                    self.on_attack(attacker_mac, self.net.gateway_ip)
                except Exception:
                    pass
        self._defend()

    def _defend(self):
        """Pin a static ARP entry for the gateway so WE stay connected."""
        try:
            subprocess.run(
                ["arp", "-s", self.net.gateway_ip,
                 self.net.gateway_mac.replace(":", "-")],
                capture_output=True, shell=False)
        except Exception:
            pass
