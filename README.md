<h1 align="center">NanOs</h1>

<p align="center">
  <strong>Kali Linux Rolling + Hyprland — ровно один рабочий стол.</strong><br>
  Версия <code>0.0.1-alpha</code>. Первый этап — проверить live-загрузку в VirtualBox.
</p>

<p align="center">
  <a href="https://github.com/Nan6767/OsNan/actions/workflows/ci.yml">
    <img alt="CI" src="https://github.com/Nan6767/OsNan/actions/workflows/ci.yml/badge.svg?branch=main">
  </a>
  <a href="https://github.com/Nan6767/OsNan/actions/workflows/iso.yml">
    <img alt="Build ISO" src="https://github.com/Nan6767/OsNan/actions/workflows/iso.yml/badge.svg?branch=main">
  </a>
</p>

> [!WARNING]
> Первый запуск текущего ISO в VirtualBox дошёл до рабочего стола Hyprland, но показал предупреждения о недостающем `hyprland-qtutils` и запуске без `start-hyprland`. Проверка live-сценария ещё не завершена: исправления внесены в конфигурацию, но новый кандидат нужно собрать и проверить. Calamares и установка на диск пока не входят в образ. Не устанавливайте NanOs на рабочий компьютер.

## Что уже выбрано

- **Система:** NanOs, репозиторий `Nan6767/OsNan`.
- **База:** Kali Linux Rolling.
- **Единственный desktop:** Hyprland. Plasma и другие DE/WM не устанавливаются.
- **Версия:** `0.0.1-alpha` (pre-release).
- **Первый критерий:** live-сессия открывает Hyprland в VirtualBox (EFI, VMSVGA, 128 МБ видео, 3D ON).
- **Сборка ISO:** только GitHub Actions, на официальной Kali `kali-live`/`live-build` инфраструктуре.

## Получить ISO

Последний успешный кандидат: [сборка GitHub Actions #44996495267](https://github.com/Nan6767/OsNan/actions/runs/44996495267). На странице запуска скачайте артефакт `nanos-0.0.1-alpha-69`; в ZIP находятся ISO, SHA-256, build manifest и лог. При первом запуске в VirtualBox он дошёл до Hyprland, но показал два предупреждения. Исправления включены в текущую конфигурацию; новый кандидат ещё не собран. Постоянного релиза нет.

Workflow можно запустить вручную или изменением `BUILD_ISO.txt`. Подробности: [сборка](docs/BUILD.md), [архитектура и этапы](docs/ARCHITECTURE.md).

## Запуск в VirtualBox

1. Создайте VM типа **Linux / Debian (64-bit)**, выделите 4 ГБ RAM и 2 CPU.
2. Включите **EFI**, отключите Secure Boot.
3. В **Display** выберите **VMSVGA**, 128 МБ видеопамяти и включите **3D Acceleration**.
4. Подключите NanOs ISO как DVD и загрузитесь с него.
5. Ожидаемый результат: live-пользователь `kali` входит автоматически, запускается Hyprland, сверху появляется Waybar.

Основные клавиши: `Super+Enter` — терминал Foot, `Super+D` — меню Wofi, `Super+Q` — закрыть окно, `Super+Shift+E` — выйти из Hyprland. При проблемах сначала проверяем live-сессию; второй рабочий стол добавлять не будем. Полный тест-лист: [VirtualBox](docs/VIRTUALBOX-TEST.md).

## Структура новой сборки

- `nanos/kali-config/` — отдельный Kali live-build overlay NanOs.
- `scripts/build-kali-iso.sh` — сборщик, вызываемый только workflow-ом.
- `scripts/check-nanos-config.py` — быстрые статические проверки без сторонних Python-модулей.

В корне ещё могут находиться неиспользуемые материалы прежней Arch-версии; они не являются входом NanOs-сборки и будут удалены после подтверждения нового live-образа.
