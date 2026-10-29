#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# FlyArchOs — финальная настройка уже установленной системы.
# Вызывается Calamares (shellprocess@finalize) ВНУТРИ целевой системы,
# после users/загрузчика. Всё, что может упасть, — не роняет установку.
# ---------------------------------------------------------------------------
set -uo pipefail

LOG=/var/log/flyarchos-install.log
STATE=/etc/flyarchos/profile.json
say() { printf '[finalize] %s\n' "$*" | tee -a "$LOG"; }
run() { say "  $*"; "$@" >>"$LOG" 2>&1 || say "  (!) команда вернула ошибку: $*"; }

say "=== финализация $(date -Is) ==="

# --- 1. Что выбрал пользователь -------------------------------------------
DESKTOP="both"
PRESET="custom"
EXTRAS=""
if [ -f "$STATE" ] && command -v python3 >/dev/null 2>&1; then
    DESKTOP=$(python3 -c "import json;print(json.load(open('$STATE')).get('desktop','both'))" 2>/dev/null || echo both)
    PRESET=$(python3 -c "import json;print(json.load(open('$STATE')).get('preset','custom'))" 2>/dev/null || echo custom)
    EXTRAS=$(python3 -c "import json;print(', '.join(json.load(open('$STATE')).get('extras',[])))" 2>/dev/null || echo "")
fi
say "Окружение: $DESKTOP; сценарий: $PRESET; наборы: ${EXTRAS:-нет}"

# --- 2. Обои по умолчанию --------------------------------------------------
case "$DESKTOP" in
    hyprland) DEFAULT_WALL="02-neon-grid" ;;
    plasma)   DEFAULT_WALL="01-aurora-nexus" ;;
    *)        DEFAULT_WALL="01-aurora-nexus" ;;
