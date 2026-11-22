# NanOs live session: start the single graphical session on tty1.
# Use Hyprland's supported launcher; if the session exits, return to this
# autologin shell instead of repeatedly restarting the compositor.
if [ -t 0 ] && [ -t 1 ] && [ "$(tty 2>/dev/null)" = "/dev/tty1" ]; then
    if command -v start-hyprland >/dev/null 2>&1; then
        start-hyprland
    else
        echo "NanOs: start-hyprland is missing; refusing direct Hyprland launch." >&2
    fi
fi
