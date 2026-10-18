"""Observed-traffic stats from this machine's ACTIVE connections (psutil).

Honest scope: this reflects only traffic THIS PC can observe (its own live
connections). It does not see every host's traffic on a switched network, so
protocol/flow counts are by connection count, not bytes, and are labelled as
"observed". Per-app (domain) data comes from the engine for managed devices.

Run `python core/flows.py` to self-check the port->protocol mapping.
"""
import socket
from collections import Counter


def proto_of(rport, is_udp):
    if rport == 443:
        return "QUIC" if is_udp else "HTTPS/TLS"
    if rport == 80:
        return "HTTP"
    if rport == 53:
        return "DNS"
    if rport == 22:
        return "SSH"
    if rport == 123:
        return "NTP"
    if rport == 3389:
        return "RDP"
    if rport in (25, 110, 143, 465, 587, 993, 995):
        return "Mail"
    if rport in (3478, 19302, 5349):
        return "STUN/RTC"
    if rport in (1935,):
        return "RTMP"
    return "UDP :%d" % rport if is_udp else "TCP :%d" % rport


def observe():
    """Return observed protocol/flow/endpoint stats from local connections."""
    protos = Counter()
    endpoints = Counter()
    active = 0
    try:
        import psutil
        conns = psutil.net_connections(kind="inet")
    except Exception:
        conns = []
    for c in conns:
        raddr = getattr(c, "raddr", None)
        if not raddr or not getattr(raddr, "ip", None):
            continue
        ip = raddr.ip
        if ip in ("127.0.0.1", "::1") or ip == "0.0.0.0" or ip.startswith("fe80"):
            continue
        active += 1
        is_udp = (c.type == socket.SOCK_DGRAM)
        protos[proto_of(raddr.port, is_udp)] += 1
        endpoints[ip] += 1
    total = sum(protos.values()) or 1
    return {
        "active_flows": active,
        "protocols": [{"name": k, "count": v, "pct": round(v * 100 / total, 1)}
                      for k, v in protos.most_common(8)],
        "endpoints": [{"ip": k, "count": v} for k, v in endpoints.most_common(8)],
    }


def _demo():
    assert proto_of(443, False) == "HTTPS/TLS"
    assert proto_of(443, True) == "QUIC"
    assert proto_of(53, False) == "DNS"
    assert proto_of(80, False) == "HTTP"
    assert proto_of(993, False) == "Mail"
    assert proto_of(9999, True) == "UDP :9999"
    assert proto_of(1234, False) == "TCP :1234"
    print("flows OK")


if __name__ == "__main__":
    _demo()
