#!/usr/bin/env python3
"""flyarchos-backup — инкрементные резервные копии домашнего каталога.

Каждый запуск создаёт отдельный снимок ``backup-ГГГГММДД-ЧЧММСС``;
Неизменённые файлы между снимками разделяются жёсткими ссылками
(rsync --link-dest), поэтому хранить несколько снимков дёшево.
Старые снимки старше лимита удаляются автоматически.

    flyarchos-backup                       # создать копию в ~/FlyArchOs-Backups
    flyarchos-backup --dest /run/media/me/USB/fly   # на внешний носитель
    flyarchos-backup list                  # список копий
    flyarchos-backup restore [имя]         # восстановить (по умолчанию последнюю)
    flyarchos-backup prune --keep 3        # оставить только 3 последние

Совет: храните копии на внешнем диске — копия в том же доме защищает
от случайных удалений, но не от поломки диска.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

MANIFEST = "flyarchos-backup.json"

# Что не копируем: кэши и мусор, которые легко восстановить без нас.
EXCLUDES = [
    ".cache",
    ".local/share/Trash",
    ".local/share/flatpak",
    ".var/app/*/.cache",
    "snap",
    ".npm",
    ".cargo/registry",
    "go/pkg/mod/cache",
]


def snapshot_name(now: datetime | None = None) -> str:
    return "backup-" + (now or datetime.now()).strftime("%Y%m%d-%H%M%S")


def list_snapshots(dest: Path) -> list[Path]:
    """Снимки в *dest*, старые -> новые. Чужие каталоги не трогаем."""
    if not dest.is_dir():
        return []
    found = [p for p in dest.glob("backup-*")
             if p.is_dir() and (p / MANIFEST).is_file()]
    return sorted(found, key=lambda p: p.name)


def _excludes_for(home: Path, dest: Path) -> list[str]:
    result = list(EXCLUDES)
    try:
        rel = dest.resolve().relative_to(home.resolve())
        result.append(rel.as_posix())
    except ValueError:
        pass
    return result


def _copy_tree(home: Path, target: Path, excludes: list[str]) -> None:
    """Запасной копировщик, если нет rsync (без жёстких ссылок)."""
    top = {e.split("/", 1)[0] for e in excludes if "*" not in e.split("/", 1)[0]}

    def ignore(dirpath: str, names: list[str]) -> set[str]:
        rel = Path(dirpath).relative_to(home).as_posix()
        skip: set[str] = set()
        for name in names:
            joined = name if rel == "." else f"{rel}/{name}"
            if joined in excludes or (rel == "." and name in top and name in excludes):
                skip.add(name)
            elif any(joined == e or joined.startswith(e.rstrip("*").rstrip("/") + "/")
                     for e in excludes):
                skip.add(name)
        return skip

    shutil.copytree(home, target, symlinks=True, ignore=ignore)


def _rsync(src: Path, dst: Path, excludes: list[str],
           link_dest: Path | None, rsync: str) -> None:
    cmd = [rsync, "-a", "--human-readable"]
    for pattern in excludes:
        cmd.append(f"--exclude={pattern}")
    cmd.append(f"--exclude={MANIFEST}")
    if link_dest is not None:
        cmd.append(f"--link-dest={link_dest}")
    dst.mkdir(parents=True, exist_ok=True)
    cmd += [f"{src}/", f"{dst}/"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode not in (0, 24):  # 24: часть файлов исчезла по пути — не страшно
        raise RuntimeError(f"rsync завершился с кодом {proc.returncode}:\n{proc.stderr.strip()}")


def prune(dest: Path, keep: int) -> list[Path]:
    snapshots = list_snapshots(dest)
    removed: list[Path] = []
    for old in snapshots[: max(0, len(snapshots) - keep)]:
        shutil.rmtree(old, ignore_errors=True)
        removed.append(old)
    return removed


def create_snapshot(home: Path, dest: Path, keep: int = 5,
                    rsync_path: str | None = None) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    excludes = _excludes_for(home, dest)
    previous = list_snapshots(dest)
    previous_dir = previous[-1] if previous else None

    name = snapshot_name()
    while (dest / name).exists():
        name += "x"
    tmp = dest / f".inprogress-{name}"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)

    rsync = rsync_path if rsync_path is not None else (shutil.which("rsync") or "")
    if rsync:
        _rsync(home, tmp, excludes, previous_dir, rsync)
    else:
        _copy_tree(home, tmp, excludes)

    (tmp / MANIFEST).write_text(json.dumps({
        "created": datetime.now().isoformat(timespec="seconds"),
        "host": socket.gethostname(),
        "home": str(home),
        "tool": "flyarchos-backup",
        "incremental_from": previous_dir.name if previous_dir else None,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    final = dest / name
    tmp.rename(final)
    latest = dest / "latest"
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(final.name)
    except OSError:
        pass
    prune(dest, keep)
    return final


def restore_snapshot(dest: Path, snapshot: Path, home: Path,
                     rsync_path: str | None = None) -> None:
    rsync = rsync_path if rsync_path is not None else (shutil.which("rsync") or "")
    if rsync:
        _rsync(snapshot, home, [], None, rsync)
    else:
        for item in snapshot.iterdir():
            if item.name == MANIFEST:
                continue
            target = home / item.name
            if item.is_dir() and not item.is_symlink():
                shutil.copytree(item, target, symlinks=True, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target, follow_symlinks=False)


def _human(size: float) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if size < 1024 or unit == "ГБ":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} ГБ"


def dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", nargs="?", default="create",
                        choices=["create", "list", "restore", "prune"],
                        help="действие (по умолчанию create)")
    parser.add_argument("snapshot", nargs="?", help="имя снимка для restore")
    parser.add_argument("--dest", type=Path,
                        default=Path(os.environ.get("FLYARCHOS_BACKUP_DIR",
                                     Path.home() / "FlyArchOs-Backups")),
                        help="где хранить копии")
    parser.add_argument("--keep", type=int, default=5, help="сколько копий хранить")
    parser.add_argument("--yes", action="store_true", help="без подтверждения (restore)")
    args = parser.parse_args()

    home = Path.home()
    dest: Path = args.dest.expanduser()

    if args.action == "list":
        snapshots = list_snapshots(dest)
        if not snapshots:
            print(f"Копий в {dest} пока нет. Создать: flyarchos-backup")
            return 0
        for snap in snapshots:
            print(f"{snap.name}  ({_human(dir_size(snap))})")
        return 0

    if args.action == "prune":
        removed = prune(dest, args.keep)
        for old in removed:
            print(f"удалено: {old.name}")
        print(f"осталось копий: {len(list_snapshots(dest))}")
        return 0

    if args.action == "restore":
        snapshots = list_snapshots(dest)
        if not snapshots:
            print("восстанавливать нечего: копий нет", file=sys.stderr)
            return 1
        chosen = (dest / args.snapshot) if args.snapshot else snapshots[-1]
        if not (chosen.is_dir() and (chosen / MANIFEST).is_file()):
            print(f"нет такой копии: {chosen}", file=sys.stderr)
            return 1
        if not args.yes:
            ans = input(f"Восстановить {chosen.name} в {home}? Файлы будут перезаписаны. [y/N] ")
            if ans.strip().lower() not in ("y", "yes", "д", "да"):
                print("Отменено")
                return 0
        restore_snapshot(dest, chosen, home)
        print(f"Восстановлено из {chosen.name}")
        return 0

    final = create_snapshot(home, dest, keep=args.keep)
    print(f"Копия создана: {final} ({_human(dir_size(final))})")
    print(f"Хранится копий: {len(list_snapshots(dest))} (лимит {args.keep})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
