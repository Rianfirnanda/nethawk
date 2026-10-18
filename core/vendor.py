"""MAC -> vendor name lookup (offline cache, updates once over the net).

Uses the `mac-vendor-lookup` package which caches the Wireshark OUI list on
disk. Everything is wrapped so a missing DB / no internet never crashes the app
-- it just returns "Unknown".
"""
import threading

from .logutil import log

_ml = None
_ready = False
_lock = threading.Lock()


def _get():
    global _ml, _ready
    with _lock:
        if _ml is None and not _ready:
            try:
                from mac_vendor_lookup import MacLookup
                _ml = MacLookup()
            except Exception as e:
                log("mac-vendor-lookup tidak tersedia: %s" % e, "WARN")
            _ready = True
    return _ml


def ensure_db(update_if_missing: bool = True):
    """Make sure the vendor DB exists. Safe to call in a background thread."""
    ml = _get()
    if not ml:
        return
    try:
        ml.lookup("00:00:00:00:00:00")  # cheap probe; raises if DB absent
    except Exception:
        if update_if_missing:
            try:
                log("Mengunduh database vendor (OUI) sekali saja...")
                ml.update_vendors()
                log("Database vendor siap.")
            except Exception as e:
                log("Gagal update DB vendor (offline?): %s" % e, "WARN")


def _is_locally_administered(mac: str) -> bool:
    """True if the MAC is randomized/locally-administered (privacy MAC on phones)."""
    try:
        first = int(mac.split(":")[0], 16)
        return bool(first & 0x02)
    except Exception:
        return False


def lookup(mac: str) -> str:
    ml = _get()
    if not mac:
        return "Unknown"
    if ml:
        try:
            name = ml.lookup(mac)
            if name:
                return name
        except Exception:
            pass
    # No vendor found: flag randomized MACs so the user understands why.
    if _is_locally_administered(mac):
        return "Private (MAC acak)"
    return "Unknown"
