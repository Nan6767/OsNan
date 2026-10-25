#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FlyArchOs — инструмент профилирования пакетов.

ISO собирается «жирным»: все окружения и все наборы ПО уже стоят в
live-системе. Установка — это распаковка squashfs на диск, а выбор
пользователя в Calamares превращается в **удаление лишнего**:

    flyarchos-profile --apply --desktop=hyprland --extras=gaming,media

что означает «оставить Hyprland (без Plasma), игры и мультимедиа,
выкинуть остальные наборы и live-пакеты».

Ключи Calamares (global storage) подставляются прямо в командную строку:

    flyarchos-profile --apply --desktop=${gs[packagechooser_desktop]}
                              --extras=${gs[packagechooser_extras]}

Без ``--apply`` ничего не меняется: печатается план (dry-run).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set

# --------------------------------------------------------------------------- #
# Константы
# --------------------------------------------------------------------------- #
GROUPS_DIR = Path(os.environ.get("FLYARCHOS_GROUPS_DIR", "/usr/share/flyarchos/groups"))
STATE_DIR = Path(os.environ.get("FLYARCHOS_STATE_DIR", "/etc/flyarchos"))
STATE_FILE = STATE_DIR / "profile.json"
LOG_FILE = Path("/var/log/flyarchos/profile.log")

# Группы, которые всегда остаются в системе.
MANDATORY_GROUPS: tuple[str, ...] = ("core", "common", "apps")
# Рабочие окружения (взаимоисключающие опции установщика).
DESKTOP_GROUPS: tuple[str, ...] = ("hyprland", "plasma")
# Дополнительные наборы ПО.
EXTRA_GROUPS: tuple[str, ...] = ("dev", "gaming", "media", "office")
# Пакеты только для live-образа.
LIVE_GROUP = "live"
# Порядок удаления: сначала «допы», затем окружения, в конце — live.
REMOVAL_ORDER: tuple[str, ...] = LIVE_GROUP, "office", "media", "gaming", "dev", "plasma", "hyprland"

GROUP_TITLES = {
    "core": "Базовая система",
    "common": "Общее для окружений",
    "hyprland": "Hyprland",
    "plasma": "KDE Plasma",
    "apps": "Повседневные приложения",
    "dev": "Разработка",
    "gaming": "Игры",
    "media": "Мультимедиа",
    "office": "Офис",
    "live": "Только для live-образа",
}

LOG = logging.getLogger("flyarchos-profile")


class ProfileError(RuntimeError):
    """Ошибка в описании групп или в вызове."""


# --------------------------------------------------------------------------- #
# Чтение групп
# --------------------------------------------------------------------------- #
def parse_packages(path: Path) -> List[str]:
    """Прочитать список пакетов из файла группы (без комментариев)."""
    packages: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            packages.extend(line.split())
    return packages


def load_groups(groups_dir: Path = GROUPS_DIR) -> Dict[str, List[str]]:
    """Загрузить все файлы ``NN-имя.txt`` из каталога групп."""
    if not groups_dir.is_dir():
        raise ProfileError(f"нет каталога с описанием групп: {groups_dir}")
    groups: Dict[str, List[str]] = {}
    # только файлы вида NN-имя.txt; aur.txt отдельно (это не группа установщика)
    for path in sorted(groups_dir.glob("[0-9][0-9]-*.txt")):
        name = path.stem.split("-", 1)[1]
        groups[name] = parse_packages(path)
    if not groups:
        raise ProfileError(f"в {groups_dir} не найдено файлов групп (*.txt)")
    return groups


# --------------------------------------------------------------------------- #
# Разбор выбора пользователя
# --------------------------------------------------------------------------- #
def normalize_desktop(value: str | None) -> str:
    """Привести выбор окружения к одному из ``hyprland``/``plasma``/``both``."""
    raw = (value or "").strip().lower()
    if not raw:
        return "both"
    if raw in ("both", "all", "hyprland,plasma", "plasma,hyprland"):
        return "both"
    picked = [part for part in raw.replace(";", ",").split(",") if part.strip()]
    unknown = [p for p in picked if p not in DESKTOP_GROUPS]
    if unknown:
        raise ProfileError(f"неизвестное окружение: {', '.join(unknown)}")
    if not picked:
        return "both"
    if len(picked) == 2:
        return "both"
    return picked[0]


