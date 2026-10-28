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

if [ -d /usr/share/sddm ] || command -v sddm >/dev/null 2>&1; then
    SESSION=$(pick_session "$DESKTOP" || true)
    if [ -n "${SESSION:-}" ]; then
        say "SDDM: сессия по умолчанию $SESSION"
        install -d -m 755 /var/lib/sddm
        cat > /var/lib/sddm/state.conf <<EOF
[Last]
Session=${SESSION}
EOF
        chown -R sddm:sddm /var/lib/sddm 2>/dev/null || true
    fi
fi

# --- 4. Тема GRUB -----------------------------------------------------------
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

say "Тема GRUB"
make_grub_theme || say "  тема GRUB не применена (не критично)"

# --- 5. Контрольная проверка загрузчика ------------------------------------
if [ ! -f /boot/grub/grub.cfg ] && [ ! -d /boot/loader/entries ] && [ ! -d /boot/EFI ]; then
    say "(!) загрузчик не найден — ставим GRUB вручную"
    if [ -d /sys/firmware/efi ]; then
        for esp in /boot/efi /boot /efi; do
            if [ -d "$esp" ]; then
                run grub-install --target=x86_64-efi --efi-directory="$esp" \
                                 --bootloader-id=FlyArchOs --recheck
                break
            fi
        done
        run grub-mkconfig -o /boot/grub/grub.cfg
    else
        rootdev=$(findmnt -no SOURCE / 2>/dev/null | sed -E 's/p?[0-9]+$//')
        if [ -n "$rootdev" ]; then
            run grub-install --target=i386-pc --recheck "$rootdev"
            run grub-mkconfig -o /boot/grub/grub.cfg
        fi
    fi
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
if ! command -v calamares >/dev/null 2>&1; then
    rm -rf /etc/calamares /usr/share/calamares 2>/dev/null
    rm -f /usr/share/applications/flyarchos-install.desktop 2>/dev/null
fi
rm -rf /var/cache/pacman/pkg/* /tmp/* /var/tmp/* 2>/dev/null
rm -f /root/.bash_history

# --- 9. Памятка о выбранном профиле ---------------------------------------
{
    echo "FlyArchOs — установка завершена"
    echo "  Дата:          $(date -Is)"
    echo "  Окружение:     $DESKTOP"
    echo "  Сценарий:      $PRESET"
    echo "  Наборы ПО:     ${EXTRAS:-не выбраны}"
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
