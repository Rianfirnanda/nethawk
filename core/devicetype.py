"""Guess a device's type (and an icon glyph) from its vendor and hostname.
Purely heuristic -- used only for nicer UI labelling."""

# (keyword, type, emoji) — first match wins.
_RULES = [
    ("router", "Router", "\U0001F4E1"),
    ("tp-link", "Router", "\U0001F4E1"),
    ("mikrotik", "Router", "\U0001F4E1"),
    ("ubiquiti", "Router", "\U0001F4E1"),
    ("huawei", "Router", "\U0001F4E1"),
    ("zte", "Router", "\U0001F4E1"),
    ("fiberhome", "Router", "\U0001F4E1"),

    ("vivo", "HP", "\U0001F4F1"),
    ("oppo", "HP", "\U0001F4F1"),
    ("xiaomi", "HP", "\U0001F4F1"),
    ("redmi", "HP", "\U0001F4F1"),
    ("samsung", "HP", "\U0001F4F1"),
    ("realme", "HP", "\U0001F4F1"),
    ("oneplus", "HP", "\U0001F4F1"),
    ("apple", "Apple", "\U0001F34F"),
    ("iphone", "HP", "\U0001F4F1"),
    ("android", "HP", "\U0001F4F1"),
    ("motorola", "HP", "\U0001F4F1"),
    ("infinix", "HP", "\U0001F4F1"),
    ("tecno", "HP", "\U0001F4F1"),

    ("intel", "Laptop/PC", "\U0001F4BB"),
    ("liteon", "Laptop/PC", "\U0001F4BB"),
    ("dell", "Laptop/PC", "\U0001F4BB"),
    ("lenovo", "Laptop/PC", "\U0001F4BB"),
    ("asus", "Laptop/PC", "\U0001F4BB"),
    ("hewlett", "Laptop/PC", "\U0001F4BB"),
    ("micro-star", "Laptop/PC", "\U0001F4BB"),
    ("acer", "Laptop/PC", "\U0001F4BB"),

    ("sony", "TV/Media", "\U0001F4FA"),
    ("lg electronics", "TV/Media", "\U0001F4FA"),
    ("roku", "TV/Media", "\U0001F4FA"),
    ("google", "TV/Media", "\U0001F4FA"),
    ("amazon", "IoT", "\U0001F50C"),
    ("espressif", "IoT", "\U0001F50C"),
    ("tuya", "IoT", "\U0001F50C"),
    ("sonos", "IoT", "\U0001F50C"),
]


def guess(vendor: str = "", hostname: str = "") -> tuple:
    """Return (type_label, emoji)."""
    hay = ("%s %s" % (vendor or "", hostname or "")).lower()
    for kw, typ, emoji in _RULES:
        if kw in hay:
            return typ, emoji
    if "mac acak" in hay or "private" in hay:
        return "HP (privasi)", "\U0001F4F1"
    return "Perangkat", "\U0001F5A5"
