#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FlyArchOs — генератор процедурных обоев (без интернета, только Pillow).

    flyarchos-wallpaper-gen --list
    flyarchos-wallpaper-gen --theme aurora --size 2560x1440 --out ~/Pictures/aurora.jpg
    flyarchos-wallpaper-gen --all --out ~/Pictures/flyarchos

Каждая тема детерминирована: при одном и том же --seed получается одна и та
же картинка. Хотите «другой» вариант — меняйте --seed.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
except ImportError:  # pragma: no cover
    sys.exit("Нужен Pillow: sudo pacman -S python-pillow  (или pip install Pillow)")

# --------------------------------------------------------------------------- #
# Палитры тем: (название, описание, цвета)
# --------------------------------------------------------------------------- #
THEMES = {
    "aurora": (
        "Северное сияние",
        "вертикальный градиент ночного неба + мягкие «шторы» сияния",
        ((6, 11, 31), (16, 58, 84), (35, 190, 160), (120, 96, 220)),
    ),
    "nebula": (
        "Туманность",
        "тёмный фон, радиальные свечения и звёзды",
        ((9, 8, 24), (58, 30, 92), (28, 120, 168), (196, 84, 140)),
    ),
    "mesh": (
        "Мesh-градиент",
        "плавный переход четырёх угловых цветов",
        ((18, 22, 48), (12, 116, 140), (86, 44, 140), (232, 130, 96)),
    ),
    "waves": (
        "Волны",
        "слои синусоидальных полос",
        ((8, 14, 30), (22, 84, 116), (64, 176, 176), (244, 214, 168)),
    ),
    "grid": (
        "Сетка",
        "перспективная неоновая сетка у горизонта",
        ((10, 8, 26), (58, 24, 96), (214, 68, 168), (86, 226, 236)),
    ),
    "sunset": (
        "Закат",
        "тёплый горизонт с солнечным диском",
        ((32, 16, 52), (150, 52, 92), (242, 128, 76), (255, 214, 140)),
    ),
    "forest": (
        "Лесная ночь",
        "глубокий зелёно-бирюзовый градиент с туманом",
        ((6, 18, 20), (14, 60, 56), (38, 120, 96), (186, 214, 160)),
    ),
    "mono": (
        "Монохром",
        "строгий серый градиент с диагональными полосами",
        ((12, 12, 14), (56, 58, 64), (128, 130, 136), (226, 228, 232)),
    ),
}

DEFAULT_SIZE = (2560, 1440)
DEFAULT_QUALITY = 88


# --------------------------------------------------------------------------- #
# Вспомогательные функции
# --------------------------------------------------------------------------- #
def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _mix(c1, c2, t: float):
    return tuple(int(round(_lerp(a, b, t))) for a, b in zip(c1, c2))


def _column_gradient(size, stops):
    """Вертикальный градиент: строим узкую картинку и растягиваем."""
    w, h = size
    col = Image.new("RGB", (2, 256))
    px = col.load()
    segments = len(stops) - 1
    for y in range(256):
        t = y / 255 * segments
        i = min(int(t), segments - 1)
        local = t - i
        px[0, y] = px[1, y] = _mix(stops[i], stops[i + 1], local)
    return col.resize((w, h), Image.BICUBIC)


def _radial(size):
    """Радиальный градиент: 255 в центре, 0 по краям (Image.radial_gradient
    в Pillow наоборот — там чёрный в центре, поэтому инвертируем)."""
    return Image.radial_gradient("L").resize(size, Image.BICUBIC).point(lambda v: 255 - v)


