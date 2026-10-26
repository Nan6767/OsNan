# FlyArchOs

**FlyArchOs Linux** — это готовый к сборке дистрибутив на базе Arch Linux с двумя
рабочими окружениями в одном установочном ISO: **Hyprland** (тайлинговый
Wayland-композит) и **KDE Plasma** (классический рабочий стол). Оба окружения
живут в образе одновременно, а установщик (**Calamares**) даёт выбрать, что
оставить на диске.

```
  _____ _       ___       _    ____   ___  ____
 |  ___| |     / _ \     / \  / ___| / _ \/ ___|
 | |_  | |    / /_\ \   / _ \| |    | | | \___ \
 |  _| | |___|  _  |  / ___ \ |___ | |_| |___) |
 |_|   |_____|_| |_| /_/   \_\____| \___/|____/
```

## Что внутри

| Возможность | Как сделано |
|---|---|
| Два окружения | `Hyprland` (Waybar + Wofi + Mako + Kitty + hyprlock) и `KDE Plasma 6` (Dolphin, Konsole, Discover, Wayland-сессия) |
| Разнообразная установка | Calamares: выбор окружения, наборов ПО, загрузчика, файловой системы, шифрования LUKS, swap-файла |
| Офлайн-установка | Все ~300 пакетов внутри squashfs: установщик копирует live-систему и удаляет невыбранные группы (`flyarchos-profile`) |
| 12 обоев | 6 авторских (AI) + 6 процедурных (генератор встроен в систему) |
| Свои обои одной командой | `flyarchos-wallpaper-gen --theme aurora --seed 3 -o ~/pic.jpg` |
| Помощник первого запуска | `flyarchos-welcome`: обои, наборы ПО, обновление системы |
| Единые обои для обоих окружений | `flyarchos-wallpaper set <id>` понимает Hyprland (swww) и Plasma (`plasma-apply-wallpaperimage`) |
| Брендинг | логотип, тема GRUB, слайд-шоу, оформление Calamares, ASCII-логотип в fastfetch |

### Обои

![Обои FlyArchOs](docs/preview.png)

Шесть картинок сгенерированы нейросетью, шесть — процедурным генератором
(`scripts/pack-wallpapers.py` вызывает тот же `wallpapers.py`, что установлен в
системе). Для KDE Plasma каждая картинка оформлена отдельным KPackage-пакетом
(`/usr/share/wallpapers/FlyArchOs-*`), поэтому они видны в «Параметры системы →
Внешний вид» по отдельности.

## Готовый ISO

Образ собирается автоматически в GitHub Actions и публикуется в
**релизах**: <https://github.com/Nan6767/OsNan/releases>.

* `iso-*-full` — «жирный» образ со всеми наборами ПО (~7,6 ГБ);
* `iso-*-slim` — только два окружения и базовые приложения (~3,7 ГБ);
* рядом с образом лежит `.sha256` и, если он больше 2 ГБ, части
  `.partNN` плюс `JOIN-README.txt` с инструкцией по сборке в один файл.

Целый ISO одним файлом (без нарезки) лежит в артефактах соответствующего
запуска Actions и хранится 90 дней.

## Быстрый старт (сборка из исходников)

```bash
# 1. На Arch Linux (или в контейнере archlinux) ставим инструменты
sudo pacman -S --needed archiso git python python-yaml

# 2. Проверяем, что дерево целое (можно и не на Arch)
make check && make test

# 3. Собираем ISO (~40-60 минут, нужно 40+ ГБ свободного места)
sudo ./scripts/build-iso.sh
```

Готовый образ — в `out/flyarchos-*.iso`. Пишем его на флешку
(`dd`, Ventoy, balenaEtcher) и грузимся в UEFI или BIOS-режиме.

Подробности: **[docs/BUILD.md](docs/BUILD.md)** (сборка) и
**[docs/INSTALL.md](docs/INSTALL.md)** (установка).

## Как устроена установка

