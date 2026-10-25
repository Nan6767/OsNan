#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Собрать все обои FlyArchOs из исходников.

Что делает:

1. AI-картинки из ``assets/wallpapers-src`` масштабируются до 1920x1080 и
   сохраняются в JPEG (экономим место в ISO).
2. Процедурные обои генерируются на месте (алгоритм — тот же, что и в
   установленной системе: ``wallpapers.py``), уже в 2560x1440.
3. Для KDE Plasma собираются KPackage-пакеты обоев
   ``/usr/share/wallpapers/FlyArchOs-<name>/`` — так картинки видны в
   «Параметры системы → Внешний вид» по отдельности.
4. Создаются превью, фон для GRUB, ``default.jpg`` и манифест
   ``/usr/share/flyarchos/wallpapers.json``.
5. В ``docs/preview.png`` сохраняется контактный лист — его удобно смотреть.

Запуск::

    python3 scripts/pack-wallpapers.py            # всё
    python3 scripts/pack-wallpapers.py --only ai  # только AI-картинки
    python3 scripts/pack-wallpapers.py --preview-only
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:
    sys.exit("Нужен Pillow: pip install --user Pillow")

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "assets" / "wallpapers-src"
OUT = REPO / "profile" / "airootfs" / "usr" / "share" / "backgrounds" / "flyarchos"
THUMBS = OUT / "thumbs"
KDE = REPO / "profile" / "airootfs" / "usr" / "share" / "wallpapers"
FLYARCHOS_DIR = REPO / "profile" / "airootfs" / "usr" / "share" / "flyarchos"
MANIFEST = FLYARCHOS_DIR / "wallpapers.json"
PREVIEW = REPO / "docs" / "preview.png"

LICENSE = "CC0-1.0"
AUTHOR = "FlyArchOs"

# id, название, русское название, источник
CATALOG: list[tuple[str, str, str, tuple]] = [
    ("01-aurora-nexus", "Aurora Nexus", "Северное сияние", ("asset", "01-aurora-nexus.jpg")),
    ("02-neon-grid", "Neon Grid", "Неоновая сетка", ("asset", "02-neon-grid.jpg")),
    ("03-mountain-dawn", "Mountain Dawn", "Рассвет в горах", ("asset", "03-mountain-dawn.jpg")),
    ("04-ink-bloom", "Ink Bloom", "Чернила и золото", ("asset", "04-ink-bloom.jpg")),
    ("05-nord-fjord", "Nord Fjord", "Северный фьорд", ("asset", "05-nord-fjord.jpg")),
    ("06-glass-prism", "Glass Prism", "Стеклянная призма", ("asset", "06-glass-prism.jpg")),
    ("07-aurora-flow", "Aurora Flow", "Поток сияния", ("theme", "aurora", 7)),
    ("08-nebula", "Nebula", "Туманность", ("theme", "nebula", 3)),
    ("09-mesh-dawn", "Mesh Dawn", "Мягкий градиент", ("theme", "mesh", 11)),
    ("10-deep-wave", "Deep Wave", "Глубокие волны", ("theme", "waves", 5)),
    ("11-sunset-line", "Sunset Line", "Линия заката", ("theme", "sunset", 2)),
    ("12-mono-slate", "Mono Slate", "Монохром", ("theme", "mono", 4)),
]

AI_SIZE = (1920, 1080)
GEN_SIZE = (2560, 1440)
THUMB_SIZE = (400, 225)
JPEG_QUALITY = 86


def load_generator():
    """Импортировать wallpapers.py из дерева профиля (одна реализация — везде)."""
    path = REPO / "profile" / "airootfs" / "usr" / "lib" / "flyarchos" / "wallpapers.py"
    spec = importlib.util.spec_from_file_location("flyarchos_wallpapers", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def kde_title(name: str) -> str:
    """'aurora-nexus' → 'AuroraNexus' (для Id пакета)."""
    return "".join(part.capitalize() for part in name.split("-"))


def make_kde_package(ident: str, title: str, image: Path, size: tuple[int, int]) -> None:
    """Создать KPackage с обоями для KDE Plasma (в Plasma 5 и 6)."""
    package_id = f"FlyArchOs-{kde_title(ident.split('-', 1)[-1])}"
    target = KDE / package_id
    images = target / "contents" / "images"
    if target.exists():
        shutil.rmtree(target)
    images.mkdir(parents=True)

    destination = images / f"{size[0]}x{size[1]}.jpg"
    shutil.copyfile(image, destination)

    screenshot = Image.open(image)
    screenshot.thumbnail((640, 360), Image.LANCZOS)
    screenshot.save(target / "contents" / "screenshot.jpg", "JPEG", quality=82)

    (target / "metadata.json").write_text(
        json.dumps(
            {
                "KPlugin": {
                    "Authors": [{"Name": AUTHOR}],
                    "Category": "Wallpapers",
                    "Description": f"FlyArchOs wallpaper «{title}»",
                    "Id": package_id,
                    "License": LICENSE,
                    "Name": title,
                },
                "X-KPackage-Type": "Wallpaper/Images",
            },
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )
    (target / "metadata.desktop").write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                f"Name={title}",
                "Comment=Обои FlyArchOs",
                "Type=Service",
                "ServiceTypes=Plasma/Wallpaper",
                f"X-KDE-PluginInfo-Author={AUTHOR}",
                f"X-KDE-PluginInfo-Name={package_id}",
                f"X-KDE-PluginInfo-License={LICENSE}",
                "X-KDE-PluginInfo-Category=Wallpapers",
                "",
            ]
        ),
        encoding="utf-8",
    )


