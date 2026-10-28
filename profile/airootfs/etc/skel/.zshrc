# FlyArchOs — настройки zsh
autoload -Uz compinit && compinit
autoload -Uz colors && colors

HISTFILE=~/.zsh_history
HISTSIZE=10000
SAVEHIST=10000
setopt appendhistory sharehistory incappendhistory histignorealldups

# Приглашение: user@host каталог →
PROMPT='%F{cyan}%n@%m%f %F{magenta}%~%f %(?.%F{green}.%F{red})❯%f '
RPROMPT='%F{244}%*%f'

alias ll='ls -lah --color=auto'
alias la='ls -A --color=auto'
alias grep='grep --color=auto'
alias update='sudo pacman -Syu'
alias fwall='flyarchos-wallpaper'
alias finfo='flyarchos-info'

# Приветствие только в чистой консоли (tty1)
if [[ -z $WAYLAND_DISPLAY && -z $DISPLAY && $(tty) == /dev/tty1 ]]; then
    flyarchos-info
fi

# Плагины (пакеты zsh-autosuggestions, zsh-syntax-highlighting)
[ -f /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh ] && \
    source /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh
[ -f /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ] && \
    source /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
