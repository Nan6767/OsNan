# NanOs live session: start the single graphical session on tty1.
# If Hyprland cannot start (for example, a VM graphics issue), return to
# this autologin shell instead of repeatedly restarting the compositor.
if [ -t 0 ] && [ -t 1 ] && [ "$(tty 2>/dev/null)" = "/dev/tty1" ]; then
    if command -v dbus-run-session >/dev/null 2>&1; then
        dbus-run-session -- Hyprland
    else
        Hyprland
    fi
fi
