"""Pure hotspot policy decision (no I/O) + self-check.

Given a device's role, accumulated data, session time and the hotspot settings,
decide what the enforcer should do: allow / monitor / limit / cut.
Run `python core/policy.py` to self-check.
"""
MB = 1048576


def decide(role, total_bytes, session_secs, s):
    """Return (action, kbps). action in: allow, monitor, limit, cut."""
    if role == "staff":
        return ("allow", 0)
    if role == "blocked":
        return ("cut", 0)
    if s.get("quota_mb") and total_bytes > s["quota_mb"] * MB:
        return ("cut", 0)              # kuota data habis
    if s.get("quota_minutes") and session_secs > s["quota_minutes"] * 60:
        return ("cut", 0)              # kuota waktu habis
    if s.get("guest_kbps"):
        return ("limit", int(s["guest_kbps"]))
    if s.get("quota_mb"):
        return ("monitor", 0)          # perlu MITM untuk menghitung data
    return ("allow", 0)


def _demo():
    assert decide("staff", 9e9, 9e9, {"quota_mb": 1, "guest_kbps": 100}) == ("allow", 0)
    assert decide("blocked", 0, 0, {}) == ("cut", 0)
    assert decide("guest", 200 * MB, 0, {"quota_mb": 100}) == ("cut", 0)
    assert decide("guest", 0, 3700, {"quota_minutes": 60}) == ("cut", 0)
    assert decide("guest", 0, 0, {"guest_kbps": 512}) == ("limit", 512)
    assert decide("guest", 0, 0, {"quota_mb": 100}) == ("monitor", 0)
    assert decide("guest", 0, 0, {}) == ("allow", 0)
    print("policy OK")


if __name__ == "__main__":
    _demo()
