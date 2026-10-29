#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FlyArchOs — единая утилита для обоев во всех окружениях.

Обои живут в /usr/share/backgrounds/flyarchos, их список (названия, превью)
— в /usr/share/flyarchos/wallpapers.json.

    flyarchos-wallpaper list
    flyarchos-wallpaper set aurora-nexus
    flyarchos-wallpaper set ~/Pictures/cat.jpg
    flyarchos-wallpaper random
    flyarchos-wallpaper current
    flyarchos-wallpaper set-default nord-fjord     # от root, симлинк default.jpg

В Hyprland картинка ставится через swww (с плавным переходом) и копируется в
~/.cache/flyarchos/current.*, откуда её забирает hyprlock (экран блокировки).
В KDE Plasma используется plasma-apply-wallpaperimage.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

WALLPAPER_DIR = Path(os.environ.get("FLYARCHOS_WALLPAPERS", "/usr/share/backgrounds/flyarchos"))
MANIFEST = Path("/usr/share/flyarchos/wallpapers.json")
DEFAULT_LINK = WALLPAPER_DIR / "default.jpg"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "flyarchos"
CURRENT_LINK = Path.home() / ".config" / "flyarchos" / "current-wallpaper"
LOCK_TEMPLATE = Path("/usr/share/flyarchos/templates/hyprlock.conf")

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")


# --------------------------------------------------------------------------- #
# Список обоев
# --------------------------------------------------------------------------- #
def load_manifest() -> list[dict]:
    """Список обоев из манифеста; если манифеста нет — сканируем каталог."""
    if MANIFEST.is_file():
        try:
            data = json.loads(MANIFEST.read_text(encoding="utf-8"))
            items = data["wallpapers"] if isinstance(data, dict) else data
            return [item for item in items if Path(item["file"]).is_file()]
        except Exception as exc:  # повреждённый манифест не должен ломать утилиту
            print(f"предупреждение: не читается {MANIFEST}: {exc}", file=sys.stderr)
    return scan_dir()


def scan_dir() -> list[dict]:
    """Список обоев прямо по каталогу (fallback)."""
    items = []
    for path in sorted(WALLPAPER_DIR.glob("*")):
        if path.suffix.lower() in IMAGE_SUFFIXES and path.name != "default.jpg":
            items.append({"id": path.stem, "title": pretty_title(path.stem), "file": str(path)})
    return items


def pretty_title(stem: str) -> str:
    """'02-neon-grid' → 'Neon Grid'."""
    name = stem.split("-", 1)[-1] if stem[:2].isdigit() else stem
    return name.replace("-", " ").title()


def find(item: str) -> Path | None:
    """Найти обои по id, названию или пути."""
    candidate = Path(os.path.expanduser(item))
    if candidate.is_file():
        return candidate
    for entry in load_manifest():
        if item.lower() in (entry["id"].lower(), entry.get("title", "").lower()):
            return Path(entry["file"])
    for entry in load_manifest():
        if item.lower() in entry["id"].lower():
            return Path(entry["file"])
    return None


# --------------------------------------------------------------------------- #
# Окружение
# --------------------------------------------------------------------------- #
def detect_session() -> str:
    """Определить текущее окружение: hyprland / plasma / x11 / tty."""
    env = os.environ
    desktop = f"{env.get('XDG_CURRENT_DESKTOP', '')} {env.get('XDG_SESSION_DESKTOP', '')} {env.get('DESKTOP_SESSION', '')}".lower()
    if env.get("HYPRLAND_INSTANCE_SIGNATURE") or "hyprland" in desktop:
        return "hyprland"
    if "plasma" in desktop or "kde" in desktop:
        return "plasma"
    if env.get("WAYLAND_DISPLAY"):
        return "wayland"
    if env.get("DISPLAY"):
        return "x11"
    return "tty"


def _run(cmd: list[str]) -> bool:
    """Запустить команду, вернуть успех."""
    if shutil.which(cmd[0]) is None:
        return False
    return subprocess.run(cmd, check=False, capture_output=True).returncode == 0


def _wallpaper_client() -> str | None:
    """Поднять демон обоев и вернуть имя клиента (awww; старое имя — swww)."""
    import time

    for client, daemon in (("awww", "awww-daemon"), ("swww", "swww-daemon")):
        if shutil.which(client) is None and shutil.which(daemon) is None:
            continue
        if not _run(["pgrep", "-x", daemon]) and shutil.which(daemon):
            subprocess.Popen(
                [daemon], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            time.sleep(0.7)
        return client
    return None


def apply_hyprland(path: Path, transition: str = "wipe") -> bool:
    """Hyprland: awww/swww, при отсутствии — hyprpaper."""
    client = _wallpaper_client()
    if client and _run(
        [client, "img", str(path), "--transition-type", transition, "--transition-fps", "60"]
    ):
        return True
    if shutil.which("hyprctl"):
        return _run(["hyprctl", "hyprpaper", "wallpaper", f",{path}"])
    return False


def apply_plasma(path: Path) -> bool:
    """KDE Plasma: plasma-apply-wallpaperimage."""
    return _run(["plasma-apply-wallpaperimage", str(path)])


def apply_x11(path: Path) -> bool:
    """X11: feh, если установлен."""
    return _run(["feh", "--bg-scale", str(path)])


def apply(path: Path, session: str, transition: str) -> bool:
    if session == "hyprland":
        return apply_hyprland(path, transition)
    if session == "plasma":
        return apply_plasma(path)
    if session == "wayland":
        return apply_hyprland(path, transition)
    if session == "x11":
        return apply_x11(path)
    print("Графическая сессия не обнаружена — путь к обоям просто сохранён.")
    return True


# --------------------------------------------------------------------------- #
# Побочные эффекты: hyprlock, симлинки, состояние
# --------------------------------------------------------------------------- #
def update_lock_screen(path: Path) -> None:
    """Hyprland: переписать hyprlock.conf под текущие обои."""
    config_dir = Path.home() / ".config" / "hypr"
    template = LOCK_TEMPLATE.read_text(encoding="utf-8") if LOCK_TEMPLATE.is_file() else None
    if template is None:
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / f"current{path.suffix.lower()}"
    try:
        shutil.copyfile(path, cached)
    except OSError:
        cached = path
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "hyprlock.conf").write_text(template.replace("{wallpaper}", str(cached)), encoding="utf-8")


