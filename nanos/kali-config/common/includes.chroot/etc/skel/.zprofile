# Kali's live user uses zsh. Start the only desktop on tty1; if Hyprland
# exits or fails, leave the user at an interactive shell for diagnostics.
if [[ -o interactive ]] && [[ -t 0 && -t 1 ]] && [[ "$(tty 2>/dev/null)" == "/dev/tty1" ]]; then
    if (( $+commands[dbus-run-session] )); then
        dbus-run-session -- Hyprland
    else
        Hyprland
    fi
fi
