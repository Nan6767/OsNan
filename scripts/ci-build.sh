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
BUILD_PACKAGES="archiso git python python-yaml squashfs-tools libisoburn mtools dosfstools grub efibootmgr rsync lua"

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

# multilib нужен и для предпроверки имён (steam, lib32-*), и для самой сборки
if ! grep -q '^\[multilib\]' /etc/pacman.conf; then
    log "Включаю multilib в /etc/pacman.conf"
    sed -i '/^#\[multilib\]/,+1 s/^#//' /etc/pacman.conf
fi

# base-devel + sudo: сборка AUR-пакетов (Calamares) идёт под пользователем builder
BUILD_PACKAGES="$BUILD_PACKAGES base-devel sudo"

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
# Синтаксис Lua-конфига Hyprland: одна опечатка — и сессия без автозапуска.
luac -p profile/airootfs/etc/skel/.config/hypr/hyprland.lua \
        profile/airootfs/etc/skel/.config/hypr/theme.lua || die "синтаксис Hyprland Lua сломан"

if [ "$WITH_AUR" = "--aur" ]; then
    log "Сборка AUR-пакетов"
    ./scripts/build-aur.sh || warn "AUR собран частично — продолжаем без него"
fi

# Проверяем имена пакетов по конфигурации самого профиля (в ней включён
# multilib) — иначе steam и lib32-* «не находятся» только из-за /etc/pacman.conf
# контейнера, а на самом деле в образ ставятся нормально.
python3 - profile/pacman.conf.in /tmp/check-pacman.conf <<'PY'
import sys
src, dst = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8").read().replace("@FLYARCHOS_REPO@", "")
open(dst, "w", encoding="utf-8").write(text)
PY
pacman -Sy --config /tmp/check-pacman.conf --noconfirm >/dev/null \
    || warn "не удалось обновить базы пакманов"
for repo in core extra multilib; do
    pacman -Sl --config /tmp/check-pacman.conf "$repo" >/dev/null 2>&1 \
        || warn "база $repo недоступна — часть пакетов не найдётся"
done

GEN_ARGS=(--profile "$PROFILE_NAME")

# Быстрая проверка: все ли имена пакетов находятся в репозиториях.
# Так ошибку в groups/*.txt видно за секунды, а не через час pacstrap-а.
log "Предпроверка имён пакетов (profile/packages.x86_64)"
python3 scripts/gen-packages.py "${GEN_ARGS[@]}" >/dev/null
mapfile -t PKGS < <(grep -vE '^\s*(#|$)' profile/packages.x86_64)
if ! pacman -S --config /tmp/check-pacman.conf --print-format '%n' --noconfirm "${PKGS[@]}" >/tmp/pkgcheck.out 2>/tmp/pkgcheck.err; then
    mapfile -t MISSING < <(grep -oE "target not found: [^ ]+" /tmp/pkgcheck.err | awk '{print $NF}' | sort -u)
    warn "не найдено в репозиториях: ${MISSING[*]}"
    for name in "${MISSING[@]}"; do
        echo -n "  $name → похожие: "
        pacman -Ssq --config /tmp/check-pacman.conf "$name" 2>/dev/null | head -20 | tr '\n' ' '
        echo
    done
    # Не падаем: собираем ISO без этих пакетов, а в groups/*.txt поправим потом.
    export EXCLUDE_PKGS="$(IFS=,; echo "${MISSING[*]}")"
    warn "собираю БЕЗ: $EXCLUDE_PKGS (поправьте groups/*.txt)"
fi
echo "  пакетов к установке: ${#PKGS[@]}${EXCLUDE_PKGS:+ (кроме: $EXCLUDE_PKGS)}"

# Calamares — установщик FlyArchOs — есть только в AUR. Собираем его в
# локальный репозиторий; если не получится, ISO соберётся без установщика.
log "Сборка Calamares из AUR"
if ! ./scripts/build-aur.sh --with calamares; then
    warn "Calamares не собрался — ISO будет без графического установщика"
