#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# FlyArchOs — сборка ISO.
#
#   ./scripts/build-iso.sh                 обычная сборка (полный профиль)
#   ./scripts/build-iso.sh --profile slim   компактный образ: оба окружения без доп. наборов
#   ./scripts/build-iso.sh --aur      сначала собрать AUR-пакеты в локальный репозиторий
#   ./scripts/build-iso.sh --clean    очистить рабочие каталоги перед сборкой
#   ./scripts/build-iso.sh --check    только проверить окружение
#
# Требования: Arch Linux (или контейнер archlinux:latest), пакет archiso,
#             ~40 ГБ свободного места, root (или sudo).
# ---------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="$REPO_ROOT/profile"
WORK="${WORK:-$REPO_ROOT/work}"
OUT="${OUT:-$REPO_ROOT/out}"
REPO_DIR="$REPO_ROOT/repo/x86_64"
RELENG="/usr/share/archiso/configs/releng"

AUR=0
CLEAN=0
ONLY_CHECK=0
VERBOSE="-v"
PROFILE_NAME="full"
SLIM_GROUPS="core,common,hyprland,plasma,apps,live"

log()  { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==> ПРЕДУПРЕЖДЕНИЕ:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m==> ОШИБКА:\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
    sed -n '3,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --aur)        AUR=1 ;;
        --profile)    shift; PROFILE_NAME="${1:-full}" ;;
        --profile=*)  PROFILE_NAME="${1#*=}" ;;
        --clean)      CLEAN=1 ;;
        --check)      ONLY_CHECK=1 ;;
        -q|--quiet)   VERBOSE="" ;;
        -h|--help)    usage; exit 0 ;;
        *)            die "неизвестный аргумент: $1 (см. --help)" ;;
    esac
    shift
done

# --- 0. права root ---------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        log "Перезапуск под sudo…"
        exec sudo --preserve-env=WORK,OUT "$0" "$@"
    fi
    die "mkarchiso требует root (нужен sudo)."
fi

# --- 1. окружение ----------------------------------------------------------
check_env() {
    local missing=0
    command -v mkarchiso >/dev/null 2>&1 || { warn "не установлен пакет archiso (pacman -S archiso)"; missing=1; }
    [ -d "$RELENG" ] || warn "нет $RELENG — файлы загрузчика возьмутся из профиля (должны быть там)"
    command -v python3 >/dev/null 2>&1 || { warn "нет python3"; missing=1; }
    [ "$(uname -m)" = "x86_64" ] || { warn "сборка рассчитана на x86_64"; missing=1; }
    local free
    free=$(df -Pk "$REPO_ROOT" | awk 'NR==2 {print int($4/1024/1024)}')
    [ "$free" -ge 30 ] || warn "свободно ${free} ГБ — для «жирного» образа желательно 40+ ГБ"
    return $missing
}

log "Проверка окружения"
if ! check_env; then
    die "окружение не готово (см. предупреждения выше)"
fi
[ "$ONLY_CHECK" = "1" ] && { log "Окружение в порядке."; exit 0; }

# --- 2. локальный репозиторий AUR (по желанию) -----------------------------
# ВАЖНО: собираем ДО генерации списка — packages.aux формируется по факту
# наличия пакетов в repo/x86_64.
if [ "$AUR" = "1" ]; then
    log "Сборка AUR-пакетов в локальный репозиторий"
    "$REPO_ROOT/scripts/build-aur.sh" || warn "AUR-пакеты собраны не полностью — ISO соберётся без них"
fi
if [ -n "${AUR_ONLY:-}" ]; then
    log "Сборка AUR-пакетов (выборочно): $AUR_ONLY"
    # shellcheck disable=SC2086
    "$REPO_ROOT/scripts/build-aur.sh" --with $AUR_ONLY || warn "AUR-пакеты собраны не полностью — ISO соберётся без них"
fi

# --- 3. список пакетов -----------------------------------------------------
log "Генерация списка пакетов из groups/ (профиль: $PROFILE_NAME)"
GEN_ARGS=()
if [ "$PROFILE_NAME" = "slim" ]; then
    GEN_ARGS=(--only-groups "$SLIM_GROUPS")
fi
if [ -n "${EXCLUDE_PKGS:-}" ]; then
    GEN_ARGS+=(--exclude "$EXCLUDE_PKGS")
fi
python3 "$REPO_ROOT/scripts/gen-packages.py" --stats "${GEN_ARGS[@]}" | sed 's/^/    /'
python3 "$REPO_ROOT/scripts/gen-packages.py" "${GEN_ARGS[@]}"

if ! grep -q '^calamares$' profile/packages.x86_64 profile/packages.aux 2>/dev/null; then
    warn "Calamares не попал в образ (нет в репозиториях или не собран из AUR) — установщика в ISO не будет"
fi

