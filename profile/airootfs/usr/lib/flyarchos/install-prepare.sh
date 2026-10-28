#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# FlyArchOs — подготовка распакованной live-системы к жизни на диске.
# Вызывается Calamares (shellprocess@prepare) уже ВНУТРИ целевой системы.
# ---------------------------------------------------------------------------
set -uo pipefail

LOG=/var/log/flyarchos-install.log
say() { printf '[prepare] %s\n' "$*" | tee -a "$LOG"; }
run() { say "  $*"; "$@" >>"$LOG" 2>&1 || say "  (!) команда вернула ошибку: $*"; }

say "=== подготовка системы $(date -Is) ==="

# --- 1. Убираем всё, что нужно только в live -------------------------------
say "Удаление live-мусора"
rm -f /etc/sudoers.d/10-flyarchos-live
rm -f /etc/pacman.d/hooks/flyarchos-live-setup.hook
rm -f /usr/lib/flyarchos/live-setup.sh
rm -f /usr/lib/sysusers.d/flyarchos-live.conf
rm -f /etc/flyarchos-live-setup.done
rm -f /etc/sddm.conf.d/zz-live-autologin.conf
rm -f /etc/systemd/system/getty@tty1.service.d/autologin.conf
rm -rf /etc/systemd/system/getty@tty1.service.d
rm -f /etc/systemd/system/pacman-init.service
rm -f /etc/systemd/system/choose-mirror.service
rm -f /etc/systemd/system/etc-pacman.d-gnupg.mount
rm -f /etc/systemd/system/multi-user.target.wants/pacman-init.service
rm -f /etc/systemd/system/multi-user.target.wants/choose-mirror.service
rm -f /etc/systemd/system/reflector.service
rm -f /etc/systemd/system/multi-user.target.wants/reflector.service
rm -f /etc/xdg/autostart/calamares.desktop 2>/dev/null
rm -f /root/.automated_script.sh
rm -f /root/customize_airootfs.sh
rm -f /etc/flyarchos-build-stamp
rm -f /etc/motd

# --- 2. Обычные mkinitcpio-пресеты вместо archiso-овских ------------------
say "mkinitcpio: обычные пресеты"
rm -f /etc/mkinitcpio-archiso.conf
# Live-хуки archiso не должны попасть в initramfs установленной системы
rm -f /etc/mkinitcpio.conf.d/archiso.conf
# Включаем обратно gpt-auto-generator (в live он заглушён)
rm -f /etc/systemd/system-generators/systemd-gpt-auto-generator
if [ -d /usr/share/flyarchos/mkinitcpio ]; then
    install -Dm 644 /usr/share/flyarchos/mkinitcpio/mkinitcpio.conf /etc/mkinitcpio.conf
    for preset in linux linux-lts; do
        if [ -f "/usr/share/flyarchos/mkinitcpio/${preset}.preset" ]; then
            install -Dm 644 "/usr/share/flyarchos/mkinitcpio/${preset}.preset" "/etc/mkinitcpio.d/${preset}.preset"
        fi
    done
fi

# --- 3. Удаляем live-пользователя, чтобы новый получил uid 1000 -----------
if id -u fly >/dev/null 2>&1; then
    say "Удаление live-пользователя fly"
    run userdel -r fly
fi
rm -rf /home/fly

# --- 4. Сбрасываем идентификаторы, которые должны быть уникальными --------
say "Сброс machine-id и случайных seed"
: > /etc/machine-id
rm -f /var/lib/dbus/machine-id
rm -f /var/lib/systemd/random-seed
rm -f /var/lib/urandom/random-seed

# --- 5. Службы установленной системы --------------------------------------
say "Включение служб"
for unit in NetworkManager.service sddm.service bluetooth.service \
            systemd-timesyncd.service systemd-oomd.service; do
    run systemctl enable "$unit"
done
for unit in cups.service avahi-daemon.service snapper-timeline.timer \
            systemd-zram-setup@zram0.service; do
    systemctl enable "$unit" >>"$LOG" 2>&1 || say "  служба недоступна: $unit"
done

# --- 6. Сеть/имя хоста: базовые значения до того, как их задаст Calamares -
echo "flyarchos" > /etc/hostname
cat > /etc/hosts <<'EOF'
127.0.0.1        localhost
::1              localhost
127.0.1.1        flyarchos.localdomain flyarchos
EOF

# --- 7. Локаль по умолчанию (Calamares запишет свою позже) ----------------
if ! grep -q '^LANG=' /etc/locale.conf 2>/dev/null; then
    echo "LANG=ru_RU.UTF-8" > /etc/locale.conf
fi

# --- 8. Чистка кэшей ------------------------------------------------------
say "Очистка кэшей"
rm -rf /var/cache/pacman/pkg/*
rm -rf /tmp/* /var/tmp/* /root/.cache/* 2>/dev/null
rm -f /root/.bash_history

# --- 9. Каталог состояния FlyArchOs ---------------------------------------
install -d -m 755 /etc/flyarchos
install -d -m 755 /var/log/flyarchos

say "=== подготовка завершена ==="
exit 0
