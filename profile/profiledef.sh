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
iso_version="1.3.0-beta"
install_dir="arch"
buildmodes=('iso')
# Режимы загрузки берутся от releng-профиля archiso:
# BIOS через syslinux, UEFI через systemd-boot. Если ваша версия archiso
# использует GRUB — scripts/build-iso.sh подставит поддерживаемый список сам.
bootmodes=('bios.syslinux' 'uefi.systemd-boot')
arch="x86_64"
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '19' '-b' '1M' '-noappend')

# Права доступа на чувствительные файлы внутри образа (пользователь fly = 1000)
# ВАЖНО: здесь только те пути, которые УЖЕ лежат в airootfs/ на момент
# копирования дерева. mkarchiso падает, если пути нет или он вне airootfs.
# Права на /home/fly, /etc/sudoers.d/10-flyarchos-live и symlink'и в /usr/bin
# выставляет profile/customize_airootfs.sh — они создаются уже в chroot.
file_permissions=(
    ["/etc/shadow"]="0:0:400"
    ["/etc/gshadow"]="0:0:400"
    ["/etc/sudoers.d"]="0:0:750"
    ["/usr/bin/flyarchos-profile"]="0:0:755"
    ["/usr/bin/flyarchos-wallpaper"]="0:0:755"
    ["/usr/bin/flyarchos-wallpaper-gen"]="0:0:755"
    ["/usr/bin/flyarchos-welcome"]="0:0:755"
    ["/usr/bin/flyarchos-info"]="0:0:755"
    ["/usr/bin/flyarchos-install"]="0:0:755"
    ["/usr/bin/flyarchos-update"]="0:0:755"
    ["/usr/bin/flyarchos-doctor"]="0:0:755"
    ["/usr/bin/flyarchos-theme"]="0:0:755"
    ["/usr/bin/flyarchos-snapshot"]="0:0:755"
    ["/usr/bin/flyarchos-backup"]="0:0:755"
    ["/usr/bin/flyarchos-clean"]="0:0:755"
    ["/usr/bin/flyarchos-aur"]="0:0:755"
    ["/usr/lib/flyarchos/profile_tool.py"]="0:0:755"
    ["/usr/lib/flyarchos/wallpapers.py"]="0:0:755"
    ["/usr/lib/flyarchos/wallpaper_tool.py"]="0:0:755"
    ["/usr/lib/flyarchos/welcome-gui.py"]="0:0:755"
    ["/usr/lib/flyarchos/install-prepare.sh"]="0:0:755"
    ["/usr/lib/flyarchos/install-finalize.sh"]="0:0:755"
    ["/usr/lib/flyarchos/backup_tool.py"]="0:0:755"
    ["/usr/lib/flyarchos/flyarchos-clean"]="0:0:755"
    ["/usr/lib/flyarchos/flyarchos-aur"]="0:0:755"
)
