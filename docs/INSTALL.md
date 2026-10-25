# Установка FlyArchOs

## 1. Загрузка с флешки

1. Запишите ISO: `sudo dd if=flyarchos-2026XX.iso of=/dev/sdX bs=4M status=progress oflag=sync`
   (или Ventoy / balenaEtcher — поддерживается и UEFI, и BIOS).
2. Загрузитесь с флешки. Live-сессия сама войдёт в **Hyprland** под
   пользователем `fly` (пароль `flyarchos`, у root тот же пароль).
3. На экране входа SDDM можно выйти и выбрать другую сессию —
   **Plasma (Wayland)**, **Plasma (X11)** или **Hyprland** — чтобы посмотреть
   оба окружения до установки.

> Хотите консоль? `Ctrl+Alt+F2…F6` — обычные tty, вход `fly` / `flyarchos`.

## 2. Запуск установщика

* Ярлык **Install FlyArchOs** на рабочем столе,
* или `flyarchos-install` в терминале (поднимается Calamares),
* запасной вариант — `archinstall` (консольный установщик Arch).

Интернет **не нужен**: все пакеты уже внутри образа.

## 3. Шаги мастера

| Шаг | Что выбрать |
|---|---|
| **Приветствие** | язык интерфейса (русский включён), проверка места/памяти |
| **Регион и язык** | `ru_RU.UTF-8`, часовой пояс (по умолчанию Europe/Kaliningrad) |
| **Клавиатура** | модель и раскладка; можно добавить `Russian` и переключатель |
| **Разметка** | «Стереть диск» для автоматики или «Вручную» — ниже подробнее |
| **Рабочее окружение** | `Hyprland` / `KDE Plasma` / **оба сразу (рекомендуется)** |
| **Наборы ПО** | Разработка · Игры · Мультимедиа · Офис — любые комбинации |
| **Загрузчик** | `GRUB` (универсально) или `systemd-boot` (только UEFI) |
| **Пользователь** | имя, пароль, пароль root, имя компьютера |
| **Сводка** | проверьте и нажимайте «Установить» |

### Про разметку

* Файловая система по умолчанию — **btrfs**; доступны ext4 и xfs.
* Swap — **файлом** (по умолчанию), можно «нет», «маленький» или «для гибернации».
  Дополнительно в системе настроен **zram** (`/etc/systemd/zram-generator.conf`).
* **Шифрование LUKS** — включите «Encrypt system»: пароль спросит установщик,
  mkinitcpio соберётся с хуком `encrypt` автоматически (этим занимается
  модуль `initcpiocfg`).
* Ручная разметка — обычный интерфейс Calamares: GPT, отдельный ESP
  (`/boot/efi`, 512 МБ, FAT32), корень и, по желанию, отдельный `/home`.

### Что происходит во время установки

```
partition → mount → unpackfs         распаковка live-системы на диск
shellprocess@prepare                 чистка live-мусора, mkinitcpio-пресеты,
                                     удаление пользователя fly
machineid → fstab → locale → localecfg → keyboard → hostinfo → networkcfg
initcpiocfg                          mkinitcpio.conf под ваше железо (в т.ч. LUKS)
shellprocess@profile                 удаление пакетов невыбранных групп
hwclock → services-systemd → users → displaymanager
initcpio → grubcfg → bootloader      ядро, GRUB/systemd-boot
shellprocess@finalize                обои, сессия SDDM, тема GRUB, контроль загрузчика
umount
```

Логи: `/var/log/flyarchos-install.log` и `/var/log/flyarchos/profile.log`
внутри установленной системы.

## 4. После установки

1. Перезагрузитесь, войдите в SDDM.
   Если выбраны оба окружения — перед входом внизу/вверху есть список сессий:
   **Plasma (Wayland)**, **Plasma (X11)**, **Hyprland**.
   По умолчанию подставляется то, что вы указали в установщике
   (`/var/lib/sddm/state.conf`).
2. Откроется **помощник первого запуска** (`flyarchos-welcome`): обои, наборы
   ПО, обновление. Снять галочку «показывать при входе» — больше не появится.

### Полезные команды

```bash
flyarchos-welcome                # помощник первого запуска
flyarchos-wallpaper list         # 12 обоев
flyarchos-wallpaper set 05-nord-fjord
flyarchos-wallpaper random
flyarchos-wallpaper-gen --list   # сгенерировать свои обои (8 тем + свой seed)
flyarchos-info                   # справка о системе и подсказки
flyarchos-profile show --desktop=plasma --extras=dev
flyarchos-profile --apply --desktop=both --extras=dev,media   # изменить набор ПО
```

`flyarchos-profile` можно запускать в любой момент: он удалит пакеты
невыбранных групп и доставит недостающие (для последнего нужна сеть).

### Обновление системы

```bash
sudo pacman -Syu           # обычное обновление
paru  /  yay               # AUR (пары стоят, если собирали репозиторий)
flatpak update             # Flatpak-приложения
```

## 5. Горячие клавиши Hyprland

| Клавиши | Действие |
|---|---|
| `SUPER+Enter` | терминал Kitty |
| `SUPER+D` | меню приложений (Wofi) |
| `SUPER+B` / `SUPER+E` | Firefox / Thunar |
| `SUPER+Q` | закрыть окно |
| `SUPER+F` | полный экран |
| `SUPER+V` | плавающее окно |
| `SUPER+L` | блокировка экрана (hyprlock) |
| `SUPER+W` | случайные обои |
| `SUPER+P` | скриншот области в буфер обмена |
| `Print` | скриншот всего экрана в буфер обмена |
| `SUPER+1…0` | рабочие столы 1…10 |
| `SUPER+Shift+1…0` | отправить окно на рабочий стол |
| `SUPER+стрелки` | перемещение фокуса |
| `Alt+Shift` | переключить us/ru |
| мультимедийные клавиши | громкость, яркость, плеер |

## 6. Если что-то пошло не так

* **Не грузится после установки.** Загрузитесь с флешки, смонтируйте корень и
  переустановите GRUB:
  ```bash
  mount /dev/sdXY /mnt && mount /dev/sdX1 /mnt/boot/efi   # ESP
  arch-chroot /mnt
  grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=FlyArchOs
  grub-mkconfig -o /boot/grub/grub.cfg
  ```
* **Хочу вернуть удалённые пакеты.** `flyarchos-profile --apply --desktop=both
  --extras=dev,gaming,media,office --install-missing` (нужна сеть).
* **Чёрный экран в Hyprland на NVIDIA.** На экране входа выберите
  **Plasma (X11)** или добавьте `nvidia_drm.modeset=1` в
  `GRUB_CMDLINE_LINUX_DEFAULT` (`/etc/default/grub` → `grub-mkconfig`).
* **Нет сети.** `nmcli device wifi list` / `nmtui` — NetworkManager включён.
* **Где логи установки:** `/var/log/flyarchos-install.log`.
