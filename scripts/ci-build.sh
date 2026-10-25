#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# FlyArchOs — сборка ISO внутри контейнера archlinux.
# Используется GitHub Actions (см. .github/workflows/iso.yml), но подходит и
# для любого места, где есть Docker:
#
#   docker run --rm -it --privileged -v "$PWD:/flyarchos" -w /flyarchos \
#       archlinux:latest ./scripts/ci-build.sh slim
#
# Аргументы:
#   $1 — профиль: slim (по умолчанию) или full;
#   $2 — "--aur", если перед сборкой нужно собрать AUR-пакеты.
# ---------------------------------------------------------------------------
set -euo pipefail

PROFILE_NAME="${1:-slim}"
WITH_AUR="${2:-}"
cd "$(dirname "${BASH_SOURCE[0]}")/.."

log()  { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==> ПРЕДУПРЕЖДЕНИЕ:\033[0m %s\n' "$*" >&2; }

log "Профиль сборки: $PROFILE_NAME"
df -h / | tail -1

log "Обновление ключей и установка инструментов сборки"
pacman -Sy --noconfirm --needed archlinux-keyring
pacman -Syu --noconfirm --needed \
    archiso \
    git \
    python \
    python-yaml \
    squashfs-tools \
    libisoburn \
    mtools \
    dosfstools \
    grub \
    efibootmgr \
    rsync

pacman-key --init
pacman-key --populate archlinux

log "Проверка дерева"
python scripts/check.py || warn "проверка выдала замечания — продолжаем"

if [ "$WITH_AUR" = "--aur" ]; then
    log "Сборка AUR-пакетов"
    ./scripts/build-aur.sh || warn "AUR собран частично — продолжаем без него"
fi

log "Сборка ISO"
./scripts/build-iso.sh --clean --profile "$PROFILE_NAME"

log "Результат"
ls -lh out/
test -f out/*.sha256 && cat out/*.sha256
