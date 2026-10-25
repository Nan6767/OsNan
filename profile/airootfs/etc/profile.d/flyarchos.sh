# FlyArchOs — удобные алиасы и приветствие в консоли.
alias ll='ls -lah --color=auto'
alias update='sudo pacman -Syu'
alias fwall='flyarchos-wallpaper'
alias finfo='flyarchos-info'

if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ] && [ "$(tty)" = "/dev/tty1" ]; then
    echo
    cat /usr/share/flyarchos/logo.txt 2>/dev/null
    echo
    echo "  FlyArchOs — Arch + Hyprland + KDE Plasma"
    echo "  Справка: flyarchos-info   Установка: flyarchos-install"
    echo
fi
