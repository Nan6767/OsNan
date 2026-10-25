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
set -uo pipefail

PROFILE_NAME="${1:-slim}"
WITH_AUR="${2:-}"
BUILD_PACKAGES="archiso git python python-yaml squashfs-tools libisoburn mtools dosfstools grub efibootmgr rsync"

log()  { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==> ПРЕДУПРЕЖДЕНИЕ:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m==> ОШИБКА:\033[0m %s\n' "$*" >&2; exit 1; }

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1

log "Профиль сборки: $PROFILE_NAME"
echo "  kernel:  $(uname -a)"
echo "  root:    $(id -u)"
df -h / | tail -1

# --------------------------------------------------------------------------- #
# Ключи pacman. В образах archlinux:latest связка ключей часто просрочена,
# поэтому сначала пробуем честно, а при ошибке — обновляем ключи без проверки
# подписей (и сразу возвращаем проверку на место).
# --------------------------------------------------------------------------- #
fix_keys() {
    warn "обновляем связку ключей без проверки подписей"
    cp -f /etc/pacman.conf /tmp/pacman.conf.orig
    sed -i 's/^SigLevel.*/SigLevel = Never/; s/^LocalFileSigLevel.*/LocalFileSigLevel = Never/; s/^RemoteFileSigLevel.*/RemoteFileSigLevel = Never/' /etc/pacman.conf
    pacman -Sy --noconfirm archlinux-keyring || true
    pacman -Su --noconfirm --needed archlinux-keyring || true
    cp -f /tmp/pacman.conf.orig /etc/pacman.conf
    rm -rf /etc/pacman.d/gnupg
    pacman-key --init
    pacman-key --populate archlinux
}

install_packages() {
    if pacman -Sy --noconfirm --needed "$@"; then
        return 0
    fi
    warn "pacman не смог поставить пакеты — чиним ключи и пробуем снова"
    fix_keys
    pacman -Sy --noconfirm --needed "$@"
}

log "Обновление ключей и установка инструментов сборки"
echo "  pacman: $(pacman -V 2>&1 | head -1)"
echo "  образ:  $(cat /etc/os-release 2>/dev/null | grep -m1 PRETTY_NAME || echo '?')"
pacman-key --init 2>&1 | tail -2
pacman-key --populate archlinux 2>&1 | tail -2

# Полное обновление: в старом контейнере установка новых пакетов поверх
# старых библиотек приводит к частичному обновлению и ошибкам.
install_packages --noconfirm -Syu $BUILD_PACKAGES || {
    warn "повторяем установку после полного обновления системы"
    pacman -Syu --noconfirm || fix_keys
    install_packages $BUILD_PACKAGES || die "не удалось установить инструменты сборки"
}
command -v mkarchiso >/dev/null || die "mkarchiso не установлен"
echo "  archiso: $(pacman -Qi archiso 2>/dev/null | awk '/^Version/{print $3}' || echo '?')"

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
for sum in out/*.sha256; do
    [ -f "$sum" ] && cat "$sum"
done
