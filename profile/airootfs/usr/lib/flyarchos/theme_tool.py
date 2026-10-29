#!/usr/bin/env python3
"""flyarchos-theme — готовые пресеты оформления для Hyprland и KDE Plasma.

Один пресет меняет сразу всё: обои, акцентный цвет Plasma и градиент
рамок окон Hyprland (~/.config/hypr/theme.lua, подключается через
``require("theme")`` в hyprland.lua; Hyprland 0.57+ .conf не читает).

    flyarchos-theme list       список пресетов
    flyarchos-theme nord       применить пресет
    flyarchos-theme next       следующий пресет по кругу (Super+Shift+W)
    flyarchos-theme current    что выбрано сейчас
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# имя: (обои для flyarchos-wallpaper, акцент HEX, второй цвет градиента HEX, подпись)
PRESETS: dict[str, tuple[str, str, str, str]] = {
    "aurora": ("aurora-nexus", "22d3ee", "818cf8", "Северное сияние"),
    "neon":   ("neon-grid",    "f0559b", "22d3ee", "Неоновая сетка"),
    "dawn":   ("mountain-dawn", "f59e0b", "f472b6", "Рассвет в горах"),
    "ink":    ("ink-bloom",    "eab308", "78716c", "Чернила и золото"),
    "nord":   ("nord-fjord",   "88c0d0", "5e81ac", "Северный фьорд"),
    "prism":  ("glass-prism",  "a78bfa", "38bdf8", "Стеклянная призма"),
    "flow":   ("aurora-flow",  "34d399", "22d3ee", "Поток сияния"),
    "mono":   ("mono-slate",   "94a3b8", "64748b", "Монохромный сланец"),
}

STATE = Path.home() / ".config" / "flyarchos" / "theme.json"
HYPR_THEME = Path.home() / ".config" / "hypr" / "theme.lua"


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def current() -> str | None:
    try:
        return json.loads(STATE.read_text(encoding="utf-8")).get("preset")
    except (OSError, ValueError):
        return None


def set_kde_accent(accent: str) -> None:
    rgb = ",".join(str(n) for n in hex_to_rgb(accent))
    if shutil.which("kwriteconfig6"):
        subprocess.run(["kwriteconfig6", "--file", "kdeglobals", "--group", "General",
                        "--key", "AccentColor", rgb], capture_output=True)
        return
    # Фолбэк: правим kdeglobals вручную (секция [General], ключ AccentColor)
    path = Path.home() / ".config" / "kdeglobals"
    try:
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    except OSError:
        lines = []
    out, section, done = [], "", False
    for line in lines:
        if line.startswith("[") and section == "General" and not done:
            out.append(f"AccentColor={rgb}")
            done = True
        if line.startswith("["):
            section = line.strip("[]")
        if section == "General" and line.startswith("AccentColor="):
            out.append(f"AccentColor={rgb}")
            done = True
            continue
        out.append(line)
    if not done:
        out += ["[General]", f"AccentColor={rgb}"] if section != "General" else [f"AccentColor={rgb}"]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    except OSError:
        pass


def apply_preset(name: str) -> int:
    if name not in PRESETS:
        print(f"нет пресета «{name}» — список: flyarchos-theme list", file=sys.stderr)
        return 2
    wallpaper, accent, accent2, _label = PRESETS[name]

    if shutil.which("flyarchos-wallpaper"):
        subprocess.run(["flyarchos-wallpaper", "set", wallpaper], capture_output=True)

    HYPR_THEME.parent.mkdir(parents=True, exist_ok=True)
    HYPR_THEME.write_text(
        "-- FlyArchOs — тема Hyprland (генерируется flyarchos-theme, не править руками)\n"
        f"-- пресет: {name}\n"
        "hl.config({\n"
        "    general = {\n"
        "        col = {\n"
        f"            active_border = {{ colors = {{ \"rgba({accent}ff)\", \"rgba({accent2}ff)\" }}, angle = 45 }},\n"
        "            inactive_border = \"rgba(24242faa)\",\n"
        "        },\n"
        "    },\n"
        "})\n",
        encoding="utf-8",
    )
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") and shutil.which("hyprctl"):
        subprocess.run(["hyprctl", "reload"], capture_output=True)

    set_kde_accent(accent)

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"preset": name, "wallpaper": wallpaper}, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    print(f"Тема «{name}» применена: обои {wallpaper}, акцент #{accent}")
    return 0


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    if action == "list":
        cur = current()
        for name, (wallpaper, accent, _a2, label) in PRESETS.items():
            mark = " ← сейчас" if name == cur else ""
            print(f"{name:<8} #{accent}  {label} (обои: {wallpaper}){mark}")
        return 0
    if action == "current":
        print(current() or "не выбран (тема по умолчанию)")
        return 0
    if action == "next":
        names = list(PRESETS)
        cur = current()
        nxt = names[(names.index(cur) + 1) % len(names)] if cur in names else names[0]
        return apply_preset(nxt)
    return apply_preset(action)


if __name__ == "__main__":
    raise SystemExit(main())
