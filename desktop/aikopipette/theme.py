"""Charte AikoRoue / AikoPipette : noir ou blanc selon le système + bleu clair."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QPainter, QPalette, QPen, QPixmap

ACCENT = QColor("#7DC8FF")
ON_ACCENT = QColor("#05121C")

DARK = dict(bg=QColor(10, 10, 12), surface=QColor("#17171A"), line=QColor(255, 255, 255, 23),
            text=QColor("#F5F7FA"), subtext=QColor("#8C949E"))
LIGHT = dict(bg=QColor(255, 255, 255), surface=QColor("#F2F7FC"), line=QColor(0, 0, 0, 20),
             text=QColor("#0A0D10"), subtext=QColor("#6B7380"))


def is_dark() -> bool:
    try:
        scheme = QGuiApplication.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except AttributeError:
        pass
    return QGuiApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128


def theme() -> dict:
    return DARK if is_dark() else LIGHT


def css(c: QColor) -> str:
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {c.alpha() / 255:.3f})"


def ui_font(px: float, weight: QFont.Weight = QFont.Weight.Normal, mono: bool = False) -> QFont:
    f = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont) if mono else QFont()
    f.setPixelSize(max(1, round(px)))
    f.setWeight(weight)
    return f


def tray_icon() -> QIcon:
    """Petite pipette bleu clair pour la zone de notification."""
    icon = QIcon()
    for s in (16, 20, 24, 32, 48, 64):
        pm = QPixmap(s, s)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        k = s / 18
        pen = QPen(ACCENT, 2.2 * k)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(3.5 * k, 14.5 * k), QPointF(11 * k, 7 * k))   # tube
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ACCENT)
        p.drawEllipse(QPointF(13 * k, 5 * k), 3.4 * k, 3.4 * k)          # poire
        p.drawEllipse(QPointF(2.6 * k, 15.4 * k), 1.3 * k, 1.3 * k)       # goutte
        p.end()
        icon.addPixmap(pm)
    return icon
