"""Raccourci clavier global, sans capturer le clavier.

Windows : RegisterHotKey (le système ne nous prévient que pour CE raccourci).
Linux X11 : XGrabKey sur la fenêtre racine. Wayland : non disponible.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal

IS_WIN = sys.platform == "win32"
IS_WAYLAND = sys.platform.startswith("linux") and (
    os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))
)

MOD_ORDER = ("ctrl", "alt", "shift", "meta")
MOD_LABELS = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Maj", "meta": "Win" if IS_WIN else "Super"}


@dataclass
class Shortcut:
    mods: list[str] = field(default_factory=lambda: ["alt"])
    key: int = 0x43 if IS_WIN else 0x63   # « C » : touche virtuelle (Windows) ou keysym (Linux)
    key_label: str = "C"

    def label(self) -> str:
        return " + ".join([MOD_LABELS[m] for m in MOD_ORDER if m in self.mods] + [self.key_label])

    def dumps(self) -> str:
        return json.dumps({"mods": self.mods, "key": self.key, "key_label": self.key_label})

    @classmethod
    def loads(cls, raw: str | None) -> "Shortcut":
        try:
            d = json.loads(raw or "")
            return cls([m for m in d["mods"] if m in MOD_ORDER], int(d["key"]), str(d["key_label"]))
        except Exception:
            return cls()


class GlobalHotkey(QObject):
    pressed = Signal()

    def __init__(self):
        super().__init__()
        self.available = not IS_WAYLAND
        self._registered = False
        self._filter = None
        self._thread: _XGrab | None = None

    def register(self, sc: Shortcut) -> bool:
        self.unregister()
        if IS_WIN:
            return self._register_win(sc)
        if not IS_WAYLAND:
            self._thread = _XGrab(sc, self.pressed.emit)
            self._thread.start()
            self._registered = True
            return True
        return False

    def unregister(self):
        if IS_WIN and self._registered:
            import ctypes

            ctypes.windll.user32.UnregisterHotKey(None, _HOTKEY_ID)
        if self._thread:
            self._thread.stop()
            self._thread = None
        self._registered = False

    # ------------------------------------------------------------ Windows

    def _register_win(self, sc: Shortcut) -> bool:
        import ctypes

        mods = 0x4000  # MOD_NOREPEAT
        for m, bit in (("alt", 0x1), ("ctrl", 0x2), ("shift", 0x4), ("meta", 0x8)):
            if m in sc.mods:
                mods |= bit
        ok = bool(ctypes.windll.user32.RegisterHotKey(None, _HOTKEY_ID, mods, int(sc.key)))
        if self._filter is None:
            self._filter = _WinFilter(self.pressed.emit)
            QCoreApplication.instance().installNativeEventFilter(self._filter)
        self._registered = ok
        return ok


_HOTKEY_ID = 0xA1C0


class _WinFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, event_type, message):
        try:
            kind = event_type.data() if hasattr(event_type, "data") else bytes(event_type)
            if kind in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
                from ctypes import wintypes

                msg = wintypes.MSG.from_address(int(message))
                if msg.message == 0x0312 and msg.wParam == _HOTKEY_ID:  # WM_HOTKEY
                    self.callback()
                    return True, 0
        except Exception:
            pass
        return False, 0


class _XGrab(threading.Thread):
    """Écoute le raccourci sur X11 (fenêtre racine), dans son propre fil."""

    def __init__(self, sc: Shortcut, callback):
        super().__init__(daemon=True)
        self.sc = sc
        self.callback = callback
        self._halt = threading.Event()

    def stop(self):
        self._halt.set()

    def run(self):
        try:
            from Xlib import X, display

            d = display.Display()
            root = d.screen().root
            code = d.keysym_to_keycode(int(self.sc.key))
            mods = 0
            for m, mask in (("shift", X.ShiftMask), ("ctrl", X.ControlMask), ("alt", X.Mod1Mask),
                            ("meta", X.Mod4Mask)):
                if m in self.sc.mods:
                    mods |= mask
            extras = (0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask)  # Verr. Maj / Verr. Num
            for extra in extras:
                root.grab_key(code, mods | extra, True, X.GrabModeAsync, X.GrabModeAsync, onerror=lambda *a: None)
            d.sync()
            while not self._halt.is_set():
                while d.pending_events():
                    ev = d.next_event()
                    if ev.type == X.KeyPress:
                        self.callback()
                time.sleep(0.03)
            for extra in extras:
                root.ungrab_key(code, mods | extra)
            d.close()
        except Exception:
            pass
