#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка дерева FlyArchOS перед сборкой ISO.

Запускается везде (не нужен Arch): проверяет синтаксис скриптов, YAML
Calamares, согласованность установщика со списками пакетов, наличие обоев,
ярлыков и файлов конфигурации.

    python3 scripts/check.py            # все проверки
    python3 scripts/check.py -q         # только ошибки
    python3 scripts/check.py --no-yaml  # пропустить проверки YAML
"""

from __future__ import annotations

import argparse
import ast
import json
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROFILE = REPO / "profile"
AIROOTFS = PROFILE / "airootfs"
CALAMARES = AIROOTFS / "etc" / "calamares"
FLYARCHOS_LIB = AIROOTFS / "usr" / "lib" / "flyarchos"
WALLPAPERS = AIROOTFS / "usr" / "share" / "backgrounds" / "flyarchos"
GROUPS = REPO / "groups"

try:
    import yaml
except ImportError:  # PyYAML не обязателен — проверки YAML просто пропустим
    yaml = None

# Модули Calamares, которым обязательно нужен свой .conf
NEEDS_CONFIG = {
    "welcome", "locale", "keyboard", "partition", "users",
    "packagechooser", "unpackfs", "shellprocess", "fstab", "machineid",
    "initcpiocfg", "initcpio", "grubcfg", "bootloader", "displaymanager",
    "services-systemd",
}
# Модули-задачи без собственного конфига (в upstream их нет)
NO_CONFIG_OK = {
    "mount", "umount", "localecfg", "networkcfg", "hostinfo", "hwclock",
    "finished", "summary", "luksbootkeyfile", "luksopenswaphookcfg", "zfs",
}

GREEN, RED, YELLOW, DIM, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


class Report:
    def __init__(self, quiet: bool = False):
        self.rows: list[tuple[str, str, str]] = []
        self.quiet = quiet

    def add(self, name: str, ok: bool | None, message: str = "") -> None:
        """ok=True — пройдено, False — ошибка, None — пропущено."""
        self.rows.append((name, "ok" if ok else ("skip" if ok is None else "fail"), message))
        if not self.quiet or ok is False:
            if ok is True:
                mark = f"{GREEN}  ok  {OFF}"
            elif ok is None:
                mark = f"{YELLOW} skip {OFF}"
            else:
                mark = f"{RED} FAIL {OFF}"
            print(f"{mark} {name}" + (f" {DIM}— {message}{OFF}" if message else ""))

    @property
    def failed(self) -> list[tuple[str, str, str]]:
        return [row for row in self.rows if row[1] == "fail"]

    @property
    def skipped(self) -> list[tuple[str, str, str]]:
        return [row for row in self.rows if row[1] == "skip"]


# --------------------------------------------------------------------------- #
# Отдельные проверки
# --------------------------------------------------------------------------- #
def python_files() -> list[Path]:
    files = sorted(REPO.glob("scripts/*.py"))
    files += sorted(FLYARCHOS_LIB.glob("*.py"))
    files += sorted((REPO / "scripts" / "tests").glob("*.py"))
    return [f for f in files if f.is_file()]


def shell_files() -> list[Path]:
    found: list[Path] = []
    for pattern in ("scripts/*.sh", "profile/*.sh", "profile/airootfs/usr/lib/flyarchos/*",
                    "profile/airootfs/usr/lib/flyarchos/*.sh"):
        found.extend(REPO.glob(pattern))
    result = []
    for path in sorted(set(found)):
        if not path.is_file() or path.suffix == ".py":
            continue
        head = path.read_text(encoding="utf-8", errors="ignore")[:128]
        if "bash" in head or path.suffix == ".sh":
            result.append(path)
    return result


def check_python(report: Report) -> None:
    broken = []
    for path in python_files():
        try:
            source = path.read_text(encoding="utf-8")
            ast.parse(source)
            with tempfile.TemporaryDirectory() as tmp:
                py_compile.compile(str(path), cfile=str(Path(tmp) / "x.pyc"), doraise=True)
        except Exception as exc:  # noqa: BLE001
            broken.append(f"{path.relative_to(REPO)}: {exc}")
    report.add(f"Python: синтаксис ({len(python_files())} файлов)", not broken, "; ".join(broken))


def check_shell(report: Report) -> None:
    broken = []
    files = shell_files()
    for path in files:
        proc = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
        if proc.returncode != 0:
            broken.append(f"{path.relative_to(REPO)}: {proc.stderr.strip().splitlines()[-1]}")
    report.add(f"Bash: синтаксис ({len(files)} файлов)", not broken, "; ".join(broken))


def check_setup_logging(report: Report) -> None:
    """Заодно ловим «немые» места: скрипты без set -e/-u не ошибка, просто подсказка."""
    sloppy = []
    for path in shell_files():
        text = path.read_text(encoding="utf-8")
        if path.suffix != ".sh" or path.name == "profiledef.sh":
            continue
        if "set -" not in text and "set -" not in text[:400]:
            sloppy.append(str(path.relative_to(REPO)))
    report.add("Bash: наличие 'set -euo pipefail' в скриптах", not sloppy,
               "нет в: " + ", ".join(sloppy) if sloppy else "")


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def check_yaml(report: Report, enabled: bool) -> None:
    if not enabled:
        report.add("YAML Calamares", None, "отключено флагом --no-yaml")
        return
    if yaml is None:
        report.add("YAML Calamares", None, "не установлен PyYAML (pip install pyyaml)")
        return
    files = sorted(CALAMARES.glob("modules/*.conf")) + [CALAMARES / "settings.conf"]
    files += sorted((CALAMARES / "branding").glob("*/*.desc"))
    broken = []
    for path in files:
        if not path.is_file():
            broken.append(f"{path.relative_to(REPO)}: файла нет")
            continue
        try:
            load_yaml(path)
        except Exception as exc:  # noqa: BLE001
            broken.append(f"{path.relative_to(REPO)}: {exc}")
    report.add(f"YAML Calamares ({len(files)} файлов)", not broken, "; ".join(broken))


def check_settings(report: Report) -> None:
    if yaml is None:
        report.add("settings.conf ↔ модули", None, "нет PyYAML")
        return
    settings_path = CALAMARES / "settings.conf"
    if not settings_path.is_file():
        report.add("settings.conf ↔ модули", False, "нет settings.conf")
        return
    settings = load_yaml(settings_path)
    instances = {item["id"]: item for item in settings.get("instances", [])}
    problems: list[str] = []

    # 1. у каждого экземпляра есть свой конфиг
    for ident, instance in instances.items():
        config = CALAMARES / "modules" / instance["config"]
        if not config.is_file():
            problems.append(f"нет {instance['config']} для экземпляра {ident}")

    # 2. все модули последовательности существуют/описаны
    used: list[str] = []
    for phase in settings.get("sequence", []):
        for (_kind, entries) in phase.items():
            used.extend(entries)
    for entry in used:
        if "@" in entry:
            module, ident = entry.split("@", 1)
            if ident not in instances:
                problems.append(f"{entry}: экземпляр не описан в instances")
                continue
            # у экземпляра свой конфиг (проверен выше) — модульный не требуется
            continue
        module = entry
        config = CALAMARES / "modules" / f"{module}.conf"
        if not config.is_file() and module in NEEDS_CONFIG:
            problems.append(f"{entry}: нет modules/{module}.conf")

    # 3. GS-ключи в shellprocess пишет только ПОКАЗАННАЯ страница
    # packagechooser (onLeave). Экземпляра в instances мало: модули вне
    # sequence/show Calamares вообще не загружает, ключ не появится, и
    # shellprocess упадёт до запуска команды (регрессия slim/mini №49/№51).
    shown_chooser_ids: set[str] = set()
    for phase in settings.get("sequence", []):
        for entry in phase.get("show", []) or []:
            if isinstance(entry, str) and entry.startswith("packagechooser@"):
                shown_chooser_ids.add(entry.split("@", 1)[1])
    for ident in sorted(shown_chooser_ids):
        inst = instances.get(ident)
        if not inst or inst.get("module") != "packagechooser":
            problems.append(f"packagechooser@{ident}: показан, но экземпляр не packagechooser")
    for path in sorted((CALAMARES / "modules").glob("shellprocess_*.conf")):
        text = path.read_text(encoding="utf-8")
        for key in re.findall(r"\$\{gs\[([^\]]+)\]\}", text):
            if key.startswith("packagechooser_"):
                if key.split("_", 1)[1] not in shown_chooser_ids:
                    problems.append(
                        f"{path.name}: GS-ключ {key} без показанной страницы packagechooser")
            else:
                problems.append(f"{path.name}: неизвестный GS-ключ {key}")
    report.add("settings.conf ↔ модули/экземпляры/GS-ключи", not problems, "; ".join(problems))


def check_packagechooser_groups(report: Report) -> None:
    """id вариантов в packagechooser должны совпадать с файлами групп."""
    if yaml is None:
        report.add("packagechooser ↔ группы пакетов", None, "нет PyYAML")
        return
    group_names = {path.stem.split("-", 1)[-1] for path in GROUPS.glob("*.txt")}
    problems = []
    desktop_ids: list[str] = []
    for path in sorted((CALAMARES / "modules").glob("packagechooser_*.conf")):
        data = load_yaml(path)
        for item in data.get("items", []):
            ident = item["id"]
            if path.name.endswith(("bootloader.conf", "preset.conf")):
                continue
            if ident in ("both", ""):
                continue
            if ident not in group_names:
                problems.append(f"{path.name}: id '{ident}' — нет такой группы пакетов")
            if path.name.endswith("desktop.conf"):
                desktop_ids.append(ident)
    report.add("packagechooser ↔ группы пакетов", not problems, "; ".join(problems))


def detected_profile_name() -> str:
    """Какой профиль записан в шапке packages.x86_64 (full/slim/mini)."""
    path = PROFILE / "packages.x86_64"
    if not path.is_file():
        return "full"
    match = re.search(r"^# Профиль: (\w+)", path.read_text(encoding="utf-8"), re.M)
    if match and match.group(1) in ("slim", "mini"):
        return match.group(1)
    return "full"


def check_packages_list(report: Report) -> None:
    cmd = [sys.executable, str(REPO / "scripts" / "gen-packages.py"), "--check"]
    profile = detected_profile_name()
    if profile != "full":
        cmd += ["--profile", profile]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    suffix = f" [профиль: {profile}]" if profile != "full" else ""
    report.add("packages.x86_64 актуален (groups/)" + suffix, proc.returncode == 0,
               proc.stderr.strip().replace("\n", " "))


def check_groups(report: Report) -> None:
    """Группы не должны быть пустыми, обязательные — присутствовать."""
    problems = []
    for path in sorted(GROUPS.glob("*.txt")):
        names = [ln.split("#")[0].strip() for ln in path.read_text(encoding="utf-8").splitlines()]
        names = [ln for ln in names if ln]
        if not names:
            problems.append(f"{path.name}: пусто")
    required = {"core", "common", "hyprland", "plasma", "apps"}
    present = {path.stem.split("-", 1)[-1] for path in GROUPS.glob("*.txt")}
    for name in sorted(required - present):
        problems.append(f"нет обязательной группы: {name}")
    report.add(f"Группы пакетов ({len(present)} шт.)", not problems, "; ".join(problems))


def check_shellprocess_targets(report: Report) -> None:
    """Скрипты/команды, которые Calamares запускает, должны существовать в образе."""
    if yaml is None:
        report.add("shellprocess: цели существуют", None, "нет PyYAML")
        return
    problems = []
    for path in sorted((CALAMARES / "modules").glob("shellprocess_*.conf")):
        data = load_yaml(path)
        for step in data.get("script", []):
            command = step["command"] if isinstance(step, dict) else str(step)
            # убрать подстановки Calamares
            command = re.sub(r"\$\{[^}]*\}", "PLACEHOLDER", command)
            binary = command.split()[0]
            target = None
            for prefix in ("", "usr/bin/", "usr/local/bin/", "bin/"):
                candidate = AIROOTFS / (prefix + binary.lstrip("/"))
                if candidate.exists():
                    target = candidate
                    break
            if target is None:
                problems.append(f"{path.name}: нет {binary} в airootfs")
    report.add("shellprocess: цели существуют в airootfs", not problems, "; ".join(problems))


# Эти файлы появляются в airootfs только после pacstrap (их приносит пакет
# filesystem) — их отсутствие в дереве репозитория не ошибка.
PACSTRAP_PATHS = {"/etc/shadow", "/etc/gshadow", "/etc/passwd", "/etc/group",
    "/root",      # создаёт pacstrap
    "/home/fly",  # собирает build-iso.sh из /etc/skel
}


def check_file_permissions(report: Report) -> None:
    """Пути из file_permissions должны существовать в airootfs — иначе mkarchiso падает."""
    profiledef = PROFILE / "profiledef.sh"
    if not profiledef.is_file():
        report.add("Права файлов (profiledef.sh)", False, "нет profile/profiledef.sh")
        return
    text = profiledef.read_text(encoding="utf-8")
    match = re.search(r"file_permissions=\((.*?)\n\)", text, re.S)
    if not match:
        report.add("Права файлов (profiledef.sh)", False, "нет блока file_permissions")
        return
    entries = re.findall(r'\["([^"]+)"\]="([^"]+)"', match.group(1))
    problems = []
    for path, perm in entries:
        if path in PACSTRAP_PATHS:
            continue
        if not (AIROOTFS / path.lstrip("/")).exists():
            problems.append(f"{path} — нет в airootfs")
        if len(perm.split(":")) != 3:
            problems.append(f"{path} — права должны быть uid:gid:mode, а не {perm!r}")
    report.add("Права файлов (profiledef.sh)", not problems, "; ".join(problems))


def check_pacman_template(report: Report) -> None:
    """Метка @FLYARCHOS_REPO@ должна стоять отдельной строкой: mkarchiso
    требует, чтобы каждая директива pacman.conf была внутри секции."""
    template = PROFILE / "pacman.conf.in"
    if not template.is_file():
        report.add("Шаблон pacman.conf", False, "нет profile/pacman.conf.in")
        return
    problems = []
    for number, line in enumerate(template.read_text(encoding="utf-8").splitlines(), 1):
        if "@FLYARCHOS_REPO@" in line and line.strip() != "@FLYARCHOS_REPO@":
            problems.append(f"строка {number}: метка не на отдельной строке")
    report.add("Шаблон pacman.conf", not problems, "; ".join(problems))


def check_wallpapers(report: Report) -> None:
    manifest = AIROOTFS / "usr" / "share" / "flyarchos" / "wallpapers.json"
    problems = []
    count = 0
    if not manifest.is_file():
        report.add("Обои", False, "нет wallpapers.json (запустите scripts/pack-wallpapers.py)")
        return
    data = json.loads(manifest.read_text(encoding="utf-8"))
    for item in data["wallpapers"]:
        count += 1
        for key in ("file", "thumb"):
            target = AIROOTFS / item[key].lstrip("/")
            if not target.is_file():
                problems.append(f"{item['id']}: нет {item[key]}")
    if not (WALLPAPERS / "default.jpg").is_file():
        problems.append("нет default.jpg")
    if not (WALLPAPERS / "grub.png").is_file():
        problems.append("нет grub.png")
    kde = sorted((AIROOTFS / "usr" / "share" / "wallpapers").glob("FlyArchOs-*"))
    for package in kde:
        if not (package / "metadata.json").is_file():
            problems.append(f"{package.name}: нет metadata.json")
        if not list((package / "contents" / "images").glob("*.jpg")):
            problems.append(f"{package.name}: нет картинок")
    report.add(f"Обои ({count} шт., {len(kde)} пакетов Plasma)", not problems, "; ".join(problems[:6]))


def check_desktop_files(report: Report) -> None:
    """Exec= в .desktop должен указывать на существующий файл в образе."""
    problems = []
    files = sorted(AIROOTFS.glob("usr/share/applications/*.desktop")) + \
        sorted(AIROOTFS.glob("etc/xdg/autostart/*.desktop"))
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("Exec="):
                rel = line[5:].split()[0].lstrip("/")
                target = AIROOTFS / (rel if "/" in rel else f"usr/bin/{rel}")
                binary = rel
                if not target.exists():
                    problems.append(f"{path.name}: {binary} не найден")
    report.add(f"Ярлыки .desktop ({len(files)} шт.)", not problems, "; ".join(problems))


def check_skel(report: Report) -> None:
    skel = AIROOTFS / "etc" / "skel"
    expected = [
        ".config/hypr/hyprland.lua",
        ".config/hypr/theme.lua",
        ".config/hypr/hypridle.conf",
        ".config/hypr/hyprlock.conf",
        ".config/waybar/config",
        ".config/waybar/style.css",
        ".config/wofi/config",
        ".config/mako/config",
        ".config/kdeglobals",
        ".config/plasma-org.kde.plasma.desktop-appletsrc",
        ".config/kitty/kitty.conf",
        ".config/gtk-3.0/settings.ini",
        ".zshrc",
    ]
    missing = [name for name in expected if not (skel / name).is_file()]
    report.add(f"Настройки /etc/skel ({len(expected)} файлов)", not missing,
               "нет: " + ", ".join(missing) if missing else "")


def check_installer_scripts(report: Report) -> None:
    expected = [
        "install-prepare.sh",
        "install-finalize.sh",
        "profile_tool.py",
        "wallpaper_tool.py",
        "wallpapers.py",
        "welcome-gui.py",
        "flyarchos-info",
        "flyarchos-install",
        "flyarchos-update",
        "flyarchos-snapshot",
        "doctor_tool.py",
        "theme_tool.py",
        "backup_tool.py",
        "flyarchos-clean",
        "flyarchos-aur",
        "flyarchos-exe",
        "flyarchos-performance",
    ]
    missing = []
    non_exec = []
    for name in expected:
        path = FLYARCHOS_LIB / name
        if not path.is_file():
            missing.append(name)
        elif not (path.stat().st_mode & 0o111):
            non_exec.append(name)
    report.add(f"Инструменты FlyArchOs ({len(expected)} шт.)", not missing and not non_exec,
               ("нет: " + ", ".join(missing) if missing else "") +
               ("; не исполняемые: " + ", ".join(non_exec) if non_exec else ""))


def check_branding(report: Report) -> None:
    branding = CALAMARES / "branding" / "flyarchos"
    expected = ["branding.desc", "logo.png", "welcome.png", "show.qml"]
    if not ((branding / "wallpaper.jpg").is_file() or (branding / "wallpaper.png").is_file()):
        expected.append("wallpaper.jpg")
    missing = [name for name in expected if not (branding / name).is_file()]
    report.add("Брендинг Calamares", not missing, "нет: " + ", ".join(missing) if missing else "")


def check_docs(report: Report) -> None:
    expected = ["README.md", "docs/BUILD.md", "docs/INSTALL.md", "docs/STRUCTURE.md"]
    missing = [name for name in expected if not (REPO / name).is_file()]
    report.add("Документация", not missing, "нет: " + ", ".join(missing) if missing else "")


def check_tools(report: Report) -> None:
    missing = [tool for tool in ("mkarchiso",) if shutil.which(tool) is None]
    if missing:
        report.add("Инструменты сборки", None,
                   "не найдено: " + ", ".join(missing) + " (нужен Arch Linux с пакетом archiso)")
    else:
        report.add("Инструменты сборки", True, "mkarchiso найден")


# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-q", "--quiet", action="store_true", help="печатать только ошибки")
    parser.add_argument("--no-yaml", action="store_true", help="пропустить проверки YAML")
    args = parser.parse_args()

    report = Report(quiet=args.quiet)
    print("Проверка дерева FlyArchOs\n")

    check_python(report)
    check_shell(report)
    check_setup_logging(report)
    check_yaml(report, not args.no_yaml)
    check_settings(report)
    check_packagechooser_groups(report)
    check_shellprocess_targets(report)
    check_groups(report)
    check_packages_list(report)
    check_file_permissions(report)
    check_pacman_template(report)
    check_installer_scripts(report)
    check_wallpapers(report)
    check_skel(report)
    check_desktop_files(report)
    check_branding(report)
    check_docs(report)
    check_tools(report)

    failed, skipped = report.failed, report.skipped
    print()
    print(f"Итого: {len(report.rows) - len(failed) - len(skipped)} пройдено, "
          f"{len(failed)} провалено, {len(skipped)} пропущено")
    if failed:
        print("\nЧто исправить:")
        for name, _state, message in failed:
            print(f"  • {name}: {message}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