# --- 4. рабочий профиль ----------------------------------------------------
if [ "$CLEAN" = "1" ]; then
    log "Очистка $WORK"
    rm -rf "$WORK"
fi
mkdir -p "$WORK" "$OUT"

log "Подготовка рабочего профиля в $WORK/profile"
rm -rf "$WORK/profile"
cp -a "$PROFILE" "$WORK/profile"

# описания групп нужны и установщику (внутри образа)
mkdir -p "$WORK/profile/airootfs/usr/share/flyarchos/groups"
cp -a "$REPO_ROOT"/groups/[0-9][0-9]-*.txt "$WORK/profile/airootfs/usr/share/flyarchos/groups/"

# --- 5. pacman.conf --------------------------------------------------------
log "pacman.conf"
if [ -f "$REPO_DIR/flyarchos.db" ]; then
    REPO_LINE="[flyarchos]
SigLevel = Optional TrustAll
Server = file://$REPO_DIR"
    log "  локальный репозиторий: $REPO_DIR"
else
    REPO_LINE="# локальный репозиторий не собран (см. scripts/build-aur.sh)"
fi
python3 - "$WORK/profile/pacman.conf.in" "$WORK/profile/pacman.conf" "$REPO_LINE" <<'PY'
import sys
src, dst, repo_line = sys.argv[1:4]
text = open(src, encoding="utf-8").read().replace("@FLYARCHOS_REPO@", repo_line)
open(dst, "w", encoding="utf-8").write(text)
PY

# --- 6. файлы загрузчика из releng ----------------------------------------
RELBUILT=0
for dir in efiboot syslinux grub isolinux; do
    if [ ! -d "$WORK/profile/$dir" ] && [ -d "$RELENG/$dir" ]; then
        log "  копирую $dir/ из $(basename "$RELENG")"
        cp -a "$RELENG/$dir" "$WORK/profile/$dir"
        RELBUILT=1
    fi
done

# --- 7. режимы загрузки ----------------------------------------------------
# Если загрузчик взят из releng, берём оттуда же и поддерживаемые bootmodes —
# так профиль не сломается на другой версии archiso.
if [ "$RELBUILT" = "1" ] && [ -f "$RELENG/profiledef.sh" ]; then
    RELENG_BOOTMODES=$(bash -c "unset bootmodes; . '$RELENG/profiledef.sh' >/dev/null 2>&1 || true; printf \"'%s' \" \"\${bootmodes[@]}\"" || true)
    if [ -n "${RELENG_BOOTMODES// /}" ]; then
        log "  bootmodes из releng: ${RELENG_BOOTMODES}"
        python3 - "$WORK/profile/profiledef.sh" "$RELENG_BOOTMODES" <<'PY'
import re, sys
path, modes = sys.argv[1], sys.argv[2].strip()
text = open(path, encoding="utf-8").read()
text = re.sub(r"bootmodes=\([^)]*\)", f"bootmodes=({modes})", text, count=1, flags=re.S)
open(path, "w", encoding="utf-8").write(text)
PY
    fi
fi

# --- 7b. slim: скрываем в установщике наборы, которых нет в образе --------
if [ "$PROFILE_NAME" = "slim" ]; then
    log "Профиль slim: убираем страницу «Наборы ПО» из установщика"
    python3 - "$WORK/profile/airootfs/etc/calamares/settings.conf" <<'PY'
import re, sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
text = re.sub(r"^[ \t]*- packagechooser@extras\n", "", text, flags=re.M)
open(path, "w", encoding="utf-8").write(text)
PY
    echo "slim" > "$WORK/profile/airootfs/usr/share/flyarchos/profile-variant"
fi

# --- 8. проверка дерева ----------------------------------------------------
log "Проверка дерева (scripts/check.py)"
python3 "$REPO_ROOT/scripts/check.py" || warn "проверка нашла замечания — смотрите вывод выше"

# --- 9. сборка -------------------------------------------------------------
log "Запуск mkarchiso (это надолго: ставится ~700 пакетов)"
start=$(date +%s)
mkarchiso $VERBOSE -w "$WORK" -o "$OUT" "$WORK/profile"

iso=$(ls -1t "$OUT"/*.iso 2>/dev/null | head -n1 || true)
[ -n "$iso" ] || die "mkarchiso не создал ISO (проверьте вывод выше)"
elapsed=$(( $(date +%s) - start ))

log "Готово за $((elapsed / 60)) мин $((elapsed % 60)) с"
ls -lh "$iso"
(
    cd "$OUT"
    sha256sum "$(basename "$iso")" > "$(basename "$iso").sha256"
    log "Контрольная сумма: $(cat "$(basename "$iso").sha256")"
)
log "Записать на флешку:  sudo dd if=$iso of=/dev/sdX bs=4M status=progress oflag=sync"
log "Или:                 ventoy / balenaEtcher"
