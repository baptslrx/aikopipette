"""Pipette plein écran : l'écran est figé, une loupe suit la souris, clic = couleur."""
from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .colors import hex_of, is_light
from .theme import ACCENT, theme, ui_font

CELLS = 11      # pixels visibles dans la loupe (impair)
CELL = 11       # taille d'un pixel agrandi
LOUPE = CELLS * CELL


class _Overlay(QWidget):
    picked = Signal(str)
    cancelled = Signal()

    def __init__(self, screen, image: QImage, dpr: float):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.screen_ = screen
        self.image = image
        self.dpr = dpr or 1.0
        self.cursor_pos: QPointF | None = None
        self.setGeometry(screen.geometry())

    # pixel de l'image sous un point de la fenêtre
    def _px(self, p: QPointF) -> QPoint:
        x = min(max(int(p.x() * self.dpr), 0), self.image.width() - 1)
        y = min(max(int(p.y() * self.dpr), 0), self.image.height() - 1)
        return QPoint(x, y)

    def color_at(self, p: QPointF) -> str:
        c = self.image.pixelColor(self._px(p))
        return hex_of(c.red(), c.green(), c.blue())

    def enterEvent(self, _):
        self.activateWindow()
        self.setFocus()

    def mouseMoveEvent(self, e):
        self.cursor_pos = e.position()
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.picked.emit(self.color_at(e.position()))
        else:
            self.cancelled.emit()

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_Escape:
            self.cancelled.emit()
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) and self.cursor_pos is not None:
            self.picked.emit(self.color_at(self.cursor_pos))
        elif k in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            dx = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1}.get(k, 0)
            dy = {Qt.Key.Key_Up: -1, Qt.Key.Key_Down: 1}.get(k, 0)
            QCursor.setPos(QCursor.pos() + QPoint(dx, dy))  # déplacement au pixel près

    def paintEvent(self, _):
        p = QPainter(self)
        p.drawImage(QRectF(self.rect()), self.image)
        if self.cursor_pos is not None:
            self._draw_loupe(p, self.cursor_pos)
        p.end()

    def _draw_loupe(self, p: QPainter, pos: QPointF):
        t = theme()
        center = self._px(pos)
        half = CELLS // 2
        src = QRect(center.x() - half, center.y() - half, CELLS, CELLS)

        # la loupe se place en bas à droite du curseur, ou de l'autre côté près des bords
        x = pos.x() + 22
        y = pos.y() + 22
        if x + LOUPE + 10 > self.width():
            x = pos.x() - 22 - LOUPE
        if y + LOUPE + 44 > self.height():
            y = pos.y() - 22 - LOUPE - 34
        box = QRectF(x, y, LOUPE, LOUPE)

        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addEllipse(box)

        # ombre douce
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(8, 0, -1):
            p.setBrush(QColor(0, 0, 0, 10))
            p.drawEllipse(box.adjusted(-i, -i + 2, i, i + 2))

        p.save()
        p.setClipPath(clip)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.fillRect(box, QColor(0, 0, 0))
        p.drawImage(box, self.image, QRectF(src))
        grid = QPen(QColor(255, 255, 255, 28), 1)
        p.setPen(grid)
        for i in range(1, CELLS):
            p.drawLine(QPointF(box.left() + i * CELL, box.top()), QPointF(box.left() + i * CELL, box.bottom()))
            p.drawLine(QPointF(box.left(), box.top() + i * CELL), QPointF(box.right(), box.top() + i * CELL))
        hexv = self.color_at(pos)
        mid = QRectF(box.left() + half * CELL, box.top() + half * CELL, CELL, CELL)
        p.setPen(QPen(QColor("#000000") if is_light(hexv) else QColor("#FFFFFF"), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(mid)
        p.restore()

        p.setPen(QPen(ACCENT, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(box)

        # pastille + valeur sous la loupe
        font = ui_font(12, QFont.Weight.DemiBold, mono=True)
        p.setFont(font)
        w = p.fontMetrics().horizontalAdvance(hexv) + 40
        pill = QRectF(box.center().x() - w / 2, box.bottom() + 8, w, 26)
        p.setPen(QPen(t["line"], 1))
        p.setBrush(t["bg"])
        p.drawRoundedRect(pill, 13, 13)
        p.setPen(QPen(t["line"], 1))
        p.setBrush(QColor(hexv))
        p.drawEllipse(QRectF(pill.left() + 7, pill.center().y() - 7, 14, 14))
        p.setPen(t["text"])
        p.drawText(pill.adjusted(28, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, hexv)


class ScreenPicker(QObject):
    picked = Signal(str)

    def __init__(self):
        super().__init__()
        self.overlays: list[_Overlay] = []

    @property
    def active(self) -> bool:
        return bool(self.overlays)

    def start(self):
        if self.overlays:
            return
        for screen in QGuiApplication.screens():
            pm = screen.grabWindow(0)
            o = _Overlay(screen, pm.toImage(), pm.devicePixelRatio())
            o.picked.connect(self._done)
            o.cancelled.connect(self._close)
            self.overlays.append(o)
        under = QGuiApplication.screenAt(QCursor.pos())
        for o in self.overlays:
            o.show()
            o.raise_()
            if o.screen_ is under:
                o.activateWindow()
                o.setFocus()
                o.cursor_pos = QPointF(o.mapFromGlobal(QCursor.pos()))

    def _done(self, hexv: str):
        self._close()
        self.picked.emit(hexv)

    def _close(self):
        for o in self.overlays:
            o.close()
        self.overlays = []