def _glow(size, center, radius, color, strength=0.85):
    """Радиальное свечение в виде RGBA-слоя."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    if radius <= 0:
        return layer
    grad = _radial((radius * 2, radius * 2))
    blob = Image.new("RGBA", (radius * 2, radius * 2), tuple(color) + (0,))
    blob.putalpha(grad.point(lambda v: int(v * strength)))
    layer.paste(blob, (int(center[0] - radius), int(center[1] - radius)), blob)
    return layer


def _screen(base: Image.Image, layer: Image.Image) -> Image.Image:
    """Сложить свечение в режиме screen (как свет)."""
    black = Image.new("RGBA", layer.size, (0, 0, 0, 255))
    rgb = Image.alpha_composite(black, layer).convert("RGB")
    return ImageChops.screen(base.convert("RGB"), rgb)


def _vignette(img: Image.Image, amount: float = 0.35) -> Image.Image:
    """Мягкое затемнение по краям."""
    w, h = img.size
    mask = _radial((w, int(h * 1.15)))
    mask = mask.crop((0, (mask.size[1] - h) // 2, w, (mask.size[1] - h) // 2 + h))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(img, dark, mask.point(lambda v: int(255 - amount * (255 - v))))


def _grain(img: Image.Image, sigma: float = 12.0, amount: float = 0.05) -> Image.Image:
    """Немного плёночного зерна, чтобы gradient был «живым»."""
    small = (max(1, img.width // 4), max(1, img.height // 4))
    noise = Image.effect_noise(small, sigma).resize(img.size, Image.BICUBIC).convert("L")
    return Image.blend(img, ImageChops.overlay(img, Image.merge("RGB", (noise, noise, noise))), amount)


# --------------------------------------------------------------------------- #
# Темой-функции
# --------------------------------------------------------------------------- #
def theme_aurora(size, palette, rng):
    img = _column_gradient(size, (palette[0], palette[1], palette[0]))
    w, h = size
    for _ in range(5):
        cx = rng.uniform(0.1, 0.9) * w
        cy = rng.uniform(0.05, 0.55) * h
        radius = rng.uniform(0.25, 0.6) * w
        color = _mix(palette[2], palette[3], rng.random())
        img = _screen(img, _glow(size, (cx, cy), int(radius), color, rng.uniform(0.55, 0.9)))
    img = _vignette(img, 0.45)
    return _grain(img, 10, 0.04)


def theme_nebula(size, palette, rng):
    img = _column_gradient(size, (palette[0], palette[1], palette[0]))
    w, h = size
    for _ in range(7):
        cx, cy = rng.uniform(0, 1) * w, rng.uniform(0, 1) * h
        radius = rng.uniform(0.12, 0.45) * w
        color = _mix(palette[1], palette[3], rng.random())
        img = _screen(img, _glow(size, (cx, cy), int(radius), color, rng.uniform(0.4, 0.75)))
    stars = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(stars)
    for _ in range(420):
        x, y = rng.uniform(0, 1) * w, rng.uniform(0, 1) * h
        r = rng.choice([1, 1, 1, 2])
        a = rng.randint(90, 230)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, a))
    img = Image.alpha_composite(img.convert("RGBA"), stars).convert("RGB")
    return _vignette(img, 0.4)


def theme_mesh(size, palette, rng):
    w, h = size
    small = Image.new("RGB", (3, 3))
    small.putpixel((0, 0), palette[0])
    small.putpixel((2, 0), palette[1])
    small.putpixel((0, 2), palette[2])
    small.putpixel((2, 2), palette[3])
    small.putpixel((1, 0), _mix(palette[0], palette[1], 0.5))
    small.putpixel((0, 1), _mix(palette[0], palette[2], 0.5))
    small.putpixel((2, 1), _mix(palette[1], palette[3], 0.5))
    small.putpixel((1, 2), _mix(palette[2], palette[3], 0.5))
    small.putpixel((1, 1), _mix(_mix(palette[0], palette[3], 0.5), _mix(palette[1], palette[2], 0.5), 0.5))
    img = small.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(radius=8))
    for _ in range(3):
        img = _screen(img, _glow(size, (rng.uniform(0, 1) * w, rng.uniform(0, 1) * h),
                                 int(rng.uniform(0.1, 0.3) * w), palette[3], 0.3))
    return _grain(img, 8, 0.05)


def theme_waves(size, palette, rng):
    img = _column_gradient(size, (palette[0], palette[1], palette[2]))
    w, h = size
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for band in range(7):
        base_y = h * (0.45 + band * 0.09)
        amp = rng.uniform(0.02, 0.07) * h
        freq = rng.uniform(1.2, 2.6)
        phase = rng.uniform(0, math.tau)
        color = _mix(palette[2], palette[3], band / 6)
        alpha = int(90 - band * 8)
        points = []
        for x in range(0, w + 8, 8):
            y = base_y + amp * math.sin(freq * math.tau * x / w + phase)
            points.append((x, y))
        for (x, y) in points:
            d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=tuple(color) + (alpha,))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    img = img.filter(ImageFilter.GaussianBlur(radius=1.5))
    return _vignette(img, 0.35)


def theme_grid(size, palette, rng):
    w, h = size
    img = _column_gradient(size, (palette[0], palette[1], palette[0]))
    horizon = h * 0.58
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    # горизонтальные линии, сгущающиеся к горизонту
    for i in range(1, 26):
        t = i / 26
        y = horizon + (h - horizon) * (t ** 2.2)
        alpha = int(150 * (1 - t * 0.75))
        d.line((0, y, w, y), fill=tuple(palette[3]) + (alpha,), width=1)
    # вертикальные линии, сходящиеся в точке схода
    cx = w / 2
    for i in range(-22, 23):
        x_bottom = cx + i * (w / 16)
        d.line((cx + i * 3, horizon, x_bottom, h), fill=tuple(palette[2]) + (110,), width=1)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    img = _screen(img, _glow(size, (cx, horizon), int(w * 0.35), palette[2], 0.45))
    img = img.filter(ImageFilter.GaussianBlur(radius=0.8))
    return _vignette(img, 0.5)


def theme_sunset(size, palette, rng):
    w, h = size
    img = _column_gradient(size, (palette[0], palette[1], palette[2], palette[3]))
    sun = (w * rng.uniform(0.35, 0.65), h * 0.62)
    img = _screen(img, _glow(size, sun, int(w * 0.28), palette[3], 0.9))
    img = _screen(img, _glow(size, sun, int(w * 0.12), (255, 250, 220), 0.95))
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(5):
        y = h * (0.64 + i * 0.08)
        d.rectangle((0, y, w, y + h * 0.012), fill=tuple(palette[0]) + (60,))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    return _vignette(img, 0.35)


def theme_forest(size, palette, rng):
    w, h = size
    img = _column_gradient(size, (palette[0], palette[1], palette[2]))
    for _ in range(4):
        img = _screen(img, _glow(size, (rng.uniform(0, 1) * w, rng.uniform(0.1, 0.9) * h),
                                 int(rng.uniform(0.2, 0.5) * w), palette[2], 0.3))
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(6):
        y = h * (0.4 + i * 0.1)
        d.ellipse((-w * 0.2, y - h * 0.06, w * 1.2, y + h * 0.12), fill=tuple(palette[3]) + (26,))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    return _vignette(img, 0.5)


def theme_mono(size, palette, rng):
    w, h = size
    img = _column_gradient(size, (palette[0], palette[2], palette[3]))
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    step = max(12, w // 90)
    for x in range(-h, w + h, step * 3):
        d.line((x, 0, x + h, h), fill=(255, 255, 255, 12), width=max(2, step // 4))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    return _vignette(img, 0.3)


GENERATORS = {
    "aurora": theme_aurora,
    "nebula": theme_nebula,
    "mesh": theme_mesh,
    "waves": theme_waves,
    "grid": theme_grid,
    "sunset": theme_sunset,
    "forest": theme_forest,
    "mono": theme_mono,
}


def generate(theme: str, size=DEFAULT_SIZE, seed: int = 0) -> Image.Image:
    """Сгенерировать обои указанной темы."""
    if theme not in GENERATORS:
        raise SystemExit(f"неизвестная тема: {theme} (доступны: {', '.join(THEMES)})")
    palette = THEMES[theme][2]
    rng = random.Random(f"{theme}:{seed}")
    return GENERATORS[theme](size, palette, rng)


def parse_size(value: str):
    try:
        w, h = (int(part) for part in value.lower().replace("*", "x").split("x"))
        return (w, h)
    except Exception:
        raise SystemExit(f"не понял размер: {value} (нужно например 2560x1440)")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="flyarchos-wallpaper-gen",
        description="Генератор процедурных обоев FlyArchOs",
    )
    parser.add_argument("--list", action="store_true", help="показать темы и выйти")
    parser.add_argument("--theme", help="тема (см. --list)")
    parser.add_argument("--all", action="store_true", help="сгенерировать все темы")
    parser.add_argument("--size", default="2560x1440")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("-o", "--out", help="файл .jpg/.png или каталог (для --all)")
    parser.add_argument("--quality", type=int, default=DEFAULT_QUALITY)
    args = parser.parse_args(argv)

    if args.list or not (args.theme or args.all):
        print("Доступные темы обоев:\n")
        for name, (title, desc, _) in THEMES.items():
            print(f"  {name:<8} {title:<18} {desc}")
        print("\nПример: flyarchos-wallpaper-gen --theme aurora --seed 2 -o ~/Pictures/aurora.jpg")
        return 0

    size = parse_size(args.size)
    themes = list(THEMES) if args.all else [args.theme]
    out = Path(args.out or ".")
    if len(themes) > 1:
        out.mkdir(parents=True, exist_ok=True)

    for theme in themes:
        img = generate(theme, size, args.seed)
        target = out / f"{theme}.jpg" if len(themes) > 1 else (out if out.suffix else out / f"{theme}.jpg")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix.lower() in (".png",):
            img.save(target, "PNG", optimize=True)
        else:
            img.save(target, "JPEG", quality=args.quality, optimize=True, progressive=True)
        print(f"{target}  ({img.width}x{img.height}, тема: {theme})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