def normalize_extras(value: str | None) -> List[str]:
    """Привести список наборов ПО к списку известных id."""
    raw = (value or "").strip().lower()
    if not raw:
        return []
    picked: List[str] = []
    for part in raw.replace(";", ",").replace(" ", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if part not in EXTRA_GROUPS:
            raise ProfileError(f"неизвестный набор ПО: {part}")
        if part not in picked:
            picked.append(part)
    return picked


def kept_groups(desktop: str, extras: Sequence[str], remove_live: bool) -> List[str]:
    """Список групп, которые должны остаться в системе."""
    kept = list(MANDATORY_GROUPS)
    if desktop in ("hyprland", "both"):
        kept.append("hyprland")
    if desktop in ("plasma", "both"):
        kept.append("plasma")
    kept.extend(extras)
    if not remove_live:
        kept.append(LIVE_GROUP)
    # сохраняем порядок и уникальность
    seen: Set[str] = set()
    result = []
    for name in kept:
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def removed_groups(groups: Dict[str, List[str]], kept: Iterable[str]) -> List[str]:
    """Группы, подлежащие удалению, в порядке REMOVAL_ORDER."""
    keep = set(kept)
    ordered = [g for g in REMOVAL_ORDER if g in groups and g not in keep]
    # на случай групп, которых нет в REMOVAL_ORDER
    ordered += [g for g in sorted(groups) if g not in keep and g not in ordered]
    return ordered


def packages_to_remove(
    groups: Dict[str, List[str]],
    kept: Iterable[str],
) -> Dict[str, List[str]]:
    """Для каждой удаляемой группы — список её пакетов (минус нужные другим)."""
    keep: Set[str] = set()
    for name in kept:
        keep.update(groups.get(name, ()))
    result: Dict[str, List[str]] = {}
    for group in removed_groups(groups, kept):
        seen: Set[str] = set()
        pkgs = []
        for pkg in groups.get(group, ()):
            if pkg in keep or pkg in seen:
                continue
            seen.add(pkg)
            pkgs.append(pkg)
        if pkgs:
            result[group] = pkgs
    return result


# --------------------------------------------------------------------------- #
# Работа с pacman
# --------------------------------------------------------------------------- #
def installed_packages() -> Set[str]:
    """Множество установленных пакетов (``pacman -Qq``)."""
    if shutil.which("pacman") is None:
        LOG.warning("pacman не найден — считаем, что ничего не установлено")
        return set()
    out = subprocess.run(
        ["pacman", "-Qq"], capture_output=True, text=True, check=False
    ).stdout
    return {line.strip() for line in out.splitlines() if line.strip()}


def run_pacman(args: Sequence[str], dry_run: bool = False) -> int:
    """Выполнить (или только показать) команду pacman."""
    cmd = ["pacman"] + list(args)
    line = " ".join(cmd)
    LOG.info(line)
    if dry_run:
        print(f"  [dry-run] {line}")
        return 0
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        LOG.warning("команда завершилась с кодом %d: %s", proc.returncode, line)
    return proc.returncode


def chunked(items: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def remove_packages(packages: Sequence[str], dry_run: bool = False, chunk_size: int = 120) -> int:
    """Удалить пакеты (``pacman -Rns``), не прерываясь на ошибках."""
    failures = 0
    for chunk in chunked(packages, chunk_size):
        failures += 1 if run_pacman(["-Rns", "--noconfirm", "--noprogressbar", *chunk], dry_run) else 0
    if failures:
        LOG.warning("некоторые пакеты не удалось удалить — пробуем по одному")
        for pkg in packages:
            run_pacman(["-Rns", "--noconfirm", "--noprogressbar", pkg], dry_run)
    return failures


def remove_orphans(dry_run: bool = False) -> None:
    """Удалить осиротевшие зависимости."""
    if shutil.which("pacman") is None:
        return
    orphans = subprocess.run(["pacman", "-Qdtq"], capture_output=True, text=True, check=False)
    pkgs = [p.strip() for p in orphans.stdout.splitlines() if p.strip()]
    if pkgs:
        LOG.info("осиротевшие пакеты: %s", " ".join(pkgs))
        remove_packages(pkgs, dry_run)


def install_missing(groups: Dict[str, List[str]], kept: Iterable[str], dry_run: bool = False) -> None:
    """Доставить пакеты выбранных групп, если они отсутствуют (нужна сеть/репо)."""
    wanted: List[str] = []
    seen: Set[str] = set()
    for name in kept:
        for pkg in groups.get(name, ()):
            if pkg not in seen:
                seen.add(pkg)
                wanted.append(pkg)
    have = installed_packages()
    missing = [p for p in wanted if p not in have]
    if not missing:
        LOG.info("все пакеты выбранных групп уже установлены")
        return
    LOG.info("не хватает %d пакетов — ставим", len(missing))
    run_pacman(["-S", "--needed", "--noconfirm", "--noprogressbar", *missing], dry_run)


# --------------------------------------------------------------------------- #
# Состояние
# --------------------------------------------------------------------------- #
def write_state(payload: dict, dry_run: bool = False) -> None:
    """Сохранить выбор в /etc/flyarchos/profile.json (читает install-finalize.sh)."""
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if dry_run:
        print("  [dry-run] было бы записано в " f"{STATE_FILE}:\n{text}")
        return
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(STATE_FILE)
    except OSError as exc:  # не роняем установку из-за файла состояния
        LOG.warning("не удалось записать %s: %s", STATE_FILE, exc)


def setup_logging(verbose: bool = True) -> None:
    LOG.setLevel(logging.DEBUG if verbose else logging.INFO)
    LOG.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(fmt)
    LOG.addHandler(stream)
    if os.access(LOG_FILE.parent, os.W_OK) if LOG_FILE.parent.exists() else False:
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            LOG.addHandler(logging.FileHandler(LOG_FILE, encoding="utf-8"))
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# Команды
# --------------------------------------------------------------------------- #
def cmd_list(groups: Dict[str, List[str]]) -> int:
    width = max(len(name) for name in groups)
    for name, pkgs in sorted(groups.items(), key=lambda kv: kv[0]):
        mark = "обяз." if name in MANDATORY_GROUPS else "опция"
        print(f"{name:<{width}}  {len(pkgs):>4} пак.  {mark:<5}  {GROUP_TITLES.get(name, '')}")
    return 0


def cmd_show(args, groups: Dict[str, List[str]]) -> int:
    desktop = normalize_desktop(args.desktop)
    extras = normalize_extras(args.extras)
    kept = kept_groups(desktop, extras, not args.keep_live)
    plan = packages_to_remove(groups, kept)
    print(f"Окружение:      {desktop}")
    print(f"Наборы ПО:      {', '.join(extras) or '—'}")
    print(f"Остаётся групп: {', '.join(kept)}")
    print(f"Удаляемые группы: {', '.join(plan) or '—'}")
    total = 0
    for group, pkgs in plan.items():
        total += len(pkgs)
        print(f"\n[{group}] {len(pkgs)} пакетов:")
        print("  " + " ".join(pkgs))
    print(f"\nИтого к удалению: {total}")
    return 0


def cmd_apply(args, groups: Dict[str, List[str]]) -> int:
    desktop = normalize_desktop(args.desktop)
    extras = normalize_extras(args.extras)
    dry = not args.apply
    kept = kept_groups(desktop, extras, not args.keep_live)
    plan = packages_to_remove(groups, kept)

    print("=" * 68)
    print(f"FlyArchOs: применяем профиль (окружение: {desktop}, наборы: {', '.join(extras) or '—'})")
    print(f"Режим: {'ПРИМЕНИТЬ' if args.apply else 'ПРОСМОТР (dry-run)'}")
    print("=" * 68)

    if args.install_missing:
        install_missing(groups, kept, dry)

    have = installed_packages()
    removed_all: List[str] = []
    for group, pkgs in plan.items():
        present = [p for p in pkgs if p in have] if have else list(pkgs)
        if not present:
            LOG.info("группа %s: нечего удалять", group)
            continue
        skipped = [p for p in pkgs if p not in present]
        if skipped:
            LOG.info("группа %s: не установлены %s", group, " ".join(skipped))
        LOG.info("группа %s: удаляем %d пакетов", group, len(present))
        remove_packages(present, dry)
        removed_all.extend(present)

    if args.clean_orphans:
        remove_orphans(dry)

    write_state(
        {
            "desktop": desktop,
            "extras": extras,
            "groups_kept": kept,
            "groups_removed": sorted(plan),
            "packages_removed": removed_all,
            "remove_live": not args.keep_live,
            "timestamp": int(time.time()),
            "version": 1,
        },
        dry,
    )
    print("=" * 68)
    print(f"Готово. Удалено пакетов: {len(removed_all)}")
    print("=" * 68)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flyarchos-profile",
        description="FlyArchOs: выбор рабочего окружения и наборов ПО",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--groups-dir", type=Path, default=GROUPS_DIR,
                       help=f"каталог с файлами групп (по умолчанию {GROUPS_DIR})")
    parser.add_argument("--desktop", default="both",
                       help="hyprland | plasma | both (можно списком через запятую)")
    parser.add_argument("--extras", default="",
                       help="наборы ПО через запятую: dev,gaming,media,office")
    parser.add_argument("--apply", action="store_true",
                       help="реально применить (по умолчанию только показ плана)")
    parser.add_argument("--remove-live", action="store_true", default=True,
                       help="удалить live-пакеты (Calamares и пр.) — по умолчанию да")
    parser.add_argument("--keep-live", dest="remove_live", action="store_false",
                       help="оставить live-пакеты в системе")
    parser.add_argument("--install-missing", action="store_true",
                       help="доставить отсутствующие пакеты выбранных групп")
    parser.add_argument("--clean-orphans", action="store_true", default=True,
                       help="удалить осиротевшие зависимости (по умолчанию да)")
    parser.add_argument("--no-clean-orphans", dest="clean_orphans", action="store_false")
    parser.add_argument("-q", "--quiet", action="store_true")

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="показать группы пакетов")
    sub_show = sub.add_parser("show", help="показать план для указанного выбора")
    sub_show.add_argument("--desktop", default="both")
    sub_show.add_argument("--extras", default="")
    sub_show.add_argument("--keep-live", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(not args.quiet)

    try:
        groups = load_groups(args.groups_dir)
        if getattr(args, "command", None) == "list":
            return cmd_list(groups)
        if getattr(args, "command", None) == "show":
            return cmd_show(args, groups)
        return cmd_apply(args, groups)
    except ProfileError as exc:
        print(f"ОШИБКА: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("прервано", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
