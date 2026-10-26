#!/usr/bin/env python3
"""flyarchos-doctor — быстрая диагностика системы FlyArchOs.

Проверяет типичные проблемы после установки и обновлений: упавшие службы,
место на диске, ошибки в журнале, пакеты-сироты, файлы .pacnew, звук,
сеть и видеодрайвер. Ничего не исправляет сам — только показывает,
что не так, и подсказывает команду.

    flyarchos-doctor            отчёт в терминал
    flyarchos-doctor --save     то же + сохранить в ~/flyarchos-doctor.txt
    flyarchos-doctor --fast     без проверки обновлений (не ходит в сеть)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
OFF = "\033[0m"

REPORT: list[str] = []
PROBLEMS: list[str] = []


def say(text: str = "") -> None:
    print(text)
    REPORT.append(text)


def title(name: str) -> None:
    say(f"\n{CYAN}— {name}{OFF}")


def ok(text: str) -> None:
    say(f"  {GREEN}ok{OFF}  {text}")


def warn(text: str, hint: str = "") -> None:
    say(f"  {YELLOW}!!{OFF}  {text}")
    if hint:
        say(f"       {DIM}{hint}{OFF}")
    PROBLEMS.append(text)


def run(args: list[str], timeout: int = 15) -> str | None:
    """Вывод команды или None, если её нет/не сработала."""
    if shutil.which(args[0]) is None:
        return None
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if proc.returncode in (0, 1) else None


def check_system() -> None:
    title("Система")
    pretty = "FlyArchOs"
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if line.startswith("PRETTY_NAME="):
                pretty = line.split("=", 1)[1].strip('"')
    except OSError:
        pass
    kernel = os.uname().release
    desktop = os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("XDG_SESSION_DESKTOP") or "консоль"
    ok(f"{pretty}, ядро {kernel}, окружение {desktop}")
    if not Path(f"/usr/lib/modules/{kernel}").is_dir():
        warn("установлено ядро новее запущенного", "перезагрузитесь")


def check_disk() -> None:
    title("Диск")
    usage = shutil.disk_usage("/")
    percent = usage.used * 100 // usage.total
    gib = 1024 ** 3
    text = f"корень: занято {usage.used // gib} из {usage.total // gib} ГБ ({percent}%)"
    if percent >= 95:
        warn(text, "критично мало места: flyarchos-info, ncdu /, очистка кэша: sudo pacman -Sc")
    elif percent >= 85:
        warn(text, "места маловато")
    else:
        ok(text)


def check_services() -> None:
    title("Службы")
    out = run(["systemctl", "--failed", "--no-legend", "--no-pager", "--plain"])
    if out is None:
        say("  (systemd недоступен)")
        return
    failed = [ln.split()[0] for ln in out.splitlines() if ln.strip()]
    if failed:
        warn(f"упавших служб: {len(failed)} — {', '.join(failed[:5])}",
             "подробности: systemctl status <служба>")
    else:
        ok("упавших служб нет")


def check_journal() -> None:
    title("Журнал (ошибки текущей загрузки)")
    out = run(["journalctl", "-b", "-p", "err", "--no-pager", "--output=cat"], timeout=30)
    if out is None:
        say("  (журнал недоступен)")
        return
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if lines:
        warn(f"ошибок уровня err: {len(lines)}", "посмотреть: journalctl -b -p err")
        for line in lines[:3]:
            say(f"       {DIM}{line[:110]}{OFF}")
    else:
        ok("ошибок в журнале нет")


def check_packages(fast: bool) -> None:
    title("Пакеты")
    out = run(["pacman", "-Qq"])
    if out is not None:
        ok(f"установлено пакетов: {len(out.split())}")
    orphans = run(["pacman", "-Qdtq"])
    if orphans and orphans.split():
        warn(f"пакетов-сирот: {len(orphans.split())}",
             "удалить: sudo pacman -Rns $(pacman -Qdtq)")
    pacnew: list[str] = []
    for root, _dirs, files in os.walk("/etc"):
        pacnew += [os.path.join(root, f) for f in files if f.endswith(".pacnew")]
        if len(pacnew) > 3:
            break
    if pacnew:
        warn(f"есть файлы .pacnew ({len(pacnew)}+)", "разобрать: sudo pacdiff")
    if Path("/var/lib/pacman/db.lck").exists():
        warn("осталась блокировка базы pacman (db.lck)",
             "если pacman сейчас не работает: sudo rm /var/lib/pacman/db.lck")
    if not fast:
        updates = run(["checkupdates"], timeout=60)
        if updates is None:
            say(f"       {DIM}обновления не проверены (нет сети?){OFF}")
        else:
            count = len([ln for ln in updates.splitlines() if ln.strip()])
            if count:
                warn(f"доступно обновлений: {count}", "установить: flyarchos-update")
            else:
                ok("система актуальна")


def check_network_audio_video() -> None:
    title("Сеть, звук, видео")
    state = run(["nmcli", "-t", "-f", "STATE", "general", "status"])
    if state and state.strip().startswith("connected"):
        ok(f"сеть: {state.strip()}")
    elif state:
        warn(f"сеть: {state.strip()}", "проверить: nmtui или flyarchos-doctor после подключения")
    for unit in ("pipewire", "wireplumber"):
        active = run(["systemctl", "--user", "is-active", unit])
        if active and active.strip() == "active":
            ok(f"{unit}: работает")
        elif active:
            warn(f"{unit}: {active.strip()}", f"перезапуск: systemctl --user restart {unit}")
    lspci = run(["lspci"])
    if lspci:
        for line in lspci.splitlines():
            if "VGA" in line or "3D controller" in line or "Display controller" in line:
                ok(f"GPU: {line.split(': ', 1)[-1][:90]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--save", action="store_true", help="сохранить отчёт в ~/flyarchos-doctor.txt")
    parser.add_argument("--fast", action="store_true", help="не проверять обновления (без сети)")
    args = parser.parse_args()

    # Без цветов, если вывод не в терминал
    if not sys.stdout.isatty():
        globals().update({k: "" for k in ("CYAN", "GREEN", "YELLOW", "RED", "DIM", "OFF")})

    say(f"{CYAN}FlyArchOs Doctor{OFF} — диагностика системы")
    check_system()
    check_disk()
    check_services()
    check_journal()
    check_packages(args.fast)
    check_network_audio_video()

    say()
    if PROBLEMS:
        say(f"{YELLOW}Итог: замечаний — {len(PROBLEMS)} (см. строки с !! выше){OFF}")
    else:
        say(f"{GREEN}Итог: всё в порядке ✔{OFF}")

    if args.save:
        import re
        plain = re.sub(r"\033\[[0-9;]*m", "", "\n".join(REPORT))
        target = Path.home() / "flyarchos-doctor.txt"
        target.write_text(plain + "\n", encoding="utf-8")
        print(f"Отчёт сохранён: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
