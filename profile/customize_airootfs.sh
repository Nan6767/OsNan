#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# FlyArchOs — донастройка live-системы. Выполняется mkarchiso внутри chroot
# после установки всех пакетов (см. scripts/build-iso.sh).
# ---------------------------------------------------------------------------
set -euo pipefail

LIVE_USER="fly"
LIVE_UID="1000"

echo "==> [1/9] Локализация"
sed -i 's/^#\(en_US\.UTF-8\)/\1/; s/^#\(ru_RU\.UTF-8\)/\1/' /etc/locale.gen
locale-gen
printf 'LANG=ru_RU.UTF-8\n' > /etc/locale.conf
printf 'KEYMAP=ru\nFONT=cyr-sun16\n' > /etc/vconsole.conf
ln -sf /usr/share/zoneinfo/Europe/Kaliningrad /etc/localtime

echo "==> [2/9] Live-пользователь ${LIVE_USER}"
if ! id -u "${LIVE_USER}" >/dev/null 2>&1; then
    useradd -m -u "${LIVE_UID}" -G wheel,audio,video,optical,storage,network,input -s /usr/bin/zsh "${LIVE_USER}"
fi
echo "${LIVE_USER}:flyarchos" | chpasswd
echo 'root:flyarchos' | chpasswd
cp -aT /etc/skel/ "/home/${LIVE_USER}/"
chown -R "${LIVE_UID}:${LIVE_UID}" "/home/${LIVE_USER}"
chmod 700 "/home/${LIVE_USER}"

echo "==> [3/9] Права sudo (live: без пароля, для установщика)"
install -Dm 440 /dev/stdin /etc/sudoers.d/10-flyarchos-live <<'EOF'
%wheel ALL=(ALL:ALL) NOPASSWD: ALL
EOF

echo "==> [4/9] Службы live-сессии"
# Всё через || true: в chroot systemd может быть недоступен, а сборка
# не должна падать из-за сервисов (они всё равно включаются установщиком).
for unit in sddm.service NetworkManager.service bluetooth.service \
            cups.service avahi-daemon.service systemd-timesyncd.service; do
    systemctl enable "$unit" 2>/dev/null || echo "  (не удалось включить $unit — не критично)"
done
systemctl disable systemd-resolved.service 2>/dev/null || true
systemctl set-default graphical.target 2>/dev/null || true

echo "==> [5/9] Кэш иконок/шрифтов/тем"
fc-cache -fs >/dev/null 2>&1 || true
update-desktop-database -q 2>/dev/null || true
gtk-update-icon-cache -q -t -f /usr/share/icons/breeze 2>/dev/null || true
gtk-update-icon-cache -q -t -f /usr/share/icons/breeze-dark 2>/dev/null || true
gtk-update-icon-cache -q -t -f /usr/share/icons/Papirus 2>/dev/null || true
gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true

echo "==> [6/9] Ссылки на инструменты FlyArchOs"
ln -sf /usr/lib/flyarchos/profile_tool.py /usr/bin/flyarchos-profile
ln -sf /usr/lib/flyarchos/wallpaper_tool.py /usr/bin/flyarchos-wallpaper
ln -sf /usr/lib/flyarchos/wallpapers.py /usr/bin/flyarchos-wallpaper-gen
ln -sf /usr/lib/flyarchos/welcome-gui.py /usr/bin/flyarchos-welcome
ln -sf /usr/lib/flyarchos/flyarchos-info /usr/bin/flyarchos-info
ln -sf /usr/lib/flyarchos/flyarchos-install /usr/bin/flyarchos-install
ln -sf /usr/lib/flyarchos/flyarchos-update /usr/bin/flyarchos-update
ln -sf /usr/lib/flyarchos/doctor_tool.py /usr/bin/flyarchos-doctor
ln -sf /usr/lib/flyarchos/theme_tool.py /usr/bin/flyarchos-theme
ln -sf /usr/lib/flyarchos/flyarchos-snapshot /usr/bin/flyarchos-snapshot

echo "==> [7/9] Обои по умолчанию"
install -d -m 755 /usr/share/backgrounds/flyarchos
flyarchos-wallpaper set-default aurora-nexus 2>/dev/null || true

echo "==> [8/9] Очистка кэшей пакетов"
rm -rf /var/cache/pacman/pkg/* || true
rm -rf /root/.cache/* || true
rm -f /var/lib/systemd/random-seed || true
: > /etc/machine-id

# Профиль mini: образ должен влезть в 2 ГБ одним файлом (лимит GitHub
# Release). Убираем документацию и локали кроме английской и русской —
# пакеты при этом не трогаем, pacman о файлах не узнает и не сломается.
if [ "$(cat /usr/share/flyarchos/profile-variant 2>/dev/null)" = "mini" ]; then
    echo "==> [mini] Урезание документации и локалей"
    rm -rf /usr/share/doc /usr/share/gtk-doc /usr/share/info /usr/share/man 2>/dev/null || true
    for d in /usr/share/locale/*/; do
        case "$(basename "$d")" in
            en*|ru*|C*|locale.alias) : ;;
            *) rm -rf "$d" ;;
        esac
    done
fi

echo "==> [9/9] Готово"
echo "FlyArchOs live image prepared" > /etc/flyarchos-build-stamp
