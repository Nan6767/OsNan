# Kali's live user uses zsh. Start the only desktop on tty1 with Hyprland's
# supported launcher; if it exits, leave the user at a shell for diagnostics.
if [[ -o interactive ]] && [[ -t 0 && -t 1 ]] && [[ "$(tty 2>/dev/null)" == "/dev/tty1" ]]; then
    if command -v start-hyprland >/dev/null 2>&1; then
        start-hyprland
    else
        echo "NanOs: start-hyprland is missing; refusing direct Hyprland launch." >&2
    fi
fi
