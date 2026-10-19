"""AikoPipette pour Windows et Linux."""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import __version__
from .colors import FORMATS, as_text, extract_palette
from .hotkey import IS_WAYLAND, IS_WIN, GlobalHotkey, Shortcut
from .picker import ScreenPicker
from .theme import tray_icon
from .ui import Bubble, PaletteWindow, ShortcutDialog

APP_ID = "aikopipette-instance"


def resource(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    for cand in (base / "assets" / name, base.parent / "assets" / name):
        if cand.exists():
            return cand
    return base / name


def _exe_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{os.environ.get("APPIMAGE", sys.executable)}"'
    return f'"{sys.executable}" -m aikopipette'


def _desktop_file() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart" / "aikopipette.desktop"


class Controller(QObject):
    palette_ready = Signal(list, str)

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.settings = QSettings("Aikographic", "AikoPipette")
        try:
            self.history: list[str] = json.loads(self.settings.value("history", "[]", type=str))
        except Exception:
            self.history = []
        self.format = self.settings.value("format", "HEX", type=str)
        if self.format not in FORMATS:
            self.format = "HEX"
        self.shortcut = Shortcut.loads(self.settings.value("shortcut", "", type=str))
        self.palette: list[str] = []
        self.palette_source = ""
        self.flash: str | None = None
        self.can_pick = not IS_WAYLAND

        self.picker = ScreenPicker()
        self.picker.picked.connect(self._picked)
        self.bubble = Bubble()
        self.window = PaletteWindow(self)
        self.palette_ready.connect(self._palette_ready)

        self.hotkey = GlobalHotkey()
        self.hotkey.pressed.connect(self.start_pick)
        self.hotkey_ok = self.hotkey.register(self.shortcut) if self.hotkey.available else False

        self.tray = QSystemTrayIcon(tray_icon(), self)
        self.tray.setToolTip(f"AikoPipette — {self.shortcut.label()}")
        self.tray.activated.connect(self._tray_clicked)
        menu = QMenu()
        menu.addAction("Prendre une couleur", self.start_pick)
        menu.addAction("Ouvrir AikoPipette", self.open_window)
        menu.addSeparator()
        menu.addAction("Quitter AikoPipette", self.quit)
        self.tray.setContextMenu(menu)
        self.tray_menu = menu
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

        self.server = QLocalServer(self)
        QLocalServer.removeServer(APP_ID)
        self.server.listen(APP_ID)
        self.server.newConnection.connect(self._second_launch)

        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda *_: self.window.apply_theme())

        if not self.settings.value("welcomed", False, type=bool):
            self.settings.setValue("welcomed", True)
            QTimer.singleShot(300, self._welcome)
        elif not QSystemTrayIcon.isSystemTrayAvailable():
            self.open_window()
        if self.hotkey.available and not self.hotkey_ok:
            QTimer.singleShot(1200, lambda: self.tray.showMessage(
                "AikoPipette", f"Le raccourci {self.shortcut.label()} est déjà utilisé par une autre appli. "
                               "Choisis-en un autre dans « ⋯ → Changer le raccourci… ».",
                QSystemTrayIcon.MessageIcon.Warning, 6000))

    # ------------------------------------------------------------ pipette

    def start_pick(self):
        if not self.can_pick:
            self.open_window()
            return
        self.window.hide()
        QTimer.singleShot(120, self.picker.start)  # laisse le panneau disparaître avant la capture

    def _picked(self, hexv: str):
        self.history = [hexv] + [h for h in self.history if h != hexv]
        self.history = self.history[:32]
        self._save_history()
        text = self.copy(hexv)
        self.bubble.show_color(hexv, text, QCursor.pos())

    # ------------------------------------------------------------ actions du panneau

    def copy(self, hexv: str, fmt: str | None = None) -> str:
        text = as_text(hexv, fmt or self.format)
        QGuiApplication.clipboard().setText(text)
        self.flash = hexv
        QTimer.singleShot(1200, self._unflash(hexv))
        if self.window.isVisible():
            self.window.refresh()
        return text

    def _unflash(self, hexv):
        def run():
            if self.flash == hexv:
                self.flash = None
                if self.window.isVisible():
                    self.window.refresh()
        return run

    def copy_palette(self):
        QGuiApplication.clipboard().setText("\n".join(as_text(h, self.format) for h in self.palette))

    def remove(self, hexv: str):
        self.history = [h for h in self.history if h != hexv]
        self._save_history()
        self.window.refresh()

    def clear_history(self):
        self.history = []
        self._save_history()
        self.window.refresh()

    def set_format(self, fmt: str):
        self.format = fmt
        self.settings.setValue("format", fmt)
        self.window.refresh()

    def extract(self, path: Path):
        self.palette_source = f"Analyse de {path.name}…"
        self.window.refresh()

        def work():
            try:
                colors = extract_palette(path)
                self.palette_ready.emit(colors, path.name)
            except Exception:
                self.palette_ready.emit([], "Image illisible")

        threading.Thread(target=work, daemon=True).start()

    def _palette_ready(self, colors: list, source: str):
        self.palette, self.palette_source = colors, source
        self.window.refresh()

    def _save_history(self):
        self.settings.setValue("history", json.dumps(self.history))

    # ------------------------------------------------------------ réglages

    def change_shortcut(self):
        self.hotkey.unregister()  # pour pouvoir taper le raccourci actuel lui-même
        dlg = ShortcutDialog(self.shortcut)
        if dlg.exec():
            self.shortcut = dlg.pending
            self.settings.setValue("shortcut", self.shortcut.dumps())
        self.hotkey_ok = self.hotkey.register(self.shortcut) if self.hotkey.available else False
        self.tray.setToolTip(f"AikoPipette — {self.shortcut.label()}")
        if self.hotkey.available and not self.hotkey_ok:
            QMessageBox.warning(None, "AikoPipette",
                                f"{self.shortcut.label()} est déjà utilisé par une autre appli. Choisis-en un autre.")
        self.window.refresh()

    @property
    def autostart(self) -> bool:
        if IS_WIN:
            import winreg

            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
                    winreg.QueryValueEx(k, "AikoPipette")
                    return True
            except OSError:
                return False
        return _desktop_file().exists()

    def set_autostart(self, on: bool):
        try:
            if IS_WIN:
                import winreg

                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run",
                                    0, winreg.KEY_SET_VALUE) as k:
                    if on:
                        winreg.SetValueEx(k, "AikoPipette", 0, winreg.REG_SZ, _exe_command())
                    else:
                        try:
                            winreg.DeleteValue(k, "AikoPipette")
                        except OSError:
                            pass
            else:
                f = _desktop_file()
                if on:
                    f.parent.mkdir(parents=True, exist_ok=True)
                    f.write_text("[Desktop Entry]\nType=Application\nName=AikoPipette\n"
                                 f"Exec={_exe_command()}\nX-GNOME-Autostart-enabled=true\n", encoding="utf-8")
                elif f.exists():
                    f.unlink()
        except Exception as e:
            QMessageBox.warning(None, "AikoPipette", f"Impossible de modifier le démarrage automatique :\n{e}")

    def quit(self):
        self.hotkey.unregister()
        self.app.quit()

    # ------------------------------------------------------------ icône

    def open_window(self):
        geo = self.tray.geometry()
        anchor = geo.center() if geo.isValid() and not geo.isEmpty() else None
        if anchor is None:
            scr = QGuiApplication.primaryScreen().availableGeometry()
            anchor = scr.bottomRight() if IS_WIN else scr.topRight()
        self.window.show_near(anchor)

    def _tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.window.isVisible():
                self.window.hide()
            else:
                self.open_window()

    def _second_launch(self):
        sock = self.server.nextPendingConnection()
        if sock:
            sock.close()
        self.open_window()

    def _welcome(self):
        box = QMessageBox()
        box.setWindowTitle("AikoPipette")
        box.setIconPixmap(QIcon(str(resource("icon-256.png"))).pixmap(64, 64))
        box.setText("<b>AikoPipette est prête</b>")
        if self.can_pick:
            how = (f"Appuie sur {self.shortcut.label()} n'importe où : l'écran se fige et une loupe suit ta souris. "
                   "Clique sur une couleur : elle est copiée (HEX par défaut) et ajoutée à ton historique.\n\n"
                   "Échap annule, les flèches déplacent la souris au pixel près.")
        else:
            how = ("Ton bureau Linux (Wayland) ne permet pas de capturer l'écran : la pipette n'est pas disponible, "
                   "mais tu peux glisser une image dans AikoPipette pour obtenir sa palette.")
        box.setInformativeText(how + "\n\nClique sur l'icône pipette près de l'horloge pour l'historique, "
                                     "le format (HEX, RGB, HSL) et la palette d'une image.")
        box.exec()
        self.open_window()


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    probe = QLocalSocket()
    probe.connectToServer(APP_ID)
    if probe.waitForConnected(300):
        probe.disconnectFromServer()
        return 0
    app.setApplicationName("AikoPipette")
    app.setOrganizationName("Aikographic")
    app.setQuitOnLastWindowClosed(False)
    icon = resource("icon-256.png")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    _ = Controller(app)
    return app.exec()
