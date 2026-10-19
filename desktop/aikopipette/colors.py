"""Couleurs : formats de copie et palette principale d'une image."""
from __future__ import annotations

import colorsys
from pathlib import Path

FORMATS = ("HEX", "RGB", "HSL")


def hex_of(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


def rgb_of(hex_: str) -> tuple[int, int, int]:
    s = hex_.strip().lstrip("#")
    v = int(s, 16)
    return (v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF


def as_text(hex_: str, fmt: str) -> str:
    r, g, b = rgb_of(hex_)
    if fmt == "RGB":
        return f"rgb({r}, {g}, {b})"
    if fmt == "HSL":
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        return f"hsl({round(h * 360) % 360}, {round(s * 100)}%, {round(l * 100)}%)"
    return hex_of(r, g, b)


def is_light(hex_: str) -> bool:
    r, g, b = rgb_of(hex_)
    return 0.299 * r + 0.587 * g + 0.114 * b > 160


def extract_palette(path: Path, count: int = 6) -> list[str]:
    """Les couleurs principales d'une image, de la plus présente à la moins présente."""
    from PIL import Image, ImageOps

    try:  # HEIC (photos iPhone)
        import pillow_heif

        pillow_heif.register_heif_opener()
    except Exception:
        pass
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        im.thumbnail((128, 128))
        if im.mode in ("RGBA", "LA", "P"):
            rgba = im.convert("RGBA")
            bg = Image.new("RGB", rgba.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.getchannel("A"))
            im = bg
        else:
            im = im.convert("RGB")
    q = im.quantize(colors=count * 2, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette() or []
    counts = sorted(q.getcolors() or [], reverse=True)
    out: list[tuple[int, int, int]] = []
    for _, idx in counts:
        c = tuple(pal[idx * 3: idx * 3 + 3])
        if len(c) < 3:
            continue
        if all(_dist(c, o) > 600 for o in out):
            out.append(c)  # type: ignore[arg-type]
        if len(out) == count:
            break
    return [hex_of(*c) for c in out]


def _dist(a, b) -> float:
    return (a[0] - b[0]) ** 2 * 0.3 + (a[1] - b[1]) ** 2 * 0.59 + (a[2] - b[2]) ** 2 * 0.11
