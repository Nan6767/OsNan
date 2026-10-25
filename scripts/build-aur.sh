#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# FlyArchOs — сборка AUR-пакетов в локальный репозиторий repo/x86_64.
#
# После этого packages.x86_64 дополнится пакетами из groups/aur.txt, и они
# попадут внутрь ISO: установка останется полностью офлайн.
#
#   ./scripts/build-aur.sh                собрать всё из groups/aur.txt
#   ./scripts/build-aur.sh --with paru yay    собрать только перечисленное
#
# Требования: Arch Linux, package base-devel, git.
#              Если установлен devtools — сборка идёт в чистом chroot,
#              иначе — обычным makepkg в хостовой системе.
# ---------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$REPO_ROOT/repo/x86_64"
BUILD_DIR="${BUILD_DIR:-$REPO_ROOT/work/aur}"
AUR_LIST="$REPO_ROOT/groups/aur.txt"
DB_NAME="flyarchos.db.tar.gz"

log()  { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==> ПРЕДУПРЕЖДЕНИЕ:\033[0m %s\n' "$*" >&2; }

WITH=()
while [ $# -gt 0 ]; do
    case "$1" in
        --with) shift; while [ $# -gt 0 ] && [ "${1#--}" = "$1" ]; do WITH+=("$1"); shift; done ;;
        -h|--help) sed -n '3,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) warn "неизвестный аргумент: $1"; shift ;;
    esac
    shift 0
done

if [ ${#WITH[@]} -gt 0 ]; then
    PACKAGES=("${WITH[@]}")
else
    mapfile -t PACKAGES < <(grep -vE '^\s*(#|$)' "$AUR_LIST" | awk '{print $1}')
fi

[ ${#PACKAGES[@]} -gt 0 ] || { warn "список пакетов пуст"; exit 0; }

mkdir -p "$REPO_DIR" "$BUILD_DIR"

# Чистый chroot (devtools) надёжнее, но работает и обычный makepkg.
USE_CHROOT=0
if command -v extra-x86_64-build >/dev/null 2>&1 && [ -d /var/lib/archbuild/extra-x86_64 ]; then
    USE_CHROOT=1
    log "Сборка в чистом chroot (devtools)"
else
    warn "devtools не настроен — собираем makepkg в текущей системе (makepkg -s)"
fi

for pkg in "${PACKAGES[@]}"; do
    src="$BUILD_DIR/$pkg"
    if [ -d "$src/.git" ]; then
        log "$pkg: обновляю исходники"
        git -C "$src" pull --quiet --ff-only || warn "$pkg: не удалось обновить"
    else
        log "$pkg: клонирую AUR"
        rm -rf "$src"
        git clone --quiet --depth 1 "https://aur.archlinux.org/${pkg}.git" "$src" \
            || { warn "$pkg: не клонируется, пропускаю"; continue; }
    fi

    built=0
    (
        cd "$src"
        if [ "$USE_CHROOT" = "1" ]; then
            extra-x86_64-build -- -A --noconfirm || makepkg -s --noconfirm --skippgpcheck
        else
            makepkg -s --noconfirm --skippgpcheck --cleanbuild
        fi
    ) && built=1

    if [ "$built" = "1" ]; then
        found=$(ls -1 "$src"/*.pkg.tar.* 2>/dev/null | head -n1 || true)
        if [ -n "$found" ]; then
            mv -f "$src"/*.pkg.tar.* "$REPO_DIR/"
            log "$pkg: готово ($(basename "$found"))"
        else
            warn "$pkg: сборка прошла, но пакет не найден"
        fi
    else
        warn "$pkg: сборка не удалась — пакет не попадёт в ISO"
    fi
done

log "Обновляю базу репозитория"
shopt -s nullglob
files=("$REPO_DIR"/*.pkg.tar.*)
if [ ${#files[@]} -eq 0 ]; then
    warn "в $REPO_DIR нет пакетов"
    exit 1
fi
repo-add -q "$REPO_DIR/$DB_NAME" "${files[@]}"

log "Локальный репозиторий: $REPO_DIR (${#files[@]} пакетов)"
log "Дальше: ./scripts/build-iso.sh --aur"