fi

log "Сборка ISO"
./scripts/build-iso.sh --clean --profile "$PROFILE_NAME"

# Контроль готового образа: live-сессия обязана существовать
# (пользователь fly, пароль, дисплей-менеджер, брендинг, локаль).
# Лучше упасть здесь, чем опубликовать непригодный ISO.
log "Проверка содержимого образа"
SFS="$(find work -name airootfs.sfs 2>/dev/null | head -1)"
if [ -z "$SFS" ]; then
    xorriso -osirrox on -indev out/*.iso -extract /arch/x86_64/airootfs.sfs /tmp/airootfs.sfs >/dev/null 2>&1 || true
    SFS=/tmp/airootfs.sfs
fi
fail_iso() { echo "ОШИБКА ОБРАЗА: $1"; exit 1; }
sfs_cat() { unsquashfs -cat "$SFS" "$1" 2>/dev/null; }
# grep без флага -q: читает поток до конца. С -q он закрывает трубу на
# первом совпадении, unsquashfs получает SIGPIPE, и при pipefail вся
# проверка падает, хотя совпадение было (так падала проверка локали).
sfs_grep() { sfs_cat "$1" | grep -ai "$2" >/dev/null 2>&1; }
sfs_grep /etc/passwd '^fly:' || fail_iso "нет пользователя fly в /etc/passwd"
sfs_grep /etc/shadow '^fly:$' && fail_iso "у fly пустой пароль в /etc/shadow"
sfs_grep /etc/shadow '^fly:\$' || fail_iso "у fly не задан пароль в /etc/shadow"
sfs_grep /usr/lib/os-release 'FlyArchOs' || fail_iso "os-release не брендирован (хук live-setup не сработал)"
if ! sfs_grep /usr/lib/locale/locale-archive 'ru_RU'; then
    echo "--- диагностика локалей в образе ---"
    unsquashfs -l "$SFS" /usr/lib/locale 2>&1 | head -30
    sfs_cat /usr/lib/locale/locale-archive | strings | head -20
    fail_iso "локаль ru_RU не сгенерирована"
fi
unsquashfs -l "$SFS" /etc/systemd/system/display-manager.service >/dev/null 2>&1 || fail_iso "нет display-manager.service (SDDM не включён)"
unsquashfs -l "$SFS" /home/fly >/dev/null 2>&1 || fail_iso "нет домашнего каталога /home/fly"
# Права на исполнение инструментов: оверлей теряет +x без file_permissions,
# а симлинки /usr/bin/flyarchos-* тогда ведут в Permission denied.
for tool in profile_tool.py wallpaper_tool.py wallpapers.py welcome-gui.py \
            doctor_tool.py theme_tool.py backup_tool.py \
            flyarchos-info flyarchos-install flyarchos-update flyarchos-snapshot \
            flyarchos-clean flyarchos-aur flyarchos-exe \
            install-prepare.sh install-finalize.sh live-setup.sh; do
    line="$(unsquashfs -ll "$SFS" "/usr/lib/flyarchos/$tool" 2>/dev/null | grep -a "$tool" | head -1)"
    case "$line" in
        -rwx*) : ;;
        *) fail_iso "нет права на исполнение: /usr/lib/flyarchos/$tool" ;;
    esac
done
# fly состоит в wheel — иначе в live мертвы sudo и запуск установщика
sfs_grep /etc/group '^wheel:.*fly' || fail_iso "fly не входит в группу wheel"
# Автологин SDDM настроен на fly
sfs_grep /etc/sddm.conf.d/zz-live-autologin.conf 'User=fly' || fail_iso "нет автологина SDDM (User=fly)"
# Образы ядер для prepare (он копирует их в /boot целевой системы)
unsquashfs -l "$SFS" /usr/lib/modules 2>/dev/null | grep -a '/vmlinuz' >/dev/null 2>&1 || fail_iso "нет /usr/lib/modules/*/vmlinuz"
# В образе не должно быть приватных ключей pacman сборочного хоста
if unsquashfs -l "$SFS" /etc/pacman.d/gnupg 2>/dev/null | grep -ai 'private-keys' >/dev/null 2>&1; then
    fail_iso "в образе приватные ключи pacman сборочного хоста"
