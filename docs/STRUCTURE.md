# Структура репозитория FlyArchOs

```
OsNan/
├── README.md                 главный документ (обзор, быстрый старт)
├── Makefile                  цели: check, test, packages, wallpapers, branding, iso…
├── .gitignore
│
├── groups/                   ★ список пакетов — источник правды
│   ├── 00-core.txt           118  ядро, сеть, диски, звук, консоль
│   ├── 10-common.txt          42  шрифты, темы, Wayland-утилиты
│   ├── 20-hyprland.txt        14  Hyprland + Waybar/Wofi/Mako/Kitty
│   ├── 30-plasma.txt          38  KDE Plasma + SDDM + KDE-приложения
│   ├── 40-apps.txt            10  Firefox, Chromium, Telegram, Discord
│   ├── 50-dev.txt             32  компиляторы, Docker, ВМ, VS Code
│   ├── 60-gaming.txt          24  Steam, Wine, драйверы (вкл. 32-бит)
│   ├── 70-media.txt           12  GIMP, Krita, Kdenlive, OBS, Blender
│   ├── 80-office.txt           7  LibreOffice, Thunderbird
│   ├── 99-live.txt             4  Calamares и прочее только для ISO
│   ├── aur.txt                AUR (в образ только при собранном репозитории)
│   └── README.md              как устроены группы и как их менять
│
├── profile/                  archiso-профиль (mkarchiso)
│   ├── profiledef.sh         имя/лейбл ISO, сжатие squashfs, права файлов
│   ├── pacman.conf.in        шаблон pacman.conf (multilib + локальный репозиторий)
│   ├── packages.x86_64       генерируется скриптом gen-packages.py
│   ├── customize_airootfs.sh настройка live-системы внутри chroot при сборке
│   └── airootfs/             файлы, которые попадут в образ
│       ├── etc/
│       │   ├── calamares/
│       │   │   ├── settings.conf        последовательность шагов установщика
│       │   │   ├── modules/             конфиги модулей (welcome, partition, …)
│       │   │   └── branding/flyarchos/  логотип, баннер, слайды, show.qml
│       │   ├── skel/                    конфиги для новых пользователей
│       │   │   ├── .config/hypr/        hyprland/hypridle/hyprlock/hyprpaper
│       │   │   ├── .config/waybar|wofi|mako|kitty/
│       │   │   ├── .config/kdeglobals, kwinrc, plasma-…-appletsrc   (Plasma)
│       │   │   ├── .config/gtk-3.0|gtk-4.0, .gtkrc-2.0             (GTK)
│       │   │   ├── .config/environment.d/00-flyarchos.conf
│       │   │   └── .zshrc, .bashrc
│       │   ├── sddm.conf.d/             тема SDDM + автовход в live (удаляется)
│       │   ├── mkinitcpio.conf.d/       сжатие initramfs (хуки задаёт установщик)
│       │   ├── sudoers.d/, profile.d/, systemd/zram-generator.conf… системные мелочи
│       ├── usr/
│       │   ├── lib/flyarchos/           ★ инструменты дистрибутива
│       │   │   ├── profile_tool.py      выбор окружения/наборов (удаление групп)
│       │   │   ├── wallpaper_tool.py    обои: Hyprland (swww) и Plasma
│       │   │   ├── wallpapers.py        генератор процедурных обоев
│       │   │   ├── welcome-gui.py       помощник первого запуска (PyQt6/CLI)
│       │   │   ├── install-prepare.sh   шаг установки: чистка live-мусора
│       │   │   ├── install-finalize.sh  шаг установки: обои, SDDM, тема GRUB
│       │   │   ├── flyarchos-info       краткая справка
│       │   │   └── flyarchos-install    запуск Calamares
│       │   ├── bin/flyarchos-*          симлинки на инструменты
│       │   └── share/
│       │       ├── backgrounds/flyarchos/   12 обоев + превью + default.jpg
│       │       ├── wallpapers/FlyArchOs-*/  KPackage-пакеты обоев для Plasma
│       │       ├── flyarchos/               logo.txt, манифест обоев, шаблоны,
│       │       │                            mkinitcpio-пресеты, groups/
│       │       ├── applications/*.desktop   ярлыки установщика и помощника
│       │       └── pixmaps/, icons/         иконка FlyArchOs
│
├── scripts/
│   ├── gen-packages.py       groups/*.txt → profile/packages.x86_64
│   ├── build-iso.sh          подготовка профиля + mkarchiso
│   ├── build-aur.sh          сборка AUR-пакетов в локальный репозиторий repo/
│   ├── pack-wallpapers.py    AI-исходники + процедурные генерации → обои в ISO
│   ├── make-branding.py      логотип → графика установщика и иконки
│   ├── check.py              проверка дерева перед сборкой
│   └── tests/                22 модульных теста (логика выбора групп)
│
├── assets/                   исходники графики
│   ├── wallpapers-src/       6 AI-картинок
│   ├── logo-src/logo.png     логотип
│   └── favicon.png
│
├── docker/Dockerfile         сборка ISO в контейнере archlinux
└── docs/                     BUILD.md, INSTALL.md, STRUCTURE.md, preview.png
```

## Кто за что отвечает

### `groups/` — один источник правды

Файлы `NN-имя.txt` читаются дважды:

1. `scripts/gen-packages.py` собирает из них `profile/packages.x86_64` — что
   поставить в live-систему;
2. копия кладётся внутрь образа (`/usr/share/flyarchos/groups/`) — установщик
   по ним понимает, какие пакеты удалить, если группу не выбрали.

Пересечения допустимы: пакет удаляется, только если он не нужен ни одной из
выбранных групп.

### `flyarchos-profile` — «разнообразие» установки

ISO «жирный»: всё уже стоит. Выбор в Calamares (`packagechooser`, метод
`legacy`) превращается в строку, которую Calamares подставляет в команду:

```
flyarchos-profile --apply --desktop=${gs[packagechooser_desktop]}
                          --extras=${gs[packagechooser_extras]} --remove-live
```

Дальше считается `удаляемое = все группы − выбранные − обязательные`,
пакеты фильтруются по `pacman -Q` и удаляются пачками (`pacman -Rns`),
потом подчищаются осиротевшие зависимости. Результат пишется в
`/etc/flyarchos/profile.json`, его читает `install-finalize.sh`.

Без `--apply` утилита ничего не меняет, а печатает план — это же поведение
покрыто тестами в `scripts/tests/`.

### Calamares

* `settings.conf` задаёт три экземпляра `packagechooser` (окружение, наборы ПО,
  загрузчик) и три `shellprocess` (prepare, profile, finalize);
* установка идёт через `unpackfs` (распаковка `airootfs.sfs`), поэтому сеть не
  нужна;
* `initcpiocfg` + `initcpio` отвечают за mkinitcpio (в т.ч. LUKS),
  `grubcfg` + `bootloader` — за GRUB, `efiBootLoaderVar` читает выбор
  загрузчика из global storage;
* `install-finalize.sh` страхует установку: если загрузчика нет — ставит GRUB.

### Обои

`scripts/pack-wallpapers.py`:

* масштабирует 6 AI-картинок до 1920×1080;
* генерирует 6 процедурных обоев в 2560×1440 тем же `wallpapers.py`, что
  установлен в системе (один алгоритм — везде);
* делает превью, `default.jpg`, фон для GRUB, манифест
  `/usr/share/flyarchos/wallpapers.json`;
* собирает KPackage-пакеты `/usr/share/wallpapers/FlyArchOs-*` для Plasma;
* сохраняет контактный лист в `docs/preview.png`.
