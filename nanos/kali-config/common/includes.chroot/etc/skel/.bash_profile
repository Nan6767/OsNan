# Keep bash login setup, then run the NanOs tty1 live session hook.
[ -r "$HOME/.bashrc" ] && . "$HOME/.bashrc"
[ -r "$HOME/.profile" ] && . "$HOME/.profile"