esac
if command -v flyarchos-wallpaper >/dev/null 2>&1; then
    if ! flyarchos-wallpaper set-default "$DEFAULT_WALL" >>"$LOG" 2>&1; then
        # fallback: первый попавшийся файл обоев
        first=$(ls /usr/share/backgrounds/flyarchos/*.jpg 2>/dev/null | head -n1)
        [ -n "$first" ] && flyarchos-wallpaper set-default "$first" >>"$LOG" 2>&1
    fi
    say "Обои по умолчанию: $DEFAULT_WALL"
fi

# --- 3. Сессия по умолчанию в SDDM ----------------------------------------
pick_session() {
    case "$1" in
        hyprland)
            for f in /usr/share/wayland-sessions/hyprland.desktop \
                     /usr/share/wayland-sessions/hyprland-uwsm.desktop; do
                [ -f "$f" ] && { echo "$f"; return 0; }
            done ;;
        *)
            for f in /usr/share/wayland-sessions/plasma.desktop \
                     /usr/share/wayland-sessions/plasmawayland.desktop \
                     /usr/share/xsessions/plasma.desktop; do
                [ -f "$f" ] && { echo "$f"; return 0; }
            done ;;
    esac
    return 1
}

if command -v sddm >/dev/null 2>&1; then
    SESSION=$(pick_session "$DESKTOP" || true)
    if [ -z "${SESSION:-}" ]; then
        # Выбранная сессия не нашлась (например, её пакеты удалены) —
        # берём любую реально оставшуюся, лишь бы вход был графическим.
        SESSION=$(pick_session plasma || pick_session hyprland || true)
    fi
    if [ -n "${SESSION:-}" ]; then
        say "SDDM: сессия по умолчанию $SESSION"
        install -d -m 755 /var/lib/sddm
        cat > /var/lib/sddm/state.conf <<EOF
[Last]
Session=${SESSION}
EOF
        chown -R sddm:sddm /var/lib/sddm 2>/dev/null || true
    else
        say "(!) SDDM: не найдено ни одной графической сессии"
    fi

    # Тема экрана входа обязана существовать после удаления невыбранного
    # окружения. breeze может исчезнуть вместе с Plasma, а elarun/maldives/
    # maya поставляет сам пакет sddm (он теперь в обязательной группе).
    SDDM_THEME=""
    for cand in breeze elarun maldives maya; do
        if [ -d "/usr/share/sddm/themes/$cand" ]; then
            SDDM_THEME="$cand"
            break
        fi
    done
    if [ -n "$SDDM_THEME" ]; then
        say "SDDM: тема $SDDM_THEME"
        install -d -m 755 /etc/sddm.conf.d
        cat > /etc/sddm.conf.d/zz-flyarchos-finalize.conf <<EOF
# Записано install-finalize: тема гарантированно существует в системе
# после применения выбранного профиля окружения.
[Theme]
Current=${SDDM_THEME}
EOF
    else
        say "(!) SDDM: не найдено ни одной темы в /usr/share/sddm/themes"
    fi
else
    say "(!) SDDM отсутствует в установленной системе"
fi

# --- 4. Контроль загрузчика по реальным артефактам -------------------------
# Один лишь /boot/grub/grub.cfg ничего не доказывает: grubcfg создаёт его
# всегда, а модуль bootloader у Calamares на нескольких путях возвращает
# «успех», ничего не установив (у systemd-boot ещё и bootctl без проверки
# кода возврата). Поэтому проверяем файлы на ESP и, при нужде, ставим GRUB.
EFFECTIVE_BOOTLOADER="unknown"

find_esp() {
    local d fstype
    for d in /boot/efi /efi /boot; do
        [ -d "$d" ] || continue
        fstype=$(findmnt -no FSTYPE "$d" 2>/dev/null || true)
        case "$fstype" in
            vfat|fat|msdos) printf '%s\n' "$d"; return 0 ;;
        esac
        if [ -d "$d/EFI" ] || [ -d "$d/loader" ]; then
            printf '%s\n' "$d"
            return 0
        fi
    done
    return 1
}

systemd_boot_entries_ok() {
    local esp="$1" entry kind path rest
    [ -f "$esp/loader/loader.conf" ] || return 1
    entry=$(find "$esp/loader/entries" -maxdepth 1 -type f -name '*.conf' -print -quit 2>/dev/null)
    if [ -z "${entry:-}" ]; then
        # UKI (BLS Type#2): отдельные .efi в EFI/Linux тоже загружаемы.
        compgen -G "$esp/EFI/Linux/*.efi" >/dev/null 2>&1 && return 0
        return 1
    fi
    grep -q '^linux[[:space:]]' "$entry" || return 1
    while read -r kind path rest; do
        case "$kind" in
            linux|initrd)
                [ -n "${path:-}" ] && [ -f "$esp$path" ] || return 1
                ;;
        esac
    done < "$entry"
    return 0
}

systemd_boot_binary_ok() {
    local esp="$1"
    [ -f "$esp/EFI/systemd/systemd-bootx64.efi" ] ||
    [ -f "$esp/EFI/BOOT/BOOTX64.EFI" ] ||
    [ -f "$esp/EFI/boot/bootx64.efi" ]
}

has_grub_efi() {
    local esp="$1" found
    [ -s /boot/grub/grub.cfg ] || return 1
    found=$(find "$esp/EFI" -iname 'grubx64.efi' -print -quit 2>/dev/null)
    [ -n "${found:-}" ]
}

install_grub_efi() {
    local esp="$1"
    command -v grub-install >/dev/null 2>&1 || return 1
    say "Ставлю GRUB (UEFI) на ESP $esp"
    if ! grub-install --target=x86_64-efi --efi-directory="$esp" \
            --bootloader-id=FlyArchOs --recheck >>"$LOG" 2>&1; then
        say "  обычный grub-install не прошёл — пробую removable/no-nvram"
        grub-install --target=x86_64-efi --efi-directory="$esp" \
            --bootloader-id=FlyArchOs --removable --no-nvram --recheck >>"$LOG" 2>&1 || return 1
    fi
    grub-mkconfig -o /boot/grub/grub.cfg >>"$LOG" 2>&1
}

root_disk() {
    local dev type parent n
    dev=$(findmnt -no SOURCE / 2>/dev/null || true)
    dev=${dev%%\[*}   # /dev/sda2[/@] (btrfs-субтом) → /dev/sda2
    [ -b "${dev:-}" ] || return 1
    # Идём вверх по родителям: раздел → диск, LUKS-mapper → раздел → диск.
    # Старый sed 's/p?[0-9]+$//' ломался и на mapper, и на субтоме btrfs.
    for n in 1 2 3 4 5 6 7 8 9 10; do
        type=$(lsblk -dn -o TYPE "$dev" 2>/dev/null || true)
        if [ "$type" = "disk" ]; then
            printf '%s\n' "$dev"
            return 0
        fi
        parent=$(lsblk -dn -o PKNAME "$dev" 2>/dev/null || true)
        [ -n "${parent:-}" ] || return 1
        dev="/dev/$parent"
        [ -b "$dev" ] || return 1
    done
    return 1
}

say "Проверка загрузчика"
if [ -d /sys/firmware/efi ]; then
    ESP=$(find_esp || true)
    if [ -n "${ESP:-}" ]; then
        if systemd_boot_entries_ok "$ESP"; then
            if [ ! -f "$ESP/EFI/systemd/systemd-bootx64.efi" ] && command -v bootctl >/dev/null 2>&1; then
                say "systemd-boot: записи есть, EFI-бинарника нет — повторяю bootctl install"
                bootctl --path="$ESP" install >>"$LOG" 2>&1 || say "  (!) bootctl install не отработал"
            fi
            if systemd_boot_binary_ok "$ESP"; then
                EFFECTIVE_BOOTLOADER="systemd-boot"
            fi
        fi
        if [ "$EFFECTIVE_BOOTLOADER" = "unknown" ] && has_grub_efi "$ESP"; then
            EFFECTIVE_BOOTLOADER="grub"
        fi
        if [ "$EFFECTIVE_BOOTLOADER" = "unknown" ]; then
            say "(!) на ESP $ESP нет работоспособного загрузчика — аварийно ставлю GRUB"
            if install_grub_efi "$ESP" && has_grub_efi "$ESP"; then
                EFFECTIVE_BOOTLOADER="grub"
            fi
        fi
    else
        say "(!) EFI-раздел (ESP) не найден среди /boot/efi, /efi, /boot"
    fi
else
    ROOT_DISK=$(root_disk || true)
    if [ -n "${ROOT_DISK:-}" ] && command -v grub-install >/dev/null 2>&1; then
        # Для BIOS запись в MBR файлами не проверить — просто переустанавливаем.
        say "BIOS: ставлю GRUB в MBR диска $ROOT_DISK"
        if grub-install --target=i386-pc --recheck "$ROOT_DISK" >>"$LOG" 2>&1 &&
           grub-mkconfig -o /boot/grub/grub.cfg >>"$LOG" 2>&1; then
            EFFECTIVE_BOOTLOADER="grub"
        else
            say "  (!) grub-install (BIOS) не отработал — смотрите $LOG"
        fi
    else
        say "(!) BIOS: не удалось определить диск корня для GRUB"
        [ -s /boot/grub/grub.cfg ] && EFFECTIVE_BOOTLOADER="grub"
    fi
fi
say "Эффективный загрузчик: $EFFECTIVE_BOOTLOADER"

# --- 5. Тема GRUB -----------------------------------------------------------
make_grub_theme() {
    local themedir=/boot/grub/themes/flyarchos
    local bg=/usr/share/backgrounds/flyarchos/default.jpg
    [ -d /boot/grub ] || return 0
    [ -f "$bg" ] || return 0
    command -v grub-mkfont >/dev/null 2>&1 || return 0
    local font=""
    for f in /usr/share/fonts/TTF/DejaVuSansMono.ttf /usr/share/fonts/TTF/DejaVuSans.ttf \
             /usr/share/fonts/noto/NotoSansMono-Regular.ttf; do
        [ -f "$f" ] && { font="$f"; break; }
    done
    [ -n "$font" ] || return 0

    install -d -m 755 "$themedir"
    cp -f "$bg" "$themedir/background.jpg"
    grub-mkfont -s 16 -o "$themedir/unicode.pf2" "$font" >>"$LOG" 2>&1 || return 0

    cat > "$themedir/theme.txt" <<'EOF'
# FlyArchOs GRUB theme
desktop-image: "background.jpg"
desktop-color: "#10121c"
terminal-font: "unicode.pf2"

+ boot_menu {
    left = 12%
    width = 76%
    top = 22%
    height = 56%
    item_font = "unicode 16"
    item_color = "#c8cbe0"
    selected_item_color = "#22d3ee"
    item_height = 32
    item_spacing = 8
    item_padding = 8
    icon_width = 0
    icon_height = 0
}
+ label {
    text = "FlyArchOs"
    font = "unicode 28"
    color = "#f5f7ff"
    left = 12%
    top = 12%
}
+ progress_bar {
    id = "__timeout__"
    left = 12%
    width = 76%
    top = 86%
    height = 4
    fg_color = "#f0559b"
    bg_color = "#242840"
    border_color = "#242840"
}
EOF

    # Прописываем тему в /etc/default/grub и пересобираем конфиг
    if [ -f /etc/default/grub ]; then
        sed -i '/^GRUB_THEME=/d; /^GRUB_FONT=/d' /etc/default/grub
        cat >> /etc/default/grub <<EOF
GRUB_THEME="$themedir/theme.txt"
GRUB_FONT="$themedir/unicode.pf2"
EOF
    fi
    grub-mkconfig -o /boot/grub/grub.cfg >>"$LOG" 2>&1 || say "  (!) grub-mkconfig не отработал"
}

if [ "$EFFECTIVE_BOOTLOADER" != "systemd-boot" ]; then
    say "Тема GRUB"
    make_grub_theme || say "  тема GRUB не применена (не критично)"
else
    say "Тема GRUB пропущена: используется systemd-boot"
fi

# --- 6. Службы (повторно, на случай если prepare что-то пропустил) --------
say "Службы"
for unit in NetworkManager.service sddm.service bluetooth.service systemd-timesyncd.service; do
    run systemctl enable "$unit"
done

# --- 6б. Файрвол для набора «Приватность» ---------------------------------
FIREWALL="не установлен"
if command -v ufw >/dev/null 2>&1; then
    FIREWALL="установлен, выключен (sudo systemctl enable --now ufw)"
    case "$EXTRAS" in
        *privacy*)
            say "Файрвол UFW: включаю (набор «Приватность»)"
            if [ -f /etc/ufw/ufw.conf ]; then
                sed -i 's/^ENABLED=no/ENABLED=yes/' /etc/ufw/ufw.conf
            fi
            if [ -f /etc/default/ufw ]; then
                sed -i 's/^DEFAULT_INPUT_POLICY=.*/DEFAULT_INPUT_POLICY="DROP"/; s/^DEFAULT_OUTPUT_POLICY=.*/DEFAULT_OUTPUT_POLICY="ACCEPT"/; s/^DEFAULT_FORWARD_POLICY=.*/DEFAULT_FORWARD_POLICY="DROP"/' /etc/default/ufw
            fi
            run systemctl enable ufw.service
            FIREWALL="включён (входящие запрещены, исходящие разрешены)"
            ;;
    esac
fi

# --- 7. Первый вход: одноразовый помощник ---------------------------------
install -d -m 755 /etc/skel/.config/flyarchos
if [ -f /etc/skel/.config/flyarchos/welcome-done ]; then
    rm -f /etc/skel/.config/flyarchos/welcome-done
fi

# --- 8. Финальная уборка ---------------------------------------------------
say "Уборка"
# Установщик в установленной системе не нужен. profile_tool уже удалил
# пакет (LIVE_ONLY_PACKAGES); здесь — страховочный повтор, а затем чистка
# остатков конфигурации, которые pacman оставляет как .pacsave/оверлей.
if command -v calamares >/dev/null 2>&1; then
    say "Calamares всё ещё в целевой системе — удаляю пакет"
    pacman -Rns --noconfirm --noprogressbar calamares >>"$LOG" 2>&1 ||
        say "  (!) pacman не смог удалить calamares"
fi
if ! command -v calamares >/dev/null 2>&1; then
    rm -rf /etc/calamares /usr/share/calamares 2>/dev/null
fi
rm -f /usr/share/applications/flyarchos-install.desktop 2>/dev/null
rm -rf /var/cache/pacman/pkg/* /tmp/* /var/tmp/* 2>/dev/null
rm -f /root/.bash_history

# --- 9. Памятка о выбранном профиле ---------------------------------------
{
    echo "FlyArchOs — установка завершена"
    echo "  Дата:          $(date -Is)"
    echo "  Окружение:     $DESKTOP"
    echo "  Сценарий:      $PRESET"
    echo "  Наборы ПО:     ${EXTRAS:-не выбраны}"
    echo "  Загрузчик:     $EFFECTIVE_BOOTLOADER"
    echo "  Файрвол UFW:   $FIREWALL"
    echo "  Ядро:          $(uname -r)"
    echo
    echo "Полезные команды:"
    echo "  flyarchos-welcome         помощник первого запуска"
    echo "  flyarchos-wallpaper list  список обоев"
    echo "  flyarchos-profile         изменить набор ПО (--desktop/--extras)"
    echo "  flyarchos-info            информация о системе"
} > /etc/flyarchos/install-summary.txt

say "=== финализация завершена ==="
exit 0
