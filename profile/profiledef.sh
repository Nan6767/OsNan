#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# FlyArchOs — описание archiso-профиля.
# Этот файл читает mkarchiso (см. scripts/build-iso.sh).
# ---------------------------------------------------------------------------
# shellcheck shell=bash

iso_name="flyarchos"
iso_label="FLYARCHOS_$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y%m)"
iso_publisher="FlyArchOs <https://github.com/Nan6767/OsNan>"
iso_application="FlyArchOs Linux - Arch-based live/installable ISO (Hyprland + KDE Plasma)"
iso_version="1.0.0"
install_dir="arch"
buildmodes=('iso')
# Режимы загрузки берутся от releng-профиля archiso:
# BIOS через syslinux, UEFI через systemd-boot. Если ваша версия archiso
# использует GRUB — scripts/build-iso.sh подставит поддерживаемый список сам.
bootmodes=('bios.syslinux.mbr' 'bios.syslinux.eltorito' \
           'uefi-x64.systemd-boot.esp' 'uefi-x64.systemd-boot.eltorito')
arch="x86_64"
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '19' '-b' '1M' '-noappend')

# Права доступа на чувствительные файлы внутри образа (пользователь fly = 1000)
file_permissions=(
    ["/etc/shadow"]="0:0:400"
    ["/etc/gshadow"]="0:0:400"
    ["/etc/sudoers"]="0:0:440"
    ["/etc/sudoers.d"]="0:0:750"
    ["/etc/sudoers.d/10-flyarchos-live"]="0:0:440"
    ["/root"]="0:0:750"
    ["/home/fly"]="1000:1000:750"
    ["/home/fly/.config"]="1000:1000:700"
    ["/usr/bin/flyarchos-profile"]="0:0:755"
    ["/usr/bin/flyarchos-wallpaper"]="0:0:755"
    ["/usr/bin/flyarchos-wallpaper-gen"]="0:0:755"
    ["/usr/bin/flyarchos-welcome"]="0:0:755"
    ["/usr/bin/flyarchos-info"]="0:0:755"
    ["/usr/bin/flyarchos-install"]="0:0:755"
    ["/usr/lib/flyarchos/profile_tool.py"]="0:0:755"
    ["/usr/lib/flyarchos/wallpaper_tool.py"]="0:0:755"
    ["/usr/lib/flyarchos/welcome.py"]="0:0:755"
    ["/usr/lib/flyarchos/welcome-gui.py"]="0:0:755"
)
