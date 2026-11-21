# Сборка NanOs ISO

NanOs основана на Kali Linux Rolling и собирается официальной инфраструктурой Kali `kali-live`/`live-build`. Сам ISO в песочнице не собирается: сборка запускается GitHub Actions в Kali Rolling container.

## Запуск

- Автоматически: изменение `BUILD_ISO.txt` запускает workflow **Build NanOs ISO**.
- Вручную: GitHub → Actions → **Build NanOs ISO** → Run workflow.

После успеха ISO, SHA-256, manifest и build log доступны в артефакте запуска Actions. Первые кандидаты не публикуются в постоянный релиз до прохождения проверки в VirtualBox.

## Что делает workflow

1. Запускает `kalilinux/kali-rolling` как привилегированный контейнер (это нужно live-build для chroot/mount).
2. Устанавливает `git`, `live-build` и `cdebootstrap`.
3. `scripts/build-kali-iso.sh` клонирует официальный `kali-live`, добавляет `nanos/kali-config/` в `variant-nanos` и вызывает `build.sh --distribution kali-rolling --variant nanos --arch amd64`.
4. Сохраняет commit `kali-live`, версию Hyprland из собранного chroot (если live-build сохраняет dpkg database), имя образа `nanos-0.0.1-alpha-amd64.iso` и SHA-256.

Версии Kali Rolling и Hyprland меняются. В образе лежат конфиги Hyprland 0.56-style (`hyprland.conf`) и 0.57+ (`hyprland.lua`), но это не заменяет реальный запуск: build log и manifest фиксируют данные кандидата, а совместимость подтверждается только VirtualBox-тестом.

## Локальные проверки без сборки ISO

```bash
python3 scripts/check-nanos-config.py
bash -n scripts/build-kali-iso.sh
```

Эти проверки не заменяют GitHub Actions и не подтверждают загрузку ISO.
