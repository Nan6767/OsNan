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
> Это новый проект и **ISO ещё не подтверждён загрузкой в VirtualBox**. Calamares и установка на диск пока не входят в образ. Не используйте NanOs для установки на рабочий компьютер.

## Что уже выбрано

- **Система:** NanOs, репозиторий `Nan6767/OsNan`.
- **База:** Kali Linux Rolling.
- **Единственный desktop:** Hyprland. Plasma и другие DE/WM не устанавливаются.
- **Версия:** `0.0.1-alpha` (pre-release).
- **Первый критерий:** live-сессия открывает Hyprland в VirtualBox (EFI, VMSVGA, 128 МБ видео, 3D ON).
- **Сборка ISO:** только GitHub Actions, на официальной Kali `kali-live`/`live-build` инфраструктуре.

## Получить ISO

Откройте **Actions → Build NanOs ISO**, дождитесь успешной сборки и скачайте артефакт `nanos-0.0.1-alpha-<run>`. В нём будут ISO, SHA-256, build manifest и лог. Пока проверка VirtualBox не пройдена, постоянного релиза нет.

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
