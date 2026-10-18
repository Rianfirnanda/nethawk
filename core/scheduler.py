"""Scheduled rules (parental control): cut or block a device during a time
window on chosen weekdays. A background thread checks regularly and fires
on_apply / on_clear callbacks. Rules persist to schedule.json.
"""
import datetime
import json
import threading
import time

from . import config
from .logutil import log

DAYS = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]  # Monday = 0


class Scheduler:
    def __init__(self, on_apply=None, on_clear=None):
        self._path = config.schedule_db_path()
        self.rules = []          # list of rule dicts
        self._applied = set()    # rule ids currently applied
        self._lock = threading.Lock()
        self.on_apply = on_apply
        self.on_clear = on_clear
        self._running = False
        self._thread = None
        self._load()

    # ---- persistence ----------------------------------------------------
    def _load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self.rules = json.load(f)
        except Exception:
            self.rules = []

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self.rules, f, indent=2)
        except Exception as e:
            log("Gagal simpan schedule.json: %s" % e, "WARN")

    # ---- edits ----------------------------------------------------------
    def add_rule(self, mac, ip, name, action, days, start, end):
        with self._lock:
            new_id = (max((r["id"] for r in self.rules), default=0) + 1)
            self.rules.append({
                "id": new_id, "mac": (mac or "").lower(), "ip": ip,
                "name": name, "action": action,   # "cut" or "block"
                "days": list(days), "start": start, "end": end,
            })
            self._save()
        log("Jadwal ditambah: %s %s %s-%s" % (name, action, start, end))
        return new_id

    def remove_rule(self, rule_id):
        with self._lock:
            rule = next((r for r in self.rules if r["id"] == rule_id), None)
            self.rules = [r for r in self.rules if r["id"] != rule_id]
            self._save()
        if rule and rule_id in self._applied:
            self._applied.discard(rule_id)
            if self.on_clear:
                self.on_clear(rule)

    def all_rules(self):
        with self._lock:
            return list(self.rules)

    def active_ids(self):
        with self._lock:
            return set(self._applied)

    # ---- engine ---------------------------------------------------------
    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log("Scheduler: AKTIF")

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                self._tick()
            except Exception as e:
                log("Scheduler error: %s" % e, "WARN")
            time.sleep(20)

    def _tick(self):
        now = datetime.datetime.now()
        for rule in self.all_rules():
            inside = self._in_window(rule, now)
            applied = rule["id"] in self._applied
            if inside and not applied:
                self._applied.add(rule["id"])
                log("Jadwal AKTIF: %s (%s)" % (rule["name"], rule["action"]))
                if self.on_apply:
                    self.on_apply(rule)
            elif not inside and applied:
                self._applied.discard(rule["id"])
                log("Jadwal SELESAI: %s" % rule["name"])
                if self.on_clear:
                    self.on_clear(rule)

    @staticmethod
    def _in_window(rule, now):
        try:
            sh, sm = map(int, rule["start"].split(":"))
            eh, em = map(int, rule["end"].split(":"))
        except Exception:
            return False
        cur = now.hour * 60 + now.minute
        start = sh * 60 + sm
        end = eh * 60 + em
        wd = now.weekday()
        days = rule.get("days", [])
        if start <= end:
            return wd in days and start <= cur <= end
        # overnight window (e.g. 22:00 - 06:00)
        if cur >= start:
            return wd in days
        return ((wd - 1) % 7) in days
