#!/usr/bin/env python3
"""Generate the archiso package list (``profile/packages.x86_64``) from ``groups/*.txt``.

The group files are the single source of truth for packages in FlyArchOs:

* ``00-core.txt`` … ``99-live.txt``   — official repositories (always installed
  into the ISO, some groups are pruned by the installer afterwards);
* ``aur.txt``                          — AUR/extra packages, included into the
  ISO only when a local repository has been built (see ``scripts/build-aur.sh``).

Usage::

    scripts/gen-packages.py                 # regenerate the list
    scripts/gen-packages.py --check         # verify it is up to date (CI)
    scripts/gen-packages.py --stats         # print per-group statistics
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GROUPS = REPO_ROOT / "groups"
DEFAULT_OUT = REPO_ROOT / "profile" / "packages.x86_64"
DEFAULT_AUR_OUT = REPO_ROOT / "profile" / "packages.aux"

PKG_RE = re.compile(r"^[a-z0-9][a-z0-9+._-]*$")
GROUP_RE = re.compile(r"^(?P<order>\d{2})-(?P<name>[a-z0-9]+)\.txt$")

HEADER = """\
# ---------------------------------------------------------------------------
# FlyArchOs — список пакетов live-образа.
#
# ВНИМАНИЕ: файл сгенерирован scripts/gen-packages.py из каталога groups/.
# Не правьте его руками — правьте groups/*.txt и запускайте `make packages`.
# ---------------------------------------------------------------------------
"""


class PackageError(Exception):
    """Raised when a group file is malformed."""


def parse_group(path: Path) -> list[str]:
    """Return the package names declared in *path* (comments stripped)."""
    packages: list[str] = []
    seen: dict[str, int] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        for name in line.split():
            if not PKG_RE.match(name):
                raise PackageError(
                    f"{path}:{number}: подозрительное имя пакета {name!r} "
                    "(допустимы только [a-z0-9+._-], без версий и кавычек)"
                )
            if name in seen:
                raise PackageError(f"{path}:{number}: пакет {name!r} уже указан в {path}:{seen[name]}")
            seen[name] = number
            packages.append(name)
    return packages


def local_repo_packages(repo_dir: Path) -> set[str]:
    """Return package names actually present in the local repository *repo_dir*."""
    built: set[str] = set()
    if not repo_dir.is_dir():
        return built
    for path in repo_dir.glob("*.pkg.tar.zst"):
        # формат: имя-версия-релиз-архитектура.pkg.tar.zst
        parts = path.name[: -len(".pkg.tar.zst")].rsplit("-", 3)
        if len(parts) == 4:
            built.add(parts[0])
    return built


def load_groups(groups_dir: Path) -> list[tuple[str, Path, list[str]]]:
    """Load every ``NN-name.txt`` file from *groups_dir*, ordered by number."""
    if not groups_dir.is_dir():
        raise PackageError(f"нет каталога с группами: {groups_dir}")
    result = []
    for path in sorted(groups_dir.glob("[0-9][0-9]-*.txt")):
        match = GROUP_RE.match(path.name)
        if not match:
            raise PackageError(
                f"{path.name}: имя файла должно быть NN-имя.txt (например 20-hyprland.txt)"
            )
        result.append((match.group("name"), path, parse_group(path)))
    return result


# --------------------------------------------------------------------------- #
# Профили сборки. Единое место, где описано, чем slim и mini отличаются от
# полного образа — build-iso.sh и ci-build.sh просто передают --profile.
# --------------------------------------------------------------------------- #
SLIM_GROUPS: list[str] = ["core", "common", "hyprland", "plasma", "apps", "live"]

# mini: тот же состав групп, но без тяжёлых пакетов. Цель — ISO меньше 2 ГБ,
# чтобы он влезал в GitHub Release одним файлом (лимит GitHub — 2 GiB).
# Здесь только имена из groups/*.txt (зависимости pacman подтянет сам).
MINI_EXCLUDE: list[str] = [
    # второе ядро и заголовки, компиляторы
    "linux-lts", "linux-lts-headers", "linux-headers", "base-devel",
    # рантаймы для разработки
    "nodejs", "npm", "python-pip",
    # документация и дубль редактора
    "man-pages", "texinfo", "vim",
    # тяжёлые шрифты (остаются Noto Sans/Emoji, JetBrains Mono Nerd, DejaVu, Liberation)
    "noto-fonts-cjk", "noto-fonts-extra", "ttf-fira-code", "ttf-roboto",
    "ttf-opensans", "inter-font", "ttf-jetbrains-mono",
    # второй браузер и мессенджеры (остаётся Firefox)
    "chromium", "telegram-desktop", "discord", "qbittorrent",
    # дубли и необязательное
    "foot", "imagemagick", "fwupd", "clonezilla",
    # стоковые обои и дополнения Plasma (свои обои в образе есть)
    "plasma-workspace-wallpapers", "kdeplasma-addons",
    # графический центр обновлений заменяет flyarchos-update
    "discover", "packagekit", "packagekit-qt6",
    "elisa", "kdeconnect", "kinfocenter",
]

PROFILES: dict[str, dict[str, list[str]]] = {
    "full": {"groups": [], "exclude": []},
    "slim": {"groups": SLIM_GROUPS, "exclude": []},
    "mini": {"groups": SLIM_GROUPS, "exclude": MINI_EXCLUDE},
}


def render(groups: list[tuple[str, Path, list[str]]], title: str, only: Sequence[str] = (),
           profile: str = "full", excluded_count: int = 0) -> str:
    lines = [HEADER, f"# Файл: {title}", "#"]
    if profile == "full" and not only:
        lines.append("# Профиль: full (все группы)")
    else:
        label = profile if profile != "full" else "slim"
        suffix = f"; исключено пакетов: {excluded_count}" if excluded_count else ""
        lines.append(f"# Профиль: {label} (группы: {', '.join(only)}{suffix})")
    total = 0
    for name, path, packages in groups:
        total += len(packages)
        lines.append(f"# --- {name} ({path.name}): {len(packages)} шт. " + "-" * 20)
        lines.extend(packages)
        lines.append("")
    lines.insert(3, f"# Всего пакетов: {total}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--groups-dir", type=Path, default=DEFAULT_GROUPS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--aur-out", type=Path, default=DEFAULT_AUR_OUT)
    parser.add_argument("--profile", choices=["full", "slim", "mini"], default="",
                       help="готовый профиль: full — всё, slim — без доп. наборов, "
                            "mini — компактный ISO < 2 ГБ одним файлом")
    parser.add_argument("--only-groups", default="",
                       help="ограничить состав (например core,common,hyprland,plasma,apps,live)")
    parser.add_argument("--exclude", default="",
                       help="исключить пакеты по именам (через запятую) — например calamares")
    parser.add_argument("--check", action="store_true", help="проверить, что файлы актуальны")
    parser.add_argument("--stats", action="store_true", help="вывести статистику по группам")
    args = parser.parse_args()

    only = [name.strip() for name in args.only_groups.split(",") if name.strip()]
    exclude = {name.strip() for name in args.exclude.split(",") if name.strip()}
    profile = args.profile
    if profile:
        spec = PROFILES[profile]
        if not only:
            only = list(spec["groups"])
        exclude |= set(spec["exclude"])

    try:
        groups = load_groups(args.groups_dir)
    except PackageError as exc:
        print(f"ОШИБКА: {exc}", file=sys.stderr)
        return 1

    if only:
        known = {name for name, _path, _packages in groups}
        unknown = [name for name in only if name not in known]
        if unknown:
            print(f"ОШИБКА: неизвестные группы: {', '.join(unknown)}", file=sys.stderr)
            return 1
        groups = [item for item in groups if item[0] in only]

    excluded_count = 0
    if exclude:
        trimmed = []
        for name, path, pkgs in groups:
            kept = [p for p in pkgs if p not in exclude]
            excluded_count += len(pkgs) - len(kept)
            trimmed.append((name, path, kept))
        groups = trimmed

    if args.stats:
        width = max(len(name) for name, _, _ in groups)
        total = 0
        for name, path, packages in groups:
            total += len(packages)
            print(f"{name:<{width}}  {len(packages):>4}  ({path.name})")
        print(f"{'ИТОГО':<{width}}  {total:>4}")
        return 0

    content = render(groups, args.out.name, only, profile, excluded_count)
    # В дополнительный список попадают только те AUR-пакеты, которые РЕАЛЬНО
    # собраны в локальный репозиторий repo/x86_64 — иначе mkarchiso упадёт
    # с «target not found».
    aur_file = args.groups_dir / "aur.txt"
    aur_content = ""
    if aur_file.is_file():
        wanted = [p for p in parse_group(aur_file) if p not in exclude]
        built = local_repo_packages(REPO_ROOT / "repo" / "x86_64")
        aur_pkgs = [p for p in wanted if p in built]
        aur_content = "\n".join(aur_pkgs) + "\n" if aur_pkgs else ""

    if args.check:
        ok = True
        for path, expected in ((args.out, content), (args.aur_out, aur_content)):
            current = path.read_text(encoding="utf-8") if path.is_file() else ""
            if current != expected:
                ok = False
                print(f"ОШИБКА: {path} устарел — выполните `make packages`", file=sys.stderr)
        return 0 if ok else 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(content, encoding="utf-8")
    total = sum(len(pkgs) for _, _, pkgs in groups)
    print(f"{args.out}: записано {total} пакетов из {len(groups)} групп")

    if aur_content:
        args.aur_out.write_text(aur_content, encoding="utf-8")
        print(f"{args.aur_out}: записано {len(aur_content.split())} пакетов из локального репозитория")
    elif args.aur_out.is_file():
        args.aur_out.unlink()
        print(f"{args.aur_out}: удалён (локальный репозиторий не собран)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
