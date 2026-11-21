# NanOs 0.0.1-alpha — архитектура

## Решения

- **Имя системы:** NanOs. Репозиторий остаётся `Nan6767/OsNan`.
- **База:** Kali Linux Rolling.
- **Единственный рабочий стол:** Hyprland. Второй DE/WM не планируется.
- **Сборка:** официальный Kali `kali-live` + `live-build`; ISO собирается только в GitHub Actions, внутри Kali Rolling container.
- **Первый критерий готовности:** live-система загружается в VirtualBox до рабочего стола при EFI, VMSVGA, 128 MiB видеопамяти и 3D-ускорении.
- **Установщик:** позже — минимальный Calamares (разметка, пользователь, распаковка системы, загрузчик и сервисы), без package chooser и каскада shell hooks.

## Этапы

1. Минимальный Kali live-образ с **единственным выбранным** desktop Hyprland: сборка, EFI-загрузка и первый старт в VirtualBox проверяются одним кандидатом.
2. Стабилизировать именно эту Hyprland live-сессию в VirtualBox; никаких дополнительных DE/WM.
3. Минимальный Calamares.
4. Установка на виртуальный диск, перезагрузка и вход в установленную систему.
5. Только после стабильности — бренд NanOs, обои, темы и пользовательские утилиты.

После каждого этапа проверяем результат прежде, чем переходить к следующему. Старые Arch-профиль и сценарии FlyArchOs не являются входом новой сборки; сборщик NanOs использует `nanos/kali-config/`.

## Состав первого live-образа

- `kali-linux-core` и `kali-desktop-live` — базовая система и live-среда Kali.
- Hyprland и минимальный набор Wayland-компонентов (Waybar, Wofi, Foot, Mako, порталы).
- NetworkManager, звук PipeWire и VirtualBox guest utilities.
- Без `kali-linux-default`/`kali-linux-large` и без Plasma, GNOME, Xfce, i3, Sway или другого второго рабочего стола.

Пока образ предназначен только для live-проверки; установщик и установка на диск в этой версии не обещаются.

## Сборка

`./scripts/build-kali-iso.sh` запускается workflow-ом `.github/workflows/iso.yml`. Он клонирует официальный репозиторий Kali `kali-live`, добавляет наш `variant-nanos` и overlays, затем запускает live-build для `kali-rolling/amd64`. В манифест сборки записывается фактический commit `kali-live`, чтобы rolling-обновления можно было диагностировать.
