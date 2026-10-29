#!/usr/bin/bash
# ---------------------------------------------------------------------------
# FlyArchOs — одноразовая настройка live-образа при сборке ISO.
# Вызывается pacman-хуком flyarchos-live-setup.hook в конце pacstrap
# внутри chroot образа (mkarchiso 91+ больше не выполняет
# customize_airootfs.sh). Делает только то, что нельзя задать
# статичными файлами оверлея airootfs/.
# На установленной системе хук и этот скрипт удаляет install-prepare.sh;
# маркер дополнительно защищает от повторного запуска.
# ---------------------------------------------------------------------------
set -u

MARKER=/etc/flyarchos-live-setup.done
[ -e "$MARKER" ] && exit 0

# Пакет glibc не несёт собранных локалей — генерируем en_US и ru_RU,
# чтобы live-сессия сразу была русской. В современном glibc файл
# /etc/locale.gen может не содержать готовых строк, поэтому добавляем
# их явно и собираем локали напрямую через localedef.
for loc in en_US ru_RU; do
    grep -qx "${loc}.UTF-8 UTF-8" /etc/locale.gen 2>/dev/null \
        || echo "${loc}.UTF-8 UTF-8" >> /etc/locale.gen 2>/dev/null || true
    localedef -i "${loc}" -f UTF-8 "${loc}.UTF-8" || true
done
locale-gen || true
echo "=== FlyArchOs live-setup: собранные локали ==="
localedef --list-archive || true
ls -la /usr/lib/locale/ || true

# Фирменный os-release: заменяем файл пакета filesystem после установки.
install -Dm644 /usr/share/flyarchos/os-release /usr/lib/os-release 2>/dev/null || true

# Фон экрана входа SDDM (тема breeze) — фирменные обои.
THEME_CONF=/usr/share/sddm/themes/breeze/theme.conf
if [ -f "$THEME_CONF" ]; then
    if grep -q '^background=' "$THEME_CONF"; then
        sed -i 's|^background=.*|background=/usr/share/backgrounds/flyarchos/default.jpg|' "$THEME_CONF" || true
    else
        printf '\nbackground=/usr/share/backgrounds/flyarchos/default.jpg\n' >> "$THEME_CONF" || true
    fi
fi

# machine-id и random-seed должны родиться при первой загрузке.
# Связка ключей pacman не должна наследоваться от сборочного хоста:
# при первой загрузке её заново создаст pacman-init.service.
rm -rf /etc/pacman.d/gnupg 2>/dev/null || true
: > /etc/machine-id 2>/dev/null || true
rm -f /var/lib/systemd/random-seed 2>/dev/null || true

echo "FlyArchOs live image prepared" > /etc/flyarchos-build-stamp 2>/dev/null || true
touch "$MARKER" 2>/dev/null || true
exit 0
