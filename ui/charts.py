"""Custom-painted realtime throughput chart (no third-party chart lib, so the
look is fully ours). Shows download + upload as two filled curves."""
from collections import deque

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import (QPainter, QColor, QPen, QBrush, QLinearGradient,
                           QPainterPath, QFont)
from PySide6.QtWidgets import QWidget

from .theme import ACCENT, ACCENT2, TEXT, DIM, MUTED, BORDER
from .widgets import human_rate


class ThroughputChart(QWidget):
    def __init__(self, points=70):
        super().__init__()
        self.setMinimumHeight(210)
        self._down = deque([0.0] * points, maxlen=points)
        self._up = deque([0.0] * points, maxlen=points)
        self._cur_down = 0.0
        self._cur_up = 0.0
        # gentle repaint for a "breathing" feel even between samples
        self._t = QTimer(self)
        self._t.timeout.connect(self.update)
        self._t.start(60)

    def push(self, up, down):
        self._up.append(max(0.0, float(up or 0)))
        self._down.append(max(0.0, float(down or 0)))
        self._cur_up = max(0.0, float(up or 0))
        self._cur_down = max(0.0, float(down or 0))

    def _series_path(self, data, w, h, mx, pad_top, pad_bottom):
        n = len(data)
        step = w / (n - 1)
        line = QPainterPath()
        area = QPainterPath()
        usable = h - pad_top - pad_bottom
        area.moveTo(0, h - pad_bottom)
        for i, v in enumerate(data):
            x = i * step
            y = h - pad_bottom - (v / mx) * usable
            if i == 0:
                line.moveTo(x, y)
            else:
                line.lineTo(x, y)
            area.lineTo(x, y)
        area.lineTo(w, h - pad_bottom)
        area.closeSubpath()
        return line, area

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        pad_top, pad_bottom = 30, 16

        mx = max(max(self._down), max(self._up), 1024.0) * 1.2

        # grid
        p.setPen(QPen(QColor(BORDER), 1, Qt.DotLine))
        for i in range(1, 4):
            y = pad_top + (h - pad_top - pad_bottom) * i / 4
            p.drawLine(0, int(y), w, int(y))

        # download (accent)
        dl, da = self._series_path(list(self._down), w, h, mx, pad_top, pad_bottom)
        grad = QLinearGradient(0, pad_top, 0, h)
        c = QColor(ACCENT); c.setAlpha(90); grad.setColorAt(0, c)
        c2 = QColor(ACCENT); c2.setAlpha(0); grad.setColorAt(1, c2)
        p.fillPath(da, QBrush(grad))
        p.setPen(QPen(QColor(ACCENT), 2))
        p.drawPath(dl)

        # upload (cyan)
        ul, ua = self._series_path(list(self._up), w, h, mx, pad_top, pad_bottom)
        grad2 = QLinearGradient(0, pad_top, 0, h)
        d = QColor(ACCENT2); d.setAlpha(55); grad2.setColorAt(0, d)
        d2 = QColor(ACCENT2); d2.setAlpha(0); grad2.setColorAt(1, d2)
        p.fillPath(ua, QBrush(grad2))
        p.setPen(QPen(QColor(ACCENT2), 2))
        p.drawPath(ul)

        # legend / current values
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.setPen(QColor(ACCENT))
        p.drawText(QRectF(4, 4, w / 2, 22), Qt.AlignLeft | Qt.AlignVCenter,
                   "↓  " + human_rate(self._cur_down))
        p.setPen(QColor(ACCENT2))
        p.drawText(QRectF(4, 4, w - 8, 22), Qt.AlignRight | Qt.AlignVCenter,
                   "↑  " + human_rate(self._cur_up))

        # scale label
        p.setPen(QColor(MUTED))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(4, pad_top - 2, 120, 14), Qt.AlignLeft,
                   "max " + human_rate(mx))