fi
unsquashfs -l "$SFS" /etc/systemd/system/multi-user.target.wants/pacman-init.service >/dev/null 2>&1 || fail_iso "pacman-init.service не включён"
# Вложенные конфиги домашнего каталога принадлежат fly (1000), а не root
rm -rf /tmp/homeprobe
unsquashfs -q -d /tmp/homeprobe "$SFS" /home/fly/.config/hypr/hyprland.lua >/dev/null 2>&1 || true
homeuid="$(stat -c %u /tmp/homeprobe/home/fly/.config/hypr/hyprland.lua 2>/dev/null || echo '?')"
[ "$homeuid" = "1000" ] || fail_iso "конфиги в /home/fly принадлежат uid=$homeuid, а не 1000"
# Демон обоев Hyprland
unsquashfs -l "$SFS" /usr/bin/awww >/dev/null 2>&1 || fail_iso "нет /usr/bin/awww (обои Hyprland)"
# Установщик и модуль выбора наборов физически на месте (AUR-PKGBUILD
# пропускает packagechooser — build-aur.sh снимает пропуск, здесь контроль)
unsquashfs -l "$SFS" /usr/bin/calamares >/dev/null 2>&1 || fail_iso "нет /usr/bin/calamares (установщик)"
unsquashfs -l "$SFS" /usr/lib/calamares/modules/packagechooser >/dev/null 2>&1 || fail_iso "нет модуля packagechooser (страницы выбора в установщике)"

# Hyprland 0.57+ читает только Lua-конфиг. Legacy hyprland.conf в домашнем
# каталоге означает молча потерянные автозапуск, панель, обои и бинды.
unsquashfs -l "$SFS" /etc/skel/.config/hypr/hyprland.lua >/dev/null 2>&1 || fail_iso "нет skel hyprland.lua (Hyprland 0.57 не читает .conf)"
unsquashfs -l "$SFS" /etc/skel/.config/hypr/theme.lua >/dev/null 2>&1 || fail_iso "нет skel theme.lua для Hyprland"
if unsquashfs -l "$SFS" /etc/skel/.config/hypr/hyprland.conf >/dev/null 2>&1; then
    fail_iso "в образе остался legacy hyprland.conf вместо hyprland.lua"
fi
sfs_grep /etc/skel/.config/hypr/hyprland.lua 'hl.on("hyprland.start"' || fail_iso "hyprland.lua без автозапуска FlyArchOs"
if sfs_grep /etc/skel/.config/hypr/hyprland.lua 'exec_cmd.*pamixer'; then
    fail_iso "hyprland.lua ссылается на pamixer, которого нет в группах пакетов"
fi

# Менеджер входа и обе сессии физически в образе (имена .desktop менялись
# между версиями Hyprland/Plasma, а SDDM раньше уезжал с группой Plasma).
unsquashfs -l "$SFS" /usr/bin/sddm >/dev/null 2>&1 || fail_iso "нет /usr/bin/sddm"
unsquashfs -l "$SFS" /usr/share/wayland-sessions/hyprland.desktop >/dev/null 2>&1 || fail_iso "нет сессии hyprland.desktop"
unsquashfs -l "$SFS" /usr/share/wayland-sessions/plasma.desktop >/dev/null 2>&1 || fail_iso "нет сессии plasma.desktop"

# Конфиг pacman УСТАНОВЛЕННОЙ системы: multilib включён, а сборочных
# file://-репозиториев и mini-NoExtract в нём быть не должно.
sfs_grep /etc/pacman.conf '^\[multilib\]' || fail_iso "в /etc/pacman.conf образа не включён multilib"
if sfs_grep /etc/pacman.conf '^Server.*file://'; then
    fail_iso "в /etc/pacman.conf образа остался сборочный file://-репозиторий"
