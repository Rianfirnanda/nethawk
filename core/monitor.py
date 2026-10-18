"""Total network throughput sampler (psutil).

Always works regardless of Wi-Fi limitations -- it reads this machine's NIC
byte counters. The dashboard hero graph uses this. Per-device realtime rates
come from the WinDivert engine (for devices currently managed/MITM'd).
"""
import time

from .logutil import log


class Throughput:
    def __init__(self):
        self._last = None

    def sample(self):
        """Return (up_Bps, down_Bps) since the previous sample."""
        try:
            import psutil
            io = psutil.net_io_counters()
        except Exception:
            return (0.0, 0.0)
        now = time.time()
        if self._last is None:
            self._last = (io.bytes_sent, io.bytes_recv, now)
            return (0.0, 0.0)
        ps, pr, pt = self._last
        dt = max(now - pt, 1e-3)
        up = max(0.0, (io.bytes_sent - ps) / dt)
        down = max(0.0, (io.bytes_recv - pr) / dt)
        self._last = (io.bytes_sent, io.bytes_recv, now)
        return (up, down)
