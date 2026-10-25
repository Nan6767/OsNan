# FlyArchOs — настройки bash
[[ $- != *i* ]] && return

PS1='\[\e[36m\]\u@\h\[\e[0m\] \[\e[35m\]\w\[\e[0m\] \$ '
alias ll='ls -lah --color=auto'
alias update='sudo pacman -Syu'
alias fwall='flyarchos-wallpaper'
alias finfo='flyarchos-info'
