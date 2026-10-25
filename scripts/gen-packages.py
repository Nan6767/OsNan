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


def render(groups: list[tuple[str, Path, list[str]]], title: str, only: Sequence[str] = ()) -> str:
    lines = [HEADER, f"# Файл: {title}", "#"]
    if only:
        lines.append(f"# Профиль: slim (группы: {', '.join(only)})")
    else:
        lines.append("# Профиль: full (все группы)")
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
    parser.add_argument("--only-groups", default="",
                       help="ограничить состав (например core,common,hyprland,plasma,apps,live)")
    parser.add_argument("--check", action="store_true", help="проверить, что файлы актуальны")
    parser.add_argument("--stats", action="store_true", help="вывести статистику по группам")
    args = parser.parse_args()

    only = [name.strip() for name in args.only_groups.split(",") if name.strip()]

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

    if args.stats:
        width = max(len(name) for name, _, _ in groups)
        total = 0
        for name, path, packages in groups:
            total += len(packages)
            print(f"{name:<{width}}  {len(packages):>4}  ({path.name})")
        print(f"{'ИТОГО':<{width}}  {total:>4}")
        return 0

    content = render(groups, args.out.name, only)
    aur_file = args.groups_dir / "aur.txt"
    aur_content = ""
    if aur_file.is_file() and not only:  # в slim-профиле AUR не собираем
        aur_pkgs = parse_group(aur_file)
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