fi
if sfs_grep /etc/pacman.conf '^\[flyarchos\]'; then
    fail_iso "в /etc/pacman.conf образа осталась сборочная секция [flyarchos]"
fi
if sfs_grep /etc/pacman.conf '^NoExtract'; then
    fail_iso "в /etc/pacman.conf образа остался mini-NoExtract"
fi
sfs_grep /etc/pacman.d/mirrorlist '^Server.*https://' || fail_iso "mirrorlist образа без активных https-зеркал"
# LUKS2+Argon2id GRUB не открывает, а отдельного /boot в авторазметке нет.
sfs_grep /etc/calamares/modules/partition.conf 'luksGeneration: luks1' || fail_iso "partition.conf не на luksGeneration: luks1 (GRUB+LUKS2 не загрузится)"

# Целостность Calamares именно в УПАКОВАННОМ (уже трансформированном под
# slim/mini) виде: каждый модуль последовательности существует, а каждый
# ${gs[packagechooser_*]} в shellprocess пишет показанная страница выбора.
rm -rf /tmp/calamaresprobe
unsquashfs -q -d /tmp/calamaresprobe "$SFS" /etc/calamares/settings.conf /etc/calamares/modules >/dev/null 2>&1 || \
    fail_iso "не удалось распаковать конфиг Calamares для проверки"
if ! python3 - /tmp/calamaresprobe/etc/calamares > /tmp/calamares-modules.txt <<'PYEOF'
import re
import sys
from pathlib import Path

import yaml

root = Path(sys.argv[1])
settings = yaml.safe_load((root / "settings.conf").read_text(encoding="utf-8"))
instances = {item["id"]: item for item in settings.get("instances", [])}
used: set[str] = set()
shown_choosers: set[str] = set()
for phase in settings.get("sequence", []):
    for kind, entries in phase.items():
        for entry in entries or []:
            if "@" in entry:
                module, ident = entry.split("@", 1)
                used.add(instances.get(ident, {}).get("module", module))
                if kind == "show" and module == "packagechooser":
                    shown_choosers.add(ident)
            else:
                used.add(entry)

def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)

problems = []
for ident, inst in instances.items():
    if inst.get("module") != "shellprocess":
        continue
    data = yaml.safe_load((root / "modules" / inst["config"]).read_text(encoding="utf-8")) or {}
    for text in strings(data.get("script", [])):
        for key in re.findall(r"\$\{gs\[([^\]]+)\]\}", text):
            if not key.startswith("packagechooser_"):
                problems.append(f"{inst['config']}: неизвестный GS-ключ {key}")
            elif key.split("_", 1)[1] not in shown_choosers:
                problems.append(f"{inst['config']}: GS-ключ {key} без показанной страницы")

bootloader = root / "modules" / "bootloader.conf"
if bootloader.is_file():
    data = yaml.safe_load(bootloader.read_text(encoding="utf-8")) or {}
    var = str(data.get("efiBootLoaderVar") or "")
    if var.startswith("packagechooser_") and var.split("_", 1)[1] not in shown_choosers:
        problems.append(f"bootloader.conf: {var} без показанной страницы")

if problems:
    print("; ".join(problems), file=sys.stderr)
    raise SystemExit(1)
print("\n".join(sorted(used)))
PYEOF
then
    fail_iso "Calamares: shellprocess/bootloader ссылаются на GS-ключи непоказанных страниц packagechooser"
fi
while IFS= read -r module; do
    [ -n "$module" ] || continue
    unsquashfs -l "$SFS" "/usr/lib/calamares/modules/$module/module.desc" >/dev/null 2>&1 || \
        fail_iso "нет module.desc модуля Calamares: $module"
done < /tmp/calamares-modules.txt
echo "  образ проверен: live-сессия на месте"

log "Результат"
ls -lh out/
for sum in out/*.sha256; do
    [ -f "$sum" ] && cat "$sum"
done
