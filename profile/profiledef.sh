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
iso_version="1.7.0-beta"
install_dir="arch"
buildmodes=('iso')
# Режимы загрузки берутся от releng-профиля archiso:
# BIOS через syslinux, UEFI через GRUB: GRUB грузит ядро и initramfs
# прямо с ISO9660, а systemd-boot требует вторую копию внутри
# EFI-раздела — с полным initramfs (+200 МБ) mini не влезает в лимит
# GitHub 2 ГиБ одним файлом. Если ваша версия archiso
# использует GRUB — scripts/build-iso.sh подставит поддерживаемый список сам.
bootmodes=('bios.syslinux' 'uefi.grub')
arch="x86_64"
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '19' '-b' '1M' '-noappend')

# Права доступа на чувствительные файлы внутри образа (пользователь fly = 1000).
# mkarchiso применяет их к готовому дереву после установки пакетов.
# Live-настройка образа — статичные файлы airootfs/ + pacman-хук
# flyarchos-live-setup (customize_airootfs.sh archiso 91+ не выполняет).
file_permissions=(
    ["/etc/shadow"]="0:0:400"
    ["/etc/gshadow"]="0:0:400"
    ["/etc/sudoers.d"]="0:0:750"
    ["/etc/sudoers.d/10-flyarchos-live"]="0:0:440"
    ["/root"]="0:0:700"
    ["/home/fly"]="1000:1000:0700"
    ["/usr/lib/flyarchos/live-setup.sh"]="0:0:755"
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
    ["/usr/bin/flyarchos-exe"]="0:0:755"
    ["/usr/bin/flyarchos-performance"]="0:0:755"
    ["/usr/lib/flyarchos/profile_tool.py"]="0:0:755"
    ["/usr/lib/flyarchos/wallpapers.py"]="0:0:755"
    ["/usr/lib/flyarchos/wallpaper_tool.py"]="0:0:755"
    ["/usr/lib/flyarchos/welcome-gui.py"]="0:0:755"
    ["/usr/lib/flyarchos/install-prepare.sh"]="0:0:755"
    ["/usr/lib/flyarchos/install-finalize.sh"]="0:0:755"
    ["/usr/lib/flyarchos/backup_tool.py"]="0:0:755"
    ["/usr/lib/flyarchos/flyarchos-clean"]="0:0:755"
    ["/usr/lib/flyarchos/flyarchos-aur"]="0:0:755"
    ["/usr/lib/flyarchos/flyarchos-exe"]="0:0:755"
    ["/usr/lib/flyarchos/flyarchos-performance"]="0:0:755"
    ["/usr/lib/flyarchos/doctor_tool.py"]="0:0:755"
    ["/usr/lib/flyarchos/theme_tool.py"]="0:0:755"
    ["/usr/lib/flyarchos/flyarchos-info"]="0:0:755"
    ["/usr/lib/flyarchos/flyarchos-install"]="0:0:755"
    ["/usr/lib/flyarchos/flyarchos-snapshot"]="0:0:755"
    ["/usr/lib/flyarchos/flyarchos-update"]="0:0:755"
)
