#!/usr/bin/env python3
"""Static checks for NanOs Kali live-build inputs (no external modules)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NANOS = ROOT / "nanos" / "kali-config"
VARIANT = NANOS / "variant-nanos"
COMMON = NANOS / "common"
VERSION_FILE = ROOT / "VERSION"
checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, details: str = "") -> None:
    checks.append((name, bool(ok), details))


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def packages_from(path: Path) -> set[str]:
    return {
        line.strip().split()[0]
        for line in read(path).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def main() -> int:
    version = read(VERSION_FILE).strip()
    package_file = VARIANT / "package-lists" / "kali.list.chroot"
    packages = packages_from(package_file)
    os_release = read(COMMON / "includes.chroot" / "usr/lib/os-release")
    hypr_conf = COMMON / "includes.chroot" / "etc/skel/.config/hypr/hyprland.conf"
    hypr_lua = COMMON / "includes.chroot" / "etc/skel/.config/hypr/hyprland.lua"
    profile = COMMON / "includes.chroot" / "etc/skel/.profile"
    zprofile = COMMON / "includes.chroot" / "etc/skel/.zprofile"
    bash_profile = COMMON / "includes.chroot" / "etc/skel/.bash_profile"
    getty = COMMON / "includes.chroot" / "etc/systemd/system/getty@tty1.service.d/nanos-autologin.conf"
    waybar_config = COMMON / "includes.chroot" / "etc/skel/.config/waybar/config"
    hook = COMMON / "hooks/live/9950-nanos-live-setup.chroot"

    check("VERSION is 0.0.1-alpha", version == "0.0.1-alpha", version or "missing")
    check("Kali live package list exists", package_file.is_file())
    required = {
        "kali-linux-core", "kali-desktop-live", "kali-archive-keyring", "hyprland",
        "hyprland-qtutils", "xwayland", "waybar", "wofi", "foot", "mako-notifier", "swaybg",
        "xdg-desktop-portal-hyprland", "network-manager", "network-manager-applet",
        "nm-connection-editor", "virtualbox-guest-utils", "zsh",
    }
    missing = sorted(required - packages)
    check("minimal base + Hyprland + VirtualBox packages", not missing, ", ".join(missing))

    forbidden = {
        "kali-linux-default", "kali-linux-large", "kali-linux-everything",
        "kali-desktop-gnome", "kali-desktop-kde", "kali-desktop-xfce",
        "kali-desktop-mate", "kali-desktop-lxde", "kali-desktop-e17",
        "kali-desktop-i3", "plasma-desktop", "plasma-workspace", "gnome-shell",
        "xfce4", "sway", "i3-wm",
    }
    conflicts = sorted(packages & forbidden)
    check("exactly one desktop (Hyprland; no second DE/WM)", not conflicts, ", ".join(conflicts))
    check("NanOs name/version in os-release", all(token in os_release for token in (
        'NAME="NanOs"', 'PRETTY_NAME="NanOs 0.0.1-alpha"',
        'ID=kali', 'VARIANT_ID=nanos', 'VERSION_ID="0.0.1-alpha"',
    )))

    conf_text = read(hypr_conf)
    check("Hyprland.conf includes live bindings", all(token in conf_text for token in (
        "monitor = , preferred", "exec-once = waybar", "exec-once = swaybg",
        "$mainMod, RETURN, exec", "$mainMod, D, exec", "animations {",
    )))
    lua_text = read(hypr_lua)
    check("Lua fallback exists for a rolling Hyprland update", all(token in lua_text for token in (
        "hl.monitor({", 'hl.on("hyprland.start"', 'hl.bind(mod .. " + RETURN"',
        "new_render_scheduling = false", "dbus-update-activation-environment",
    )))

    profile_text = read(profile)
    zprofile_text = read(zprofile)
    bash_profile_text = read(bash_profile)
    getty_text = read(getty)
    bash_direct_launch = any(line.strip() in {"Hyprland", "dbus-run-session -- Hyprland"}
                             for line in profile_text.splitlines())
    zsh_direct_launch = any(line.strip() in {"Hyprland", "dbus-run-session -- Hyprland"}
                            for line in zprofile_text.splitlines())
    check("Bash login autostarts only on tty1 via start-hyprland", all(token in profile_text for token in (
        '"/dev/tty1"', "command -v start-hyprland", "start-hyprland",
    )) and not bash_direct_launch)
    check("Zsh login autostarts only on tty1 via start-hyprland", all(token in zprofile_text for token in (
        "[[ -o interactive ]]", '"/dev/tty1"', "command -v start-hyprland", "start-hyprland",
    )) and not zsh_direct_launch)
    check("bash login sources live profile", '. "$HOME/.profile"' in bash_profile_text)
    check("tty1 autologin uses Kali live user", "--autologin kali" in getty_text and "agetty" in getty_text)

    try:
        json.loads(read(waybar_config))
        waybar_ok, waybar_error = True, ""
    except json.JSONDecodeError as exc:
        waybar_ok, waybar_error = False, str(exc)
    check("Waybar config is valid JSON", waybar_ok, waybar_error)

    hook_text = read(hook)
    executable = hook.is_file() and bool(hook.stat().st_mode & 0o111)
    check("live setup hook exists and is executable", executable)
    check("live setup hook enables NetworkManager and tty1", "NetworkManager.service" in hook_text and "getty@tty1.service" in hook_text)
    no_legacy = not any(word in "\n".join((read(package_file), conf_text, lua_text, hook_text))
                        for word in ("packagechooser", "[flyarchos]", "mkarchiso", "plasma-meta"))
    check("new build inputs contain no old installer/Arch pipeline", no_legacy)

    errors = 0
    for name, ok, details in checks:
        suffix = f" — {details}" if details else ""
        print(f"[{'OK' if ok else 'FAIL'}] {name}{suffix}")
        errors += not ok
    print(f"\n{len(checks) - errors}/{len(checks)} checks passed")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