def remember(path: Path) -> None:
    """Запомнить текущие обои (симлинк в ~/.config/flyarchos)."""
    CURRENT_LINK.parent.mkdir(parents=True, exist_ok=True)
    if CURRENT_LINK.is_symlink() or CURRENT_LINK.exists():
        CURRENT_LINK.unlink()
    try:
        CURRENT_LINK.symlink_to(path)
    except OSError:
        CURRENT_LINK.write_text(str(path), encoding="utf-8")
    state = Path.home() / ".config" / "flyarchos" / "wallpaper.json"
    state.write_text(json.dumps({"current": str(path)}, ensure_ascii=False, indent=2), encoding="utf-8")


def current() -> str | None:
    """Путь к текущим обоям (если запоминали)."""
    if CURRENT_LINK.is_symlink():
        return str(CURRENT_LINK.resolve())
    if CURRENT_LINK.is_file():
        return CURRENT_LINK.read_text(encoding="utf-8").strip() or None
    state = Path.home() / ".config" / "flyarchos" / "wallpaper.json"
    if state.is_file():
        try:
            return json.loads(state.read_text(encoding="utf-8")).get("current")
        except Exception:
            return None
    return None


# --------------------------------------------------------------------------- #
# Команды
# --------------------------------------------------------------------------- #
def cmd_list(_args) -> int:
    items = load_manifest()
    if not items:
        print(f"обои не найдены в {WALLPAPER_DIR}")
        return 1
    cur = current()
    for entry in items:
        mark = "*" if cur and str(Path(entry["file"]).resolve()) == str(Path(cur).resolve()) else " "
        print(f" {mark} {entry['id']:<20} {entry.get('title', pretty_title(entry['id']))}")
    return 0


def cmd_set(args) -> int:
    if args.target in ("random", "rand", "любой"):
        return cmd_random(args)
    path = find(args.target)
    if path is None:
        print(f"не найдено: {args.target}\nСписок: flyarchos-wallpaper list", file=sys.stderr)
        return 1
    session = detect_session()
    ok = apply(path, session, args.transition)
    if session == "hyprland":
        update_lock_screen(path)
    remember(path)
    print(f"Обои: {path.name} ({session})")
    return 0 if ok else 1


def cmd_random(args) -> int:
    items = load_manifest()
    if not items:
        print(f"обои не найдены в {WALLPAPER_DIR}", file=sys.stderr)
        return 1
    entry = random.choice(items)
    args.target = entry["id"]
    return cmd_set(args)


def cmd_current(_args) -> int:
    path = current()
    print(path if path else "неизвестно")
    return 0 if path else 1


def cmd_set_default(args) -> int:
    """Системные обои по умолчанию (для новых пользователей и GRUB)."""
    path = find(args.target)
    if path is None:
        print(f"не найдено: {args.target}", file=sys.stderr)
        return 1
    if not WALLPAPER_DIR.exists():
        print(f"нет каталога {WALLPAPER_DIR}", file=sys.stderr)
        return 1
    link = WALLPAPER_DIR / f"default{path.suffix.lower()}"
    try:
        tmp = link.with_suffix(".tmp" + link.suffix)
        if tmp.exists():
            tmp.unlink()
        shutil.copyfile(path, tmp)
        tmp.replace(link)
        if link != DEFAULT_LINK:
            # для png/webp держим отдельный указатель default.jpg
            if DEFAULT_LINK.exists() or DEFAULT_LINK.is_symlink():
                DEFAULT_LINK.unlink()
            DEFAULT_LINK.symlink_to(link.name)
    except OSError as exc:
        print(f"не удалось установить обои по умолчанию (нужны права root): {exc}", file=sys.stderr)
        return 1
    print(f"Обои по умолчанию: {link.name}")
    return 0


def cmd_open(_args) -> int:
    """Открыть каталог с обоями в файловом менеджере."""
    opener = shutil.which("xdg-open") or shutil.which("dolphin") or shutil.which("thunar")
    if not opener:
        print("нет xdg-open/dolphin/thunar", file=sys.stderr)
        return 1
    subprocess.Popen([opener, str(WALLPAPER_DIR)], start_new_session=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="flyarchos-wallpaper", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--transition", default="wipe", help="переход swww: wipe/fade/grow/outer/any")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="показать обои").set_defaults(func=cmd_list)
    p_set = sub.add_parser("set", help="установить обои")
    p_set.add_argument("target", help="id обоев, название или путь к файлу")
    p_set.set_defaults(func=cmd_set)
    sub.add_parser("random", help="случайные обои").set_defaults(func=cmd_random)
    sub.add_parser("current", help="текущие обои").set_defaults(func=cmd_current)
    p_def = sub.add_parser("set-default", help="системные обои по умолчанию (root)")
    p_def.add_argument("target")
    p_def.set_defaults(func=cmd_set_default)
    sub.add_parser("open", help="открыть каталог обоев").set_defaults(func=cmd_open)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
