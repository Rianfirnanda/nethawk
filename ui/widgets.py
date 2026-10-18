"""Reusable Command Center widgets: animated stat tiles, sparklines, toggle
switches, badges + formatting helpers."""
from collections import deque

from PySide6.QtCore import (Qt, QVariantAnimation, QPropertyAnimation,
                            QEasingCurve, Property, QSize, QRectF, QPointF)
from PySide6.QtGui import (QPainter, QColor, QPen, QBrush, QLinearGradient,
                           QPainterPath, QFont)
from PySide6.QtWidgets import (QFrame, QLabel, QVBoxLayout, QHBoxLayout,
                               QWidget, QAbstractButton)

from .theme import (ACCENT, ACCENT2, TEXT, DIM, MUTED, BORDER, DANGER, WARN,
                    SURFACE2, BG2)


def human_bytes(n: float) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return (f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}")
        n /= 1024
    return f"{n:.1f} TB"


def human_rate(bps: float) -> str:
    if not bps or bps < 1:
        return "0 B/s"
    return human_bytes(bps) + "/s"


class Card(QFrame):
    def __init__(self, alt=False):
        super().__init__()
        self.setObjectName("cardAlt" if alt else "card")


class StatTile(Card):
    """Card with a title and an animated (counting) value."""

    def __init__(self, title, icon="", accent=TEXT):
        super().__init__()
        self._fmt = lambda v: str(int(round(v)))
        self._val = 0.0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(8)
        self._icon = QLabel(icon)
        self._icon.setStyleSheet("font-size:14px;")
        t = QLabel(title.upper())
        t.setObjectName("cardTitle")
        top.addWidget(self._icon)
        top.addWidget(t)
        top.addStretch(1)
        lay.addLayout(top)
        self._value = QLabel("0")
        self._value.setObjectName("statValue")
        self._value.setStyleSheet(f"color:{accent};")
        lay.addWidget(self._value)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(520)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(
            lambda v: self._value.setText(self._fmt(float(v))))

    def set_value(self, target, fmt=None):
        if fmt is not None:
            self._fmt = fmt
        try:
            target = float(target)
        except Exception:
            return
        self._anim.stop()
        self._anim.setStartValue(float(self._val))
        self._anim.setEndValue(target)
        self._val = target
        self._anim.start()

    def set_accent(self, color):
        self._value.setStyleSheet(f"color:{color};")


class Sparkline(QWidget):
    """Tiny filled line chart fed one value at a time."""

    def __init__(self, color=ACCENT, maxlen=46, height=34):
        super().__init__()
        self._data = deque([0.0] * maxlen, maxlen=maxlen)
        self._color = QColor(color)
        self.setMinimumHeight(height)
        self.setMinimumWidth(80)

    def push(self, v):
        self._data.append(max(0.0, float(v or 0)))
        self.update()

    def set_color(self, color):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        data = list(self._data)
        mx = max(data) or 1.0
        n = len(data)
        if n < 2:
            return
        step = w / (n - 1)
        path = QPainterPath()
        area = QPainterPath()
        area.moveTo(0, h)
        for i, v in enumerate(data):
            x = i * step
            y = h - (v / mx) * (h - 4) - 2
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
            area.lineTo(x, y)
        area.lineTo(w, h)
        area.closeSubpath()
        grad = QLinearGradient(0, 0, 0, h)
        c = QColor(self._color)
        c.setAlpha(70)
        grad.setColorAt(0, c)
        c2 = QColor(self._color)
        c2.setAlpha(0)
        grad.setColorAt(1, c2)
        p.fillPath(area, QBrush(grad))
        p.setPen(QPen(self._color, 1.8))
        p.drawPath(path)


class ToggleSwitch(QAbstractButton):
    """iOS-style animated on/off switch."""

    def __init__(self, checked=False):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self._offset = 1.0 if checked else 0.0
        self.setFixedSize(46, 26)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)
        self.toggled.connect(self._on_toggled)

    def _get_offset(self):
        return self._offset

    def _set_offset(self, v):
        self._offset = v
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _on_toggled(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def sizeHint(self):
        return QSize(46, 26)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        off = QColor(BORDER)
        on = QColor(ACCENT)
        track = QColor(
            int(off.red() + (on.red() - off.red()) * self._offset),
            int(off.green() + (on.green() - off.green()) * self._offset),
            int(off.blue() + (on.blue() - off.blue()) * self._offset))
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(0, 0, w, h, h / 2, h / 2)
        d = h - 6
        x = 3 + self._offset * (w - d - 6)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, 3, d, d))


class Badge(QLabel):
    """Small rounded status pill."""

    def __init__(self, text="", color=ACCENT):
        super().__init__(text)
        self.set_color(color)
        self.setAlignment(Qt.AlignCenter)

    def set(self, text, color):
        self.setText(text)
        self.set_color(color)

    def set_color(self, color):
        c = QColor(color)
        self.setStyleSheet(
            f"color:{color}; background: rgba({c.red()},{c.green()},{c.blue()},40);"
            f"border:1px solid rgba({c.red()},{c.green()},{c.blue()},90);"
            f"border-radius:9px; padding:2px 9px; font-size:11px; font-weight:700;")
