#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Собрать графику бренда для Calamares (и не только).

Из ``assets/logo-src/logo.png`` и обоев получаются:

* ``profile/airootfs/etc/calamares/branding/flyarchos/logo.png``    — 256x256
* ``.../welcome.png``        — баннер на страницу приветствия
* ``.../wallpaper.png``      — фон окна установщика
* ``.../slide-1..3.jpg``     — картинки для слайд-шоу во время установки
* ``/usr/share/pixmaps/flyarchos.png`` и ``/usr/share/icons/hicolor/...``
* ``assets/favicon.png``     — иконка для документации

Запуск::

    python3 scripts/make-branding.py
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps
except ImportError:
    sys.exit("Нужен Pillow: pip install --user Pillow")

REPO = Path(__file__).resolve().parents[1]
LOGO_SRC = REPO / "assets" / "logo-src" / "logo.png"
WALLPAPERS = REPO / "profile" / "airootfs" / "usr" / "share" / "backgrounds" / "flyarchos"
BRANDING = REPO / "profile" / "airootfs" / "etc" / "calamares" / "branding" / "flyarchos"
PIXMAPS = REPO / "profile" / "airootfs" / "usr" / "share" / "pixmaps"
ICONS = REPO / "profile" / "airootfs" / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

ACCENT = (34, 211, 238)
ACCENT2 = (240, 85, 155)
BG = (16, 18, 28)


def font(path: str, size: int):
    return ImageFont.truetype(path, size) if Path(path).is_file() else ImageFont.load_default()


def load_logo(size: int) -> Image.Image:
    """Логотип нужного размера на тёмном фоне."""
    logo = Image.open(LOGO_SRC).convert("RGBA")
    logo = ImageOps.contain(logo, (size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), BG + (255,))
    canvas.alpha_composite(logo, ((size - logo.width) // 2, (size - logo.height) // 2))
    return canvas


def make_welcome() -> Image.Image:
    """Баннер: логотип + название."""
    w, h = 640, 200
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)
    logo = load_logo(150)
    img.paste(logo.convert("RGB"), (40, (h - 150) // 2))
    title = font(FONT_BOLD, 58)
    subtitle = font(FONT_REG, 20)
    draw.text((220, 62), "FlyArchOs", font=title, fill=(245, 247, 255))
    draw.text((222, 122), "Arch Linux + Hyprland + KDE Plasma", font=subtitle, fill=ACCENT)
    draw.rectangle((220, 108, 220 + 260, 112), fill=ACCENT2)
    return img


def make_wallpaper_bg() -> Image.Image:
    """Фон окна установщика: затемнённые обои."""
    source = WALLPAPERS / "01-aurora-nexus.jpg"
    if not source.is_file():
        return Image.new("RGB", (1920, 1080), BG)
    img = Image.open(source).convert("RGB")
    img = ImageOps.fit(img, (1920, 1080), Image.LANCZOS)
    img = ImageEnhance.Brightness(img).enhance(0.45)
    return ImageEnhance.Color(img).enhance(0.7)


def make_slides() -> list[Image.Image]:
    """Три картинки для слайд-шоу установки."""
    names = ["02-neon-grid.jpg", "01-aurora-nexus.jpg", "06-glass-prism.jpg"]
    out = []
    for name in names:
        path = WALLPAPERS / name
        if path.is_file():
            img = Image.open(path).convert("RGB")
            out.append(ImageOps.fit(img, (960, 540), Image.LANCZOS))
    return out


def main() -> int:
    if not LOGO_SRC.is_file():
        print(f"нет логотипа: {LOGO_SRC}", file=sys.stderr)
        return 1

    BRANDING.mkdir(parents=True, exist_ok=True)
    PIXMAPS.mkdir(parents=True, exist_ok=True)
    ICONS.mkdir(parents=True, exist_ok=True)

    logo = load_logo(256)
    logo.save(BRANDING / "logo.png", "PNG", optimize=True)
    logo.resize((128, 128), Image.LANCZOS).save(BRANDING / "logo-small.png", "PNG", optimize=True)
    logo.save(PIXMAPS / "flyarchos.png", "PNG", optimize=True)
    logo.save(ICONS / "flyarchos.png", "PNG", optimize=True)
    logo.resize((64, 64), Image.LANCZOS).save(REPO / "assets" / "favicon.png", "PNG", optimize=True)

    make_welcome().save(BRANDING / "welcome.png", "PNG", optimize=True)
    make_wallpaper_bg().save(BRANDING / "wallpaper.jpg", "JPEG", quality=82, optimize=True)
    for index, slide in enumerate(make_slides(), start=1):
        slide.save(BRANDING / f"slide-{index}.jpg", "JPEG", quality=84, optimize=True)

    print(f"Брендинг собран в {BRANDING.relative_to(REPO)}:")
    for path in sorted(BRANDING.iterdir()):
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
