"""Fenêtres d'AikoPipette : panneau (historique, palette), bulle « copié », réglage du raccourci."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (QDialog, QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel,
                               QMenu, QPushButton, QToolButton, QVBoxLayout, QWidget)

from .colors import FORMATS, as_text
from .hotkey import IS_WIN, MOD_ORDER, Shortcut
from .theme import ACCENT, ON_ACCENT, css, theme, ui_font

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".avif"}


class Swatch(QPushButton):
    def __init__(self, hexv: str, size: int, ctl, removable: bool):
        super().__init__()
        self.hexv, self.ctl, self.removable = hexv, ctl, removable
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{hexv} — clic pour copier")
        self.clicked.connect(lambda: ctl.copy(hexv))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def _menu(self, pos):
        m = QMenu(self)
        for fmt in FORMATS:
            m.addAction(f"Copier {as_text(self.hexv, fmt)}", lambda f=fmt: self.ctl.copy(self.hexv, f))
        if self.removable:
            m.addSeparator()
            m.addAction("Supprimer", lambda: self.ctl.remove(self.hexv))
        m.exec(self.mapToGlobal(pos))

    def paintEvent(self, _):
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        flashed = self.ctl.flash == self.hexv
        p.setPen(QPen(ACCENT if flashed else t["line"], 2 if flashed else 1))
        p.setBrush(QColor(self.hexv))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 7, 7)
        p.end()


class DropZone(QFrame):
    dropped = Signal(Path)

    def __init__(self):
        super().__init__()
        self.setObjectName("drop")
        self.setAcceptDrops(True)
        self.hot = False

    @staticmethod
    def _image(e) -> Path | None:
        if not e.mimeData().hasUrls():
            return None
        for u in e.mimeData().urls():
            if u.isLocalFile() and Path(u.toLocalFile()).suffix.lower() in IMAGE_EXTS:
                return Path(u.toLocalFile())
        return None

    def dragEnterEvent(self, e):
        if self._image(e):
            e.setDropAction(Qt.DropAction.CopyAction)
            e.accept()
            self._set_hot(True)
        else:
            e.ignore()

    def dragLeaveEvent(self, _):
        self._set_hot(False)

    def dropEvent(self, e):
        self._set_hot(False)
        path = self._image(e)
        if path:
            e.setDropAction(Qt.DropAction.CopyAction)
            e.accept()
            self.dropped.emit(path)

    def _set_hot(self, on: bool):
        self.hot = on
        self.setProperty("hot", on)
        self.style().unpolish(self)
        self.style().polish(self)


class PaletteWindow(QWidget):
    """Le panneau qui s'ouvre depuis l'icône."""

    def __init__(self, ctl):
        super().__init__(None)
        self.ctl = ctl
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("AikoPipette")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        self.card = QFrame()
        self.card.setObjectName("card")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.card.setGraphicsEffect(shadow)
        outer.addWidget(self.card)

        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel("AikoPipette")
        title.setObjectName("title")
        self.sc_label = QLabel()
        self.sc_label.setObjectName("chip")
        close = QToolButton()
        close.setText("✕")
        close.setObjectName("close")
        close.clicked.connect(self.hide)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.sc_label)
        head.addWidget(close)
        lay.addLayout(head)

        self.pick_btn = QPushButton("Prendre une couleur")
        self.pick_btn.setObjectName("pick")
        self.pick_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pick_btn.clicked.connect(ctl.start_pick)
        lay.addWidget(self.pick_btn)

        self.current = QHBoxLayout()
        self.current.setSpacing(12)
        lay.addLayout(self.current)

        lay.addWidget(self._section("Historique"))
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(8)
        lay.addWidget(self.grid_host)

        lay.addWidget(self._section("Palette d'une image"))
        self.drop = DropZone()
        self.drop.dropped.connect(ctl.extract)
        self.drop_lay = QVBoxLayout(self.drop)
        self.drop_lay.setContentsMargins(10, 10, 10, 10)
        lay.addWidget(self.drop)

        foot = QHBoxLayout()
        foot.setSpacing(0)
        self.fmt_buttons = []
        for i, fmt in enumerate(FORMATS):
            b = QPushButton(fmt)
            b.setCheckable(True)
            b.setObjectName("seg" + ("L" if i == 0 else "R" if i == len(FORMATS) - 1 else "M"))
            b.clicked.connect(lambda _=False, f=fmt: ctl.set_format(f))
            self.fmt_buttons.append(b)
            foot.addWidget(b)
        foot.addStretch(1)
        more = QToolButton()
        more.setText("⋯")
        more.setObjectName("more")
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_menu = QMenu(more)
        more.setMenu(self.more_menu)
        foot.addWidget(more)
        lay.addLayout(foot)

        self.setFixedWidth(352 + 32)
        self.apply_theme()
        self.refresh()

    def _section(self, text: str) -> QLabel:
        lab = QLabel(text.upper())
        lab.setObjectName("section")
        return lab

    # ------------------------------------------------------------ contenu

    def refresh(self):
        ctl = self.ctl
        self.sc_label.setText(ctl.shortcut.label())
        self.pick_btn.setText("Prendre une couleur" if ctl.can_pick else "Pipette indisponible (Wayland)")
        self.pick_btn.setEnabled(ctl.can_pick)
        for b in self.fmt_buttons:
            b.setChecked(b.text() == ctl.format)

        _clear(self.current)
        if ctl.history:
            hexv = ctl.history[0]
            big = Swatch(hexv, 46, ctl, removable=False)
            self.current.addWidget(big)
            col = QVBoxLayout()
            col.setSpacing(1)
            for fmt in FORMATS:
                b = QPushButton(as_text(hexv, fmt))
                b.setObjectName("value" if fmt == "HEX" else "subvalue")
                b.setFlat(True)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setToolTip("Copier")
                b.clicked.connect(lambda _=False, f=fmt: ctl.copy(hexv, f))
                col.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
            self.current.addLayout(col)
            self.current.addStretch(1)
            if ctl.flash:
                ok = QLabel("Copié")
                ok.setObjectName("copied")
                self.current.addWidget(ok)

        _clear(self.grid)
        if not ctl.history:
            empty = QLabel("Les couleurs prises s'afficheront ici.")
            empty.setObjectName("hint")
            self.grid.addWidget(empty, 0, 0)
        for i, hexv in enumerate(ctl.history):
            self.grid.addWidget(Swatch(hexv, 30, ctl, removable=True), i // 8, i % 8)

        _clear(self.drop_lay)
        if ctl.palette:
            row = QHBoxLayout()
            row.setSpacing(6)
            for hexv in ctl.palette:
                row.addWidget(Swatch(hexv, 38, ctl, removable=False))
            row.addStretch(1)
            self.drop_lay.addLayout(row)
            info = QHBoxLayout()
            src = QLabel(QFontMetrics(self.font()).elidedText(ctl.palette_source, Qt.TextElideMode.ElideMiddle, 200))
            src.setObjectName("hint")
            all_btn = QPushButton("Tout copier")
            all_btn.setObjectName("link")
            all_btn.setFlat(True)
            all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            all_btn.clicked.connect(ctl.copy_palette)
            info.addWidget(src)
            info.addStretch(1)
            info.addWidget(all_btn)
            self.drop_lay.addLayout(info)
            self.drop.setProperty("filled", True)
        else:
            lab = QLabel(ctl.palette_source or "Glisse une image ici")
            lab.setObjectName("hint")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setMinimumHeight(44)
            self.drop_lay.addWidget(lab)
            self.drop.setProperty("filled", False)
        self.drop.style().unpolish(self.drop)
        self.drop.style().polish(self.drop)

        self.more_menu.clear()
        self.more_menu.addAction("Changer le raccourci…", ctl.change_shortcut)
        act = self.more_menu.addAction("Lancer au démarrage")
        act.setCheckable(True)
        act.setChecked(ctl.autostart)
        act.toggled.connect(ctl.set_autostart)
        self.more_menu.addAction("Effacer l'historique", ctl.clear_history)
        self.more_menu.addSeparator()
        self.more_menu.addAction("Quitter AikoPipette", ctl.quit)
        self.adjustSize()

    def apply_theme(self):
        t = theme()
        self.setStyleSheet(f"""
            QFrame#card {{ background: {css(t['bg'])}; border: 1px solid {css(t['line'])}; border-radius: 14px; }}
            QLabel {{ color: {css(t['text'])}; background: transparent; border: none; }}
            QLabel#title {{ font-size: 13px; font-weight: 600; }}
            QLabel#chip {{ color: {css(t['subtext'])}; font-size: 11px; border: 1px solid {css(t['line'])};
                           border-radius: 5px; padding: 2px 6px; }}
            QLabel#section {{ color: {css(t['subtext'])}; font-size: 10px; font-weight: 600; letter-spacing: 0.6px; }}
            QLabel#hint {{ color: {css(t['subtext'])}; font-size: 12px; }}
            QLabel#copied {{ color: {css(ACCENT)}; font-size: 11px; font-weight: 600; }}
            QPushButton#pick {{ background: {css(ACCENT)}; color: {css(ON_ACCENT)}; border: none; border-radius: 8px;
                                padding: 9px; font-size: 13px; font-weight: 600; }}
            QPushButton#pick:disabled {{ background: {css(t['surface'])}; color: {css(t['subtext'])}; }}
            QPushButton#value, QPushButton#subvalue, QPushButton#link {{ border: none; background: transparent;
                                text-align: left; padding: 0; }}
            QPushButton#value {{ color: {css(t['text'])}; font-size: 14px; font-weight: 600; font-family: monospace; }}
            QPushButton#subvalue {{ color: {css(t['subtext'])}; font-size: 11px; font-family: monospace; }}
            QPushButton#link {{ color: {css(ACCENT)}; font-size: 11px; font-weight: 600; }}
            QFrame#drop {{ background: {css(t['surface'])}; border: 1px dashed {css(t['line'])}; border-radius: 10px; }}
            QFrame#drop[filled="true"] {{ border-style: solid; }}
            QFrame#drop[hot="true"] {{ border: 1.5px solid {css(ACCENT)}; }}
            QPushButton#segL, QPushButton#segM, QPushButton#segR {{ color: {css(t['subtext'])}; background: transparent;
                border: 1px solid {css(t['line'])}; padding: 4px 12px; font-size: 11px; font-weight: 600; }}
            QPushButton#segL {{ border-top-left-radius: 6px; border-bottom-left-radius: 6px; }}
            QPushButton#segR {{ border-top-right-radius: 6px; border-bottom-right-radius: 6px; }}
            QPushButton#segL:checked, QPushButton#segM:checked, QPushButton#segR:checked {{
                background: {css(ACCENT)}; color: {css(ON_ACCENT)}; border-color: {css(ACCENT)}; }}
            QToolButton#more, QToolButton#close {{ color: {css(t['subtext'])}; background: transparent; border: none;
                font-size: 16px; padding: 0 4px; }}
            QToolButton#more::menu-indicator {{ image: none; }}
        """)

    # ------------------------------------------------------------ position

    def show_near(self, anchor):
        """S'ouvre près de l'icône (zone de notification), sinon dans le coin de l'écran."""
        self.refresh()
        screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        w, h = self.sizeHint().width(), self.sizeHint().height()
        x = min(max(anchor.x() - w // 2, geo.left()), geo.right() - w)
        y = anchor.y() - h - 4 if anchor.y() > geo.center().y() else anchor.y() + 8
        y = min(max(y, geo.top()), geo.bottom() - h)
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()


def _clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.hide()            # sinon l'ancien widget reste affiché un instant en haut à gauche
            w.setParent(None)
            w.deleteLater()
        elif item.layout():
            _clear(item.layout())


class Bubble(QWidget):
    """« ● #7DC8FF  copié » près de la souris."""

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus
                            | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.hexv, self.text = "#000000", ""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_color(self, hexv: str, text: str, near: QPoint):
        self.hexv, self.text = hexv, f"{text}  copié"
        fm = QFontMetrics(ui_font(12.5, QFont.Weight.DemiBold, mono=True))
        w = fm.horizontalAdvance(self.text) + 52
        self.setFixedSize(w + 20, 36 + 20)
        screen = QGuiApplication.screenAt(near) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = min(max(near.x() - self.width() // 2, geo.left()), geo.right() - self.width())
        y = min(max(near.y() - 70, geo.top()), geo.bottom() - self.height())
        self.move(x, y)
        self.show()
        self.raise_()
        self.update()
        self._timer.start(1600)

    def paintEvent(self, _):
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        box = QRectF(10, 8, self.width() - 20, 36)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(8, 0, -1):
            p.setBrush(QColor(0, 0, 0, 7))
            p.drawRoundedRect(box.adjusted(-i, -i + 2, i, i + 2), 18 + i, 18 + i)
        p.setPen(QPen(t["line"], 1))
        p.setBrush(t["bg"])
        p.drawRoundedRect(box, 18, 18)
        p.setBrush(QColor(self.hexv))
        p.drawEllipse(QRectF(box.left() + 10, box.center().y() - 9, 18, 18))
        p.setPen(t["text"])
        p.setFont(ui_font(12.5, QFont.Weight.DemiBold, mono=True))
        p.drawText(box.adjusted(36, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text)
        p.end()


# ------------------------------------------------------------ réglage du raccourci

_QT_MOD_KEYS = {Qt.Key.Key_Shift: "shift", Qt.Key.Key_Control: "ctrl", Qt.Key.Key_Alt: "alt",
                Qt.Key.Key_AltGr: "alt", Qt.Key.Key_Meta: "meta", Qt.Key.Key_Super_L: "meta",
                Qt.Key.Key_Super_R: "meta"}
_KEY_NAMES = {"Space": "Espace", "Return": "Entrée", "Enter": "Entrée", "Del": "Suppr", "Ins": "Inser"}


def _mods(modifiers) -> list[str]:
    out = []
    for name, flag in (("ctrl", Qt.KeyboardModifier.ControlModifier), ("alt", Qt.KeyboardModifier.AltModifier),
                       ("shift", Qt.KeyboardModifier.ShiftModifier), ("meta", Qt.KeyboardModifier.MetaModifier)):
        if modifiers & flag:
            out.append(name)
    return out


class ShortcutDialog(QDialog):
    def __init__(self, current: Shortcut):
        super().__init__(None)
        self.setWindowTitle("Raccourci AikoPipette")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(400)
        self.pending = Shortcut(list(current.mods), current.key, current.key_label)

        intro = QLabel("Appuie sur la combinaison qui lancera la pipette "
                       f"(une touche, avec ou sans Ctrl, Alt, Maj{', Win' if IS_WIN else ''}).")
        intro.setWordWrap(True)
        self.display = QLabel(self.pending.label())
        f = QFont()
        f.setPixelSize(24)
        f.setWeight(QFont.Weight.DemiBold)
        self.display.setFont(f)
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display.setMinimumHeight(56)
        self.display.setStyleSheet(f"border: 1.5px solid {css(ACCENT)}; border-radius: 10px; padding: 8px;")

        reset = QPushButton("Rétablir Alt + C")
        cancel = QPushButton("Annuler")
        self.save = QPushButton("Enregistrer")
        self.save.setStyleSheet(f"QPushButton {{ background: {css(ACCENT)}; color: {css(ON_ACCENT)}; border: none; "
                                "border-radius: 6px; padding: 6px 14px; font-weight: 600; }")
        for b in (reset, cancel, self.save):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setAutoDefault(False)
        reset.clicked.connect(self._reset)
        cancel.clicked.connect(self.reject)
        self.save.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addWidget(reset)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(self.save)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 18)
        lay.setSpacing(14)
        lay.addWidget(intro)
        lay.addWidget(self.display)
        lay.addLayout(row)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def showEvent(self, e):
        super().showEvent(e)
        self.activateWindow()
        self.setFocus()

    def focusNextPrevChild(self, _next: bool) -> bool:
        return False

    def _reset(self):
        self.pending = Shortcut()
        self.display.setText(self.pending.label())
        self.save.setEnabled(True)

    def keyPressEvent(self, e):
        if e.isAutoRepeat():
            return
        key = e.key()
        if key == Qt.Key.Key_Escape:
            self.reject()
            return
        mods = _mods(e.modifiers())
        if key in _QT_MOD_KEYS:
            mods = sorted(set(mods) | {_QT_MOD_KEYS[key]}, key=MOD_ORDER.index)
            self.display.setText(" + ".join(Shortcut(mods).label().split(" + ")[:-1] + ["…"]))
            self.save.setEnabled(False)
            return
        name = QKeySequence(key).toString(QKeySequence.SequenceFormat.PortableText) or e.text().upper() or "?"
        name = _KEY_NAMES.get(name, name)
        native = int(e.nativeVirtualKey()) or int(key)
        self.pending = Shortcut(sorted(mods, key=MOD_ORDER.index), native, name)
        self.display.setText(self.pending.label())
        self.save.setEnabled(True)