def make_preview(entries: list[dict]) -> None:
    """Контактный лист всех обоев для документации."""
    if not entries:
        return
    cell = (320, 180)
    cols = 3
    rows = (len(entries) + cols - 1) // cols
    pad = 10
    sheet = Image.new("RGB", (cols * cell[0] + pad * (cols + 1),
                              rows * (cell[1] + 26) + pad * (rows + 1)), (14, 16, 26))
    draw = ImageDraw.Draw(sheet)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font = ImageFont.truetype(font_path, 14) if Path(font_path).is_file() else ImageFont.load_default()
    for index, entry in enumerate(entries):
        row, col = divmod(index, cols)
        x = pad + col * (cell[0] + pad)
        y = pad + row * (cell[1] + 26 + pad)
        thumb_path = Path(entry["thumb"])
        if not thumb_path.is_file():  # в манифесте пути «на установленную систему»
            thumb_path = OUT / "thumbs" / thumb_path.name
        thumb = ImageOps.fit(Image.open(thumb_path), cell, Image.LANCZOS)
        sheet.paste(thumb, (x, y))
        draw.text((x + 4, y + cell[1] + 4), f"{entry['id']} — {entry['title_ru']}", fill=(200, 210, 235), font=font)
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(PREVIEW, "PNG", optimize=True)
    print(f"{PREVIEW.relative_to(REPO)}: контактный лист ({sheet.width}x{sheet.height})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", choices=["ai", "generated"], help="обрабатывать только часть")
    parser.add_argument("--preview-only", action="store_true", help="только пересобрать контактный лист")
    parser.add_argument("--clean", action="store_true", help="перед сборкой очистить каталоги")
    args = parser.parse_args()

    if args.clean:
        for directory in (OUT, KDE):
            if directory.exists():
                shutil.rmtree(directory)

    OUT.mkdir(parents=True, exist_ok=True)
    THUMBS.mkdir(parents=True, exist_ok=True)
    KDE.mkdir(parents=True, exist_ok=True)
    FLYARCHOS_DIR.mkdir(parents=True, exist_ok=True)

    generator = load_generator()
    entries: list[dict] = []

    if not args.preview_only:
        for ident, title, title_ru, source in CATALOG:
            if source[0] == "asset":
                if args.only == "generated":
                    continue
                src = SRC / source[1]
                if not src.is_file():
                    print(f"  ! пропуск {ident}: нет {src}")
                    continue
                image = Image.open(src).convert("RGB")
                image = ImageOps.fit(image, AI_SIZE, Image.LANCZOS)
                kind = "ai"
            else:
                if args.only == "ai":
                    continue
                image = generator.generate(source[1], GEN_SIZE, seed=source[2])
                kind = "generated"

            target = OUT / f"{ident}.jpg"
            image.save(target, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)

            thumb = image.copy()
            thumb.thumbnail(THUMB_SIZE, Image.LANCZOS)
            thumb_path = THUMBS / f"{ident}.jpg"
            thumb.save(thumb_path, "JPEG", quality=80, optimize=True)

            make_kde_package(ident, title, target, image.size)

            entries.append(
                {
                    "id": ident,
                    "title": title,
                    "title_ru": title_ru,
                    "kind": kind,
                    "file": f"/usr/share/backgrounds/flyarchos/{ident}.jpg",
                    "thumb": f"/usr/share/backgrounds/flyarchos/thumbs/{ident}.jpg",
                    "size": f"{image.width}x{image.height}",
                }
            )
            print(f"  {ident:<18} {image.width}x{image.height}  {kind}")

        if entries:
            MANIFEST.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "wallpaper_dir": "/usr/share/backgrounds/flyarchos",
                        "default": "01-aurora-nexus",
                        "wallpapers": entries,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            print(f"  манифест: {MANIFEST.relative_to(REPO)} ({len(entries)} обоев)")

            # Обои по умолчанию и фон GRUB
            default_src = OUT / "01-aurora-nexus.jpg"
            if default_src.is_file():
                shutil.copyfile(default_src, OUT / "default.jpg")
            grub = Image.open(default_src)
            grub = ImageOps.fit(grub, (1920, 1080), Image.LANCZOS).point(lambda v: int(v * 0.55))
            grub.save(OUT / "grub.png", "PNG", optimize=True)
            print("  default.jpg + grub.png готовы")
    else:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        entries = data["wallpapers"]

    make_preview(entries)
    total = sum((OUT / f"{e['id']}.jpg").stat().st_size for e in entries if (OUT / f"{e['id']}.jpg").exists())
    print(f"\nИтого: {len(entries)} обоев, {total / 1024 / 1024:.1f} МБ в {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
