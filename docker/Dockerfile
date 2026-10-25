# ---------------------------------------------------------------------------
# FlyArchOs — сборка ISO в контейнере, если нет Arch Linux под рукой.
#
#   docker build -t flyarchos-builder docker/
#   docker run --rm -it --privileged \
#       -v "$PWD/out:/flyarchos/out" \
#       -v "$PWD/repo:/flyarchos/repo" \
#       flyarchos-builder
#
# --privileged нужен mkarchiso: он монтирует loop-устройства и делает chroot.
# Без Docker можно собрать на любом Arch: см. docs/BUILD.md.
# ---------------------------------------------------------------------------
FROM archlinux:latest

LABEL org.opencontainers.image.title="FlyArchOs ISO builder"
LABEL org.opencontainers.image.description="Сборка установочного ISO FlyArchOs (Arch + Hyprland + KDE Plasma)"

# Обновляем ключи и ставим инструменты сборки
RUN pacman -Sy --noconfirm --needed archlinux-keyring \
 && pacman -Syu --noconfirm --needed \
        archiso \
        squashfs-tools \
        git \
        python \
        python-yaml \
        base-devel \
        rsync \
        cdrtools \
        dosfstools \
        mtools \
        grub \
        efibootmgr \
 && pacman -Scc --noconfirm

WORKDIR /flyarchos
COPY . /flyarchos

# Рабочие каталоги mkarchiso монтируем с хоста — так не теряем кэш пакетов
VOLUME ["/flyarchos/out"]

ENV WORK=/flyarchos/work \
    OUT=/flyarchos/out

CMD ["/flyarchos/scripts/build-iso.sh"]
