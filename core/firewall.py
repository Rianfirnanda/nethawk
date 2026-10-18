"""Site/domain blocklist: global rules, per-device rules, and category presets.
Matching is suffix-based so "youtube.com" also blocks "m.youtube.com".
Persisted to firewall.json. Enforced by the WinDivert engine (DNS/SNI/Host).
"""
import json
import threading

from . import config
from .logutil import log

# Curated category presets (domains). Kept small & high-signal.
CATEGORIES = {
    "Media Sosial": ["facebook.com", "fbcdn.net", "instagram.com", "twitter.com",
                     "x.com", "tiktok.com", "snapchat.com", "threads.net"],
    "Video / Streaming": ["youtube.com", "youtu.be", "googlevideo.com",
                          "netflix.com", "twitch.tv", "primevideo.com", "disney"],
    "Game": ["roblox.com", "epicgames.com", "steampowered.com", "riotgames.com",
             "supercell.com", "garena.com", "mobilelegends.com", "pubgmobile.com"],
    "Dewasa": ["pornhub.com", "xvideos.com", "xnxx.com", "xhamster.com",
               "redtube.com", "onlyfans.com"],
    "Iklan & Tracker": ["doubleclick.net", "googlesyndication.com",
                        "google-analytics.com", "googleadservices.com",
                        "adservice.google.com", "ads.yahoo.com", "adnxs.com",
                        "scorecardresearch.com", "taboola.com", "outbrain.com",
                        "criteo.com", "pubmatic.com", "rubiconproject.com",
                        "moatads.com", "amazon-adsystem.com"],
}


class Firewall:
    def __init__(self):
        self._path = config.firewall_db_path()
        self._lock = threading.Lock()
        self.global_block = set()        # domains blocked for everyone (managed)
        self.device_block = {}           # mac(lower) -> set(domains)
        self.enabled_categories = set()  # category names applied globally
        self._load()

    # ---- persistence ----------------------------------------------------
    def _load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.global_block = set(d.get("global", []))
            self.device_block = {k: set(v) for k, v in d.get("devices", {}).items()}
            self.enabled_categories = set(d.get("categories", []))
        except Exception:
            pass

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump({
                    "global": sorted(self.global_block),
                    "devices": {k: sorted(v) for k, v in self.device_block.items()},
                    "categories": sorted(self.enabled_categories),
                }, f, indent=2)
        except Exception as e:
            log("Gagal simpan firewall.json: %s" % e, "WARN")

    # ---- edits ----------------------------------------------------------
    def add_global(self, domain):
        domain = _norm(domain)
        if domain:
            with self._lock:
                self.global_block.add(domain)
                self._save()
            log("Blokir global: %s" % domain)

    def remove_global(self, domain):
        with self._lock:
            self.global_block.discard(_norm(domain))
            self._save()

    def add_for_device(self, mac, domain):
        domain = _norm(domain)
        mac = (mac or "").lower()
        if domain and mac:
            with self._lock:
                self.device_block.setdefault(mac, set()).add(domain)
                self._save()
            log("Blokir %s untuk %s" % (domain, mac))

    def remove_for_device(self, mac, domain):
        mac = (mac or "").lower()
        with self._lock:
            if mac in self.device_block:
                self.device_block[mac].discard(_norm(domain))
                self._save()

    def toggle_category(self, name, on):
        with self._lock:
            if on:
                self.enabled_categories.add(name)
            else:
                self.enabled_categories.discard(name)
            self._save()
        log("Kategori %s: %s" % (name, "ON" if on else "OFF"))

    # ---- queries --------------------------------------------------------
    def _effective(self, mac=None):
        blocked = set(self.global_block)
        for cat in self.enabled_categories:
            blocked |= set(CATEGORIES.get(cat, []))
        if mac and mac.lower() in self.device_block:
            blocked |= self.device_block[mac.lower()]
        return blocked

    def is_blocked(self, domain, mac=None) -> bool:
        d = _norm(domain)
        if not d:
            return False
        with self._lock:
            blocked = self._effective(mac)
        return any(d == b or d.endswith("." + b) or b in d for b in blocked)

    def total_rules(self) -> int:
        with self._lock:
            n = len(self.global_block)
            n += sum(len(v) for v in self.device_block.values())
            n += sum(len(CATEGORIES.get(c, [])) for c in self.enabled_categories)
            return n

    def has_any(self) -> bool:
        with self._lock:
            return bool(self.global_block or self.enabled_categories
                        or any(self.device_block.values()))


def _norm(domain: str) -> str:
    if not domain:
        return ""
    d = domain.strip().lower()
    for pre in ("http://", "https://"):
        if d.startswith(pre):
            d = d[len(pre):]
    d = d.split("/")[0].strip(".")
    return d
