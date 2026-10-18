"""NetHawk web server.

aiohttp backend that reuses the proven core engines and serves a futuristic
single-page web UI. Realtime data (throughput, per-device rates, stats, events)
is pushed over a WebSocket; actions go through a small REST API.
"""
import asyncio
import json
import os
import sys
import threading
import time
import webbrowser
from collections import deque, Counter

from aiohttp import web, WSMsgType

from core.policy import decide

from core import config, scanner, vendor, devicetype, flows
from core.network import NetworkInfo
from core.devices_db import DeviceDB
from core.firewall import Firewall, CATEGORIES
from core.spoofer import Spoofer
from core.protection import ArpProtector
from core.monitor import Throughput
from core.engine import Engine
from core.scheduler import Scheduler
from core.logutil import add_listener, log

PORT = int(os.environ.get("NETHAWK_PORT", "8787"))
HOST = "127.0.0.1"


def resource(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


WEB_DIR = resource("web")


# =====================================================================
# Hub: owns all core engines + shared state
# =====================================================================
class Hub:
    def __init__(self):
        self.net = NetworkInfo()
        self.db = DeviceDB()
        self.firewall = Firewall()
        self.spoofer = Spoofer(self.net)
        self.protector = ArpProtector(self.net, on_attack=self._on_attack)
        self.throughput = Throughput()
        self.engine = Engine(self.firewall)
        self.engine.on_block = self._on_block
        self.scheduler = Scheduler(on_apply=self._sched_apply,
                                   on_clear=self._sched_clear)
        self.devices = {}
        self._scanned = False
        self._session_start = {}
        self.settings = self._load_settings()
        self.events = deque(maxlen=300)
        add_listener(self._on_log)
        self.net.refresh()
        self.scheduler.start()
        self._enf_running = True
        threading.Thread(target=self._enforce, daemon=True).start()

    # ---- settings + hotspot policy enforcement -------------------------
    def _load_settings(self):
        s = {}
        try:
            with open(config.settings_path(), "r", encoding="utf-8") as f:
                s = json.load(f)
        except Exception:
            pass
        for k, v in {"auto_block_new": False, "guest_kbps": 0,
                     "quota_mb": 0, "quota_minutes": 0}.items():
            s.setdefault(k, v)
        return s

    def _save_settings(self):
        try:
            with open(config.settings_path(), "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            log("Gagal simpan settings: %s" % e, "WARN")

    def _enforce(self):
        while self._enf_running:
            try:
                totals = self.engine.totals()
                now = time.time()
                for mac, dev in list(self.devices.items()):
                    if self.is_protected(dev):
                        continue
                    role = self.db.role_of(mac)
                    tot = sum(totals.get(dev["ip"], (0, 0)))
                    sess = now - self._session_start.get(mac, now)
                    act, kbps = decide(role, tot, sess, self.settings)
                    self._apply_policy(dev, act, kbps)
            except Exception as e:
                log("Enforcer error: %s" % e, "WARN")
            time.sleep(8)

    def _apply_policy(self, dev, act, kbps):
        ip, mac = dev["ip"], dev["mac"]
        cur = self.spoofer.targets().get(ip, {}).get("mode")
        if act == "cut":
            if cur != "cut":
                self.spoofer.add(ip, mac, mode="cut")
        elif act == "limit":
            self.spoofer.add(ip, mac, mode="mitm")
            self.engine.manage(ip, mac)
            self.engine.set_limit(ip, kbps)
        elif act == "monitor":
            self.spoofer.add(ip, mac, mode="mitm")
            self.engine.manage(ip, mac)
        # "allow": leave the device untouched (don't override manual control)

    # ---- event hooks (from worker threads) -----------------------------
    def _on_log(self, line):
        self.events.append({"type": "log", "line": line})

    def _on_attack(self, mac, ip):
        self.events.append({"type": "attack", "mac": mac, "ip": ip})

    def _on_block(self, ip, domain):
        self.events.append({"type": "block", "ip": ip, "domain": domain})

    def _sched_apply(self, rule):
        if rule["action"] == "cut":
            self.spoofer.add(rule["ip"], rule["mac"], mode="cut")
        else:
            self.spoofer.add(rule["ip"], rule["mac"], mode="mitm")
            self.engine.manage(rule["ip"], rule["mac"])

    def _sched_clear(self, rule):
        self.spoofer.remove(rule["ip"])
        self.engine.unmanage(rule["ip"])

    # ---- helpers --------------------------------------------------------
    def is_protected(self, dev):
        return dev["ip"] in (self.net.local_ip, self.net.gateway_ip)

    def status_of(self, dev):
        ip = dev["ip"]
        if self.is_protected(dev):
            return "safe"
        t = self.spoofer.targets().get(ip)
        if t and t.get("mode") == "cut":
            return "cut"
        if self.engine.is_managed(ip):
            return "throttled" if ip in self.engine.limited_ips() else "managed"
        return "online"

    def scan(self):
        found = scanner.arp_scan(self.net.cidr, self.net.iface,
                                 local_ip=self.net.local_ip,
                                 local_mac=self.net.local_mac)
        for dev in found:
            is_new = dev["mac"] not in self.devices
            scanner.enrich(dev, self.net.iface)
            typ, emoji = devicetype.guess(dev.get("vendor", ""),
                                          dev.get("hostname", ""))
            dev["type"] = typ
            dev["emoji"] = emoji
            dev["name"] = self.db.name_of(dev["mac"])
            self.db.seen(dev["mac"])
            self._session_start.setdefault(dev["mac"], time.time())
            if is_new and self._scanned:
                self.events.append({"type": "newdevice", "ip": dev["ip"],
                                    "name": dev.get("name") or dev["ip"],
                                    "emoji": emoji})
                if (self.settings.get("auto_block_new")
                        and self.db.role_of(dev["mac"]) != "staff"
                        and not self.is_protected(dev)):
                    self.spoofer.add(dev["ip"], dev["mac"], mode="cut")
            self.devices[dev["mac"]] = dev
        self._scanned = True
        return len(found)

    def device_list(self, rates):
        totals = self.engine.totals()
        out = []
        for mac, dev in self.devices.items():
            ip = dev["ip"]
            up, down = rates.get(ip, (None, None))
            managed = self.engine.is_managed(ip)
            tot = totals.get(ip, (0, 0))
            out.append({
                "ip": ip, "mac": mac,
                "vendor": dev.get("vendor", ""),
                "type": dev.get("type", ""),
                "emoji": dev.get("emoji", ""),
                "name": dev.get("name", "") or "",
                "hostname": dev.get("hostname", ""),
                "status": self.status_of(dev),
                "up": up, "down": down,
                "total": tot[0] + tot[1],
                "activity": [d for d, _ in self.engine.flows(ip, 3)] if managed else [],
                "sites": [{"d": d, "b": b} for d, b in self.engine.flows(ip, 10)] if managed else [],
                "blocked": self.engine.blocked_hits(ip),
                "role": self.db.role_of(mac),
                "you": ip == self.net.local_ip,
                "gateway": ip == self.net.gateway_ip,
            })
        out.sort(key=lambda d: tuple(int(p) for p in d["ip"].split(".")))
        return out

    def insight(self, rates):
        best, best_rate = None, 0
        for dev in self.devices.values():
            ip = dev["ip"]
            if not self.engine.is_managed(ip):
                continue
            up, down = rates.get(ip, (0, 0))
            r = (up or 0) + (down or 0)
            if r >= best_rate:
                best_rate, best = r, dev
        if not best:
            return {"hint": "Aktifkan “Awasi Semua” di tab Perangkat untuk "
                            "melihat siapa pemakai bandwidth terbanyak — dan "
                            "sedang membuka situs apa."}
        ip = best["ip"]
        return {
            "name": best.get("name") or ip, "emoji": best.get("emoji", ""),
            "ip": ip, "rate": best_rate,
            "activity": [d for d, _ in self.engine.flows(ip, 4)],
            "blocked": self.engine.blocked_hits(ip),
        }

    def stats(self):
        total = len(self.devices)
        cut = sum(1 for d in self.devices.values()
                  if self.status_of(d) == "cut")
        managed = len(self.engine.managed_ips())
        return {"total": total, "online": max(0, total - cut), "cut": cut,
                "managed": managed, "blocked": self.engine.blocked_hits()}

    def net_info(self):
        n = self.net
        return {"ok": bool(n.ok), "iface": n.iface_name, "ip": n.local_ip,
                "gateway": n.gateway_ip, "gateway_mac": n.gateway_mac,
                "cidr": n.cidr, "error": n.error}

    def firewall_info(self):
        return {
            "categories": [{"name": name, "count": len(doms),
                            "on": name in self.firewall.enabled_categories}
                           for name, doms in CATEGORIES.items()],
            "global": sorted(self.firewall.global_block),
        }

    def schedules(self):
        days = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
        return [{"id": r["id"], "name": r["name"], "action": r["action"],
                 "start": r["start"], "end": r["end"],
                 "days": [days[d] for d in r["days"]]}
                for r in self.scheduler.all_rules()]

    def tick(self):
        up, down = self.throughput.sample()
        rates = self.engine.rates()
        evs = list(self.events)
        self.events.clear()
        return {
            "type": "tick", "up": up, "down": down,
            "stats": self.stats(),
            "devices": self.device_list(rates),
            "net": self.net_info(),
            "protection": self.protector.active,
            "engine": self.engine.active,
            "insight": self.insight(rates),
            "observed": flows.observe(),
            "apps": self._apps(),
            "events": evs,
        }

    def _apps(self):
        c = Counter()
        for dev in self.devices.values():
            for d, b in self.engine.flows(dev["ip"], 30):
                c[d] += b
        return [{"name": k, "bytes": v} for k, v in c.most_common(8)]

    def full(self):
        snap = self.tick()
        snap["firewall"] = self.firewall_info()
        snap["schedules"] = self.schedules()
        snap["settings"] = dict(self.settings)
        return snap

    def _dev(self, mac):
        return self.devices.get((mac or "").lower())

    # ---- action dispatch ------------------------------------------------
    def action(self, data):
        a = data.get("action")
        mac = (data.get("mac") or "").lower()
        dev = self._dev(mac)
        if a == "cut" and dev:
            self.spoofer.add(dev["ip"], dev["mac"], mode="cut")
        elif a == "restore" and dev:
            self.spoofer.remove(dev["ip"]); self.engine.unmanage(dev["ip"])
        elif a == "manage" and dev:
            if not self.is_protected(dev):
                self.spoofer.add(dev["ip"], dev["mac"], mode="mitm")
                self.engine.manage(dev["ip"], dev["mac"])
        elif a == "throttle" and dev:
            kbps = int(data.get("kbps", 0))
            if kbps > 0 and not self.is_protected(dev):
                self.spoofer.add(dev["ip"], dev["mac"], mode="mitm")
                self.engine.manage(dev["ip"], dev["mac"])
                self.engine.set_limit(dev["ip"], kbps)
            else:
                self.engine.set_limit(dev["ip"], 0)
        elif a == "rename" and dev:
            self.db.set_name(dev["mac"], data.get("name", ""))
            dev["name"] = data.get("name", "")
        elif a == "block_device" and dev:
            self.firewall.add_for_device(dev["mac"], data.get("domain", ""))
            if not self.is_protected(dev):
                self.spoofer.add(dev["ip"], dev["mac"], mode="mitm")
                self.engine.manage(dev["ip"], dev["mac"])
        elif a == "cutall":
            for d in self.devices.values():
                if not self.is_protected(d):
                    self.spoofer.add(d["ip"], d["mac"], mode="cut")
        elif a == "restoreall":
            self.spoofer.clear()
            for ip in list(self.engine.managed_ips()):
                self.engine.unmanage(ip)
        elif a == "monitor_all":
            for d in self.devices.values():
                if self.is_protected(d):
                    continue
                t = self.spoofer.targets().get(d["ip"])
                if t and t.get("mode") == "cut":
                    continue
                self.spoofer.add(d["ip"], d["mac"], mode="mitm")
                self.engine.manage(d["ip"], d["mac"])
        elif a == "unmonitor_all":
            for ip in list(self.engine.managed_ips()):
                self.spoofer.remove(ip)
                self.engine.unmanage(ip)
        elif a == "block_global":
            self.firewall.add_global(data.get("domain", ""))
        elif a == "unblock_global":
            self.firewall.remove_global(data.get("domain", ""))
        elif a == "category":
            self.firewall.toggle_category(data.get("name", ""),
                                          bool(data.get("on")))
        elif a == "protect":
            if data.get("on"):
                self.protector.start()
            else:
                self.protector.stop()
        elif a == "forwarding":
            self.engine.enable_forwarding()
        elif a == "schedule_add" and dev:
            self.scheduler.add_rule(dev["mac"], dev["ip"],
                                    dev.get("name") or dev["ip"],
                                    data.get("sched_action", "cut"),
                                    data.get("days", []),
                                    data.get("start", "21:00"),
                                    data.get("end", "06:00"))
        elif a == "schedule_del":
            self.scheduler.remove_rule(int(data.get("id")))
        elif a == "set_role" and dev:
            role = data.get("role", "guest")
            self.db.set_role(mac, role)
            if role == "staff":   # staff never restricted
                self.spoofer.remove(dev["ip"])
                self.engine.unmanage(dev["ip"])
        elif a == "approve" and dev:
            self.db.set_role(mac, "guest")
            self.spoofer.remove(dev["ip"])
        elif a == "settings":
            self.settings.update(data.get("settings", {}))
            self._save_settings()
        elif a == "quit":
            self.shutdown()
            threading.Timer(0.8, lambda: os._exit(0)).start()
        return {"ok": True}

    def shutdown(self):
        try:
            self.spoofer.clear(); self.protector.stop()
            self.engine.stop(); self.scheduler.stop()
        except Exception:
            pass


# =====================================================================
# HTTP / WS handlers
# =====================================================================
HUB = None


async def index(request):
    return web.FileResponse(os.path.join(WEB_DIR, "index.html"))


async def api_snapshot(request):
    return web.json_response(HUB.full())


async def api_scan(request):
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, HUB.scan)
    except Exception as e:
        log("Scan gagal: %s" % e, "ERROR")
        return web.json_response({"ok": False, "error": str(e)}, status=500)
    return web.json_response(HUB.full())


async def api_action(request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    try:
        res = HUB.action(data)
    except Exception as e:
        log("Action gagal: %s" % e, "WARN")
        return web.json_response({"ok": False, "error": str(e)}, status=500)
    return web.json_response(res)


async def api_report(request):
    totals = HUB.engine.totals()
    now = time.time()
    rows = ["nama,ip,mac,vendor,tipe,role,data_MB,durasi_menit,situs_teratas"]
    for mac, dev in HUB.devices.items():
        tot = sum(totals.get(dev["ip"], (0, 0)))
        sess = (now - HUB._session_start.get(mac, now)) / 60
        doms = " ".join(d for d, _ in HUB.engine.flows(dev["ip"], 5))
        name = (dev.get("name") or "").replace(",", " ")
        ven = (dev.get("vendor", "") or "").replace(",", " ")
        rows.append("%s,%s,%s,%s,%s,%s,%.1f,%.0f,%s" % (
            name, dev["ip"], mac, ven, dev.get("type", ""),
            HUB.db.role_of(mac), tot / 1048576, sess, doms))
    return web.Response(
        text="\n".join(rows), content_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=nethawk-report.csv"})


async def ws_handler(request):
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    request.app["ws"].add(ws)
    try:
        await ws.send_json(HUB.full())
        async for msg in ws:
            if msg.type == WSMsgType.ERROR:
                break
    finally:
        request.app["ws"].discard(ws)
    return ws


async def push_loop(app):
    try:
        while True:
            await asyncio.sleep(1.0)
            if not app["ws"]:
                HUB.throughput.sample()  # keep counters moving
                continue
            snap = HUB.tick()
            dead = []
            for ws in list(app["ws"]):
                try:
                    await ws.send_json(snap)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                app["ws"].discard(ws)
    except asyncio.CancelledError:
        pass


async def on_startup(app):
    app["push"] = asyncio.create_task(push_loop(app))
    url = "http://%s:%d" % (HOST, PORT)

    def _open():
        try:
            webbrowser.open(url)
        except Exception:
            try:
                os.startfile(url)
            except Exception:
                pass
    if not os.environ.get("NETHAWK_NO_OPEN"):
        asyncio.get_event_loop().call_later(0.8, _open)
    log("NetHawk server aktif di %s" % url)


async def on_cleanup(app):
    task = app.get("push")
    if task:
        task.cancel()
    if HUB:
        HUB.shutdown()


def build_app():
    app = web.Application()
    app["ws"] = set()
    app.add_routes([
        web.get("/", index),
        web.get("/ws", ws_handler),
        web.get("/api/snapshot", api_snapshot),
        web.post("/api/scan", api_scan),
        web.post("/api/action", api_action),
        web.get("/api/report.csv", api_report),
        web.static("/static", WEB_DIR),
    ])
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


def run():
    global HUB
    HUB = Hub()
    threading.Thread(target=vendor.ensure_db, daemon=True).start()
    web.run_app(build_app(), host=HOST, port=PORT, print=None)


if __name__ == "__main__":
    run()