ISO собирается «жирным»: в live-системе установлено **всё** (оба окружения и все
наборы ПО). Установка — это распаковка squashfs на диск, поэтому сеть не нужна.
Выбор пользователя превращается в **удаление лишнего**:

```
Calamares: окружение = hyprland, наборы = gaming,media
        ↓
shellprocess@profile:
  flyarchos-profile --apply --desktop=hyprland --extras=gaming,media --remove-live
        ↓
  pacman -Rns  ← пакеты групп plasma, dev, office, live
        (минус всё, что нужно оставшимся группам)
```

Списки пакетов лежат в **`groups/`** — это единственный источник правды:

```
groups/00-core.txt      118  ядро, сеть, диски, звук, консоль
groups/10-common.txt     42  шрифты, темы, Wayland-утилиты
groups/20-hyprland.txt   14  Hyprland + Waybar/Wofi/Mako/Kitty
groups/30-plasma.txt     38  KDE Plasma + SDDM + KDE-приложения
groups/40-apps.txt       10  Firefox, Chromium, Telegram, Discord…
groups/50-dev.txt        32  компиляторы, Docker, ВМ, VS Code
groups/60-gaming.txt     24  Steam, Wine, драйверы (вкл. 32-бит)
groups/70-media.txt      12  GIMP, Krita, Kdenlive, OBS, Blender…
groups/80-office.txt      7  LibreOffice, Thunderbird
groups/99-live.txt        4  Calamares и прочее только для ISO
```

Добавили пакет в `groups/*.txt` → `make packages` → образ и установщик узнают о
нём одновременно.

## Управление после установки

```bash
flyarchos-welcome            # помощник первого запуска (обои, наборы ПО)
flyarchos-wallpaper list     # показать обои
flyarchos-wallpaper set 02-neon-grid
flyarchos-wallpaper random
flyarchos-wallpaper-gen --list        # свои обои: 8 тем, любой seed
flyarchos-profile show --desktop=plasma   # что будет удалено/оставлено
flyarchos-profile --apply --desktop=both --extras=dev,media
flyarchos-info               # краткая справка о системе
```

Горячие клавиши Hyprland: `SUPER+Enter` — терминал, `SUPER+D` — меню,
`SUPER+W` — случайные обои, `SUPER+L` — блокировка, `Print` — скриншот в буфер,
`SUPER+1..0` — рабочие столы, `Alt+Shift` — переключение раскладки us/ru.
Полный список — в `profile/airootfs/etc/skel/.config/hypr/hyprland.conf`.

## Структура репозитория

```
groups/          списки пакетов (источник правды и для ISO, и для установщика)
profile/         archiso-профиль: profiledef.sh, packages.x86_64, airootfs/
  airootfs/etc/calamares/   настройки установщика (settings.conf, modules/, branding/)
  airootfs/etc/skel/        конфиги Hyprland и Plasma для новых пользователей
  airootfs/usr/lib/flyarchos/   инструменты: profile_tool, wallpaper_tool, welcome
scripts/         gen-packages.py, build-iso.sh, build-aur.sh, pack-wallpapers.py, check.py
docker/          Dockerfile для сборки ISO без Arch на хосте
docs/            BUILD.md, INSTALL.md, STRUCTURE.md, preview.png
```

Подробно — **[docs/STRUCTURE.md](docs/STRUCTURE.md)**.

## Статус проекта

Репозиторий содержит **полный исходник дистрибутива**: профиль archiso,
установщик, конфиги окружений, обои, инструменты и проверки (`make check`,
`make test` — 22 теста на логику выбора групп). Сам ISO собирается на машине с
Arch Linux (в песочнице нет ни `pacman`, ни ядер Arch, поэтому готовый образ
здесь не собран) — одна команда `sudo ./scripts/build-iso.sh`.

## Лицензия

Исходники — MIT. Обои и логотип — CC0-1.0. Пакеты принадлежат своим
авторам (Arch Linux, AUR, KDE, Hyprland).
