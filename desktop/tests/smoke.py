"""Test automatique d'AikoPipette (lancé par GitHub Actions)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402
from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPixmap  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from aikopipette import colors, theme  # noqa: E402
from aikopipette.hotkey import IS_WIN, GlobalHotkey, Shortcut  # noqa: E402
from aikopipette.picker import _Overlay  # noqa: E402
from aikopipette.ui import Bubble, PaletteWindow, ShortcutDialog  # noqa: E402

failures: list[str] = []


def check(cond: bool, what: str):
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        failures.append(what)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title=Test::{what}")


class FakeCtl:
    """Contrôleur minimal pour dessiner le panneau."""

    def __init__(self):
        self.history = ["#7DC8FF", "#0A0A0C", "#F08C3C", "#E6E8EC", "#388CE6", "#2E7D32", "#FFD54F", "#C62828",
                        "#6A1B9A", "#00897B"]
        self.palette = ["#7DC8FF", "#0A0A0C", "#F08C3C", "#E6E8EC", "#388CE6"]
        self.palette_source = "affiche.png"
        self.format = "HEX"
        self.flash = None
        self.shortcut = Shortcut()
        self.can_pick = True
        self.autostart = False
        self.copied = []

    def copy(self, hexv, fmt=None):
        self.copied.append(colors.as_text(hexv, fmt or self.format))
        return self.copied[-1]

    def __getattr__(self, name):  # actions non utilisées par le test
        return lambda *a, **k: None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    app = QApplication(sys.argv)
    shots = ROOT / "screenshots"
    shots.mkdir(exist_ok=True)

    print("== formats")
    check(colors.as_text("#7DC8FF", "RGB") == "rgb(125, 200, 255)", "RGB")
    check(colors.as_text("#7DC8FF", "HSL") == "hsl(205, 100%, 75%)", "HSL")
    check(colors.as_text("#7dc8ff", "HEX") == "#7DC8FF", "HEX")

    print("== palette d'une image")
    with tempfile.TemporaryDirectory() as tmp:
        img = Image.new("RGB", (300, 200), (125, 200, 255))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 100, 200], fill=(10, 10, 12))
        d.rectangle([200, 0, 300, 60], fill=(240, 140, 60))
        path = Path(tmp) / "test.png"
        img.save(path)
        pal = colors.extract_palette(path)
        print("  palette :", pal)
        check(pal[:3] == ["#7DC8FF", "#0A0A0C", "#F08C3C"], "couleurs principales dans l'ordre")

    print("== pipette (loupe)")
    src = QImage(400, 300, QImage.Format.Format_RGB32)
    src.fill(QColor("#0A0A0C"))
    p = QPainter(src)
    p.fillRect(200, 0, 200, 300, QColor("#7DC8FF"))
    p.end()
    screen = QGuiApplication.primaryScreen()
    ov = _Overlay(screen, src, 1.0)
    ov.resize(400, 300)
    check(ov.color_at(QPointF(50, 50)) == "#0A0A0C", "couleur à gauche")
    check(ov.color_at(QPointF(300, 50)) == "#7DC8FF", "couleur à droite")
    got = []
    ov.picked.connect(got.append)
    ov.cursor_pos = QPointF(205, 150)
    QTest.mouseClick(ov, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(300, 100))
    check(got == ["#7DC8FF"], "clic = couleur prise")
    pm = QPixmap(400, 300)
    pm.fill(QColor("#888888"))
    p = QPainter(pm)
    ov.cursor_pos = QPointF(198, 120)
    ov._draw_loupe(p, ov.cursor_pos)
    p.end()

    for dark in (True, False):
        theme.is_dark = lambda dark=dark: dark
        suffix = "sombre" if dark else "clair"
        img = QImage(400, 300, QImage.Format.Format_ARGB32)
        img.fill(QColor("#2B2F36") if dark else QColor("#D9DEE5"))
        p = QPainter(img)
        p.drawImage(0, 0, src)
        ov.cursor_pos = QPointF(198, 120)
        ov._draw_loupe(p, ov.cursor_pos)
        p.end()
        img.save(str(shots / f"loupe-{suffix}.png"))

        w = PaletteWindow(FakeCtl())
        w.apply_theme()
        w.refresh()
        w.adjustSize()
        canvas = QPixmap(w.size())
        canvas.fill(QColor("#2B2F36") if dark else QColor("#D9DEE5"))
        p = QPainter(canvas)
        w.render(p, QPoint(0, 0))
        p.end()
        canvas.save(str(shots / f"panneau-{suffix}.png"))
        b = Bubble()
        b.show_color("#7DC8FF", "#7DC8FF", QPoint(300, 300))
        b.grab().save(str(shots / f"bulle-{suffix}.png"))
        b.hide()

    print("== raccourci")
    s = Shortcut(["ctrl", "shift"], 0x50, "P")
    back = Shortcut.loads(s.dumps())
    check((back.mods, back.key, back.key_label) == (s.mods, s.key, s.key_label), "relecture du raccourci")
    check(Shortcut.loads("???").label() == "Alt + C", "raccourci par défaut Alt + C")
    dlg = ShortcutDialog(Shortcut())
    dlg.show()
    QTest.keyPress(dlg, Qt.Key.Key_P, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    print("  enregistré :", dlg.pending.label())
    check(dlg.pending.label() == "Ctrl + Maj + P", "la fenêtre enregistre Ctrl + Maj + P")
    dlg.grab().save(str(shots / "fenetre-raccourci.png"))
    dlg.close()
    if IS_WIN:
        hk = GlobalHotkey()
        ok = hk.register(Shortcut(["ctrl", "alt", "shift"], 0x7B, "F12"))
        check(ok, "raccourci global enregistré auprès de Windows")
        hk.unregister()

    print("\nCaptures :", ", ".join(sorted(p.name for p in shots.glob("*.png"))))
    if failures:
        print("\nÉCHECS :\n" + "\n".join(failures))
        return 1
    print("\nTout est OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback

        tb = traceback.format_exc()
        print(tb)
        if os.environ.get("GITHUB_ACTIONS"):
            print("::error title=Erreur fatale::" + " | ".join(tb.strip().splitlines()[-6:]))
        sys.exit(1)
