# Группы пакетов FlyArchOs

Каталог — **единый источник правды** о пакетах. Из этих файлов генерируются:

* `profile/packages.x86_64` — список пакетов для `mkarchiso` (скрипт `scripts/gen-packages.py`);
* `/usr/share/flyarchos/groups/*.txt` внутри ISO — их читает установщик
  (`flyarchos-profile`), чтобы **удалить** пакеты невыбранных групп
  (ISO «жирный»: всё уже стоит в live-системе, установка — это копирование
  squashfs + подчистка).

## Файлы

| Файл | ID группы | Обязательная | Что внутри |
|---|---|---|---|
| `00-core.txt` | `core` | да | ядро, сеть, диски, звук, консоль |
| `10-desktop-common.txt` | `common` | да | шрифты, темы, Wayland-утилиты |
| `20-hyprland.txt` | `hyprland` | выбор в установщике | Hyprland + waybar/wofi/mako/kitty |
| `30-plasma.txt` | `plasma` | выбор в установщике | KDE Plasma + SDDM + KDE-приложения |
| `40-apps.txt` | `apps` | да | Firefox, Chromium, Telegram, Discord… |
| `50-dev.txt` | `dev` | выбор в установщике | компиляторы, Docker, ВМ, IDE |
| `60-gaming.txt` | `gaming` | выбор в установщике | Steam, Wine, драйверы |
| `70-media.txt` | `media` | выбор в установщике | GIMP, Kdenlive, OBS, Blender… |
| `80-office.txt` | `office` | выбор в установщике | LibreOffice, Thunderbird |
| `99-live.txt` | `live` | нет | Calamares и прочее только для ISO |

## Формат

* один пакет на строку;
* `#` — комментарий, пустые строки игнорируются;
* дубликаты между группами допустимы: при удалении групп пересечения
  вычитаются (пакет остаётся, если он нужен хотя бы одной выбранной группе).

## Как добавить пакет

1. Добавьте имя пакета в нужный файл (проверьте, что он есть в репозиториях
   Arch: `pacman -Ss <name>`).
2. `make packages` — пересобрать `profile/packages.x86_64`.
3. `make check` — проверить дерево.
