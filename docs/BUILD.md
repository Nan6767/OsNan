# Сборка ISO FlyArchOs

> **Важно про Calamares.** Графический установщик FlyArchOs — Calamares — **отсутствует
> в официальных репозиториях Arch** (только AUR). Поэтому перед сборкой ISO его нужно
> собрать в локальный репозиторий:
>
> ```bash
> ./scripts/build-aur.sh --with calamares    # или: make aur
> ./scripts/build-iso.sh                     # Calamares подхватится автоматически
> ```
>
> `build-aur.sh` под root сам создаёт пользователя `builder` (makepkg запрещён под root)
> и выдаёт ему `sudo`. Если AUR-пакет не собран, ISO всё равно соберётся — но уже без
> графического установщика (об этом будет предупреждение).


## 0. Что понадобится

| | |
|---|---|
| ОС | Arch Linux (или контейнер `archlinux:latest`) — `mkarchiso` работает через pacman |
| Пакеты | `archiso git python python-yaml` (Python/YAML нужны только для проверок) |
| Место | 40+ ГБ: рабочий каталог ~15 ГБ, кэш пакетов ~10 ГБ, ISO ~10-14 ГБ |
| Права | root (или sudo) — mkarchiso монтирует и делает chroot |
| Время | 40-90 минут в зависимости от зеркала и диска |

> «Жирный» образ: внутри лежит **всё** (оба окружения + все наборы ПО),
> поэтому установка проходит без интернета. Размер ISO ~10-14 ГБ.

## 1. Быстрый путь

```bash
git clone https://github.com/Nan6767/OsNan.git
cd OsNan

make check      # проверка дерева (можно и без Arch)
make test       # 22 модульных теста логики установщика

sudo ./scripts/build-iso.sh
```

Результат:

```
out/flyarchos-2026XX.iso
out/flyarchos-2026XX.iso.sha256
```

## 2. Что делает `build-iso.sh`

1. `scripts/gen-packages.py` — собирает `profile/packages.x86_64` из `groups/*.txt`.
2. Копирует профиль в `work/profile` (исходники не портятся).
3. Кладёт `groups/*.txt` внутрь образа — `/usr/share/flyarchos/groups/`:
   установщик читает их, чтобы удалить невыбранные наборы ПО.
4. Готовит `pacman.conf` из `pacman.conf.in`: включает multilib и, если собран
   локальный репозиторий, добавляет секцию `[flyarchos]`.
5. Добавляет файлы загрузчика из `/usr/share/archiso/configs/releng`
   (`efiboot/`, `syslinux/`, `grub/`, `isolinux/`) и подхватывает оттуда же
   поддерживаемые `bootmodes` — профиль не ломается на другой версии archiso.
6. Запускает `scripts/check.py`.
7. Запускает `mkarchiso -v -w work -o out work/profile`.

Флаги:

```bash
./scripts/build-iso.sh --aur     # сначала собрать AUR-пакеты в локальный репозиторий
./scripts/build-iso.sh --clean   # очистить work/ перед сборкой
./scripts/build-iso.sh --check   # только проверить окружение
./scripts/build-iso.sh -q        # меньше вывода
```

## 3. AUR-пакеты (по желанию)

Пакеты, которых нет в репозиториях Arch (Chrome, Spotify, Proton-GE, темы…),
перечислены в `groups/aur.txt`. Чтобы они попали внутрь ISO:

```bash
make aur                    # = ./scripts/build-aur.sh
sudo ./scripts/build-iso.sh --aur
```

`build-aur.sh` клонирует PKGBUILD из AUR и собирает пакеты:

* в чистом chroot, если установлен `devtools` (`extra-x86_64-build`);
* иначе обычным `makepkg -s` в текущей системе.

Готовые пакеты и база `flyarchos.db.tar.gz` складываются в `repo/x86_64/`,
оттуда их забирает pacman при сборке образа. Если репозитория нет — список
`aur.txt` просто игнорируется, ISO соберётся и без него.

## 4. Сборка в Docker (если Arch нет)

```bash
docker build -t flyarchos-builder docker/
docker run --rm -it --privileged \
    -v "$PWD/out:/flyarchos/out" \
    -v "$PWD/repo:/flyarchos/repo" \
    flyarchos-builder
```

`--privileged` обязателен: mkarchiso работает с loop-устройствами и chroot.
Ключи pacman в контейнере обновляются автоматически при сборке образа.

То же самое одной командой без сборки своего образа:

```bash
docker run --rm -it --privileged -v "$PWD:/flyarchos" -w /flyarchos \
    archlinux:latest ./scripts/ci-build.sh slim   # или full
```

## 4b. Сборка в GitHub Actions (облако)

Если нет ни Arch, ни Docker — соберите образ в облаке:

```bash
gh workflow run iso.yml -f profile=slim -f upload=true
gh run watch            # следить за логом
```

или через веб-интерфейс: **Actions → Build ISO → Run workflow**.

* `slim` — оба окружения без дополнительных наборов (~3-4 ГБ, ~30-50 мин);
* `full` — «жирный» образ со всеми наборами ПО (~10 ГБ, до 5 часов, может
  упереться в место на стандартном раннере);
* готовый ISO появится в артефактах запуска (`flyarchos-slim-iso`) и хранится
  7 дней. Скачать можно со страницы запуска или командой
  `gh run download <id>`.

Workflow освобождает место на раннере (удаляет android/dotnet/ghc) и запускает
`scripts/ci-build.sh` в привилегированном контейнере `archlinux:latest`.

## 5. Обновление состава системы

Все пакеты описаны в `groups/`:

```bash
$EDITOR groups/50-dev.txt      # добавили пакет
make packages                  # пересобрать profile/packages.x86_64
make check                     # убедиться, что ничего не сломалось
```

Как это работает:

* `groups/*.txt` → `profile/packages.x86_64` (что ставить в образ);
* те же файлы попадают в ISO как `/usr/share/flyarchos/groups/` (что удалять
  при установке, если группу не выбрали);
* `id` вариантов в `packagechooser_*.conf` должны совпадать с именами файлов
  групп — это проверяет `make check`.

Обои:

```bash
$EDITOR scripts/pack-wallpapers.py    # каталог CATALOG (id, название, источник)
make wallpapers                       # пересобрать обои, Plasma-пакеты, манифест
make branding                         # логотип, баннер, слайды установщика
```

## 6. Частые проблемы

**`mkarchiso: package not found`** — пакет переименован или есть только в AUR.
Проверьте имя: `pacman -Ss <name>`. Уберите строку из `groups/` или перенесите
её в `groups/aur.txt`.

**`signature from ... is unknown trust` / keyring** — обновите ключи на хосте:

```bash
sudo pacman -Sy archlinux-keyring && sudo pacman-key --populate archlinux
```

**ISO грузится, но установщик не находит squashfs** — проверьте, что
`unpackfs.conf` указывает на `/run/archiso/bootmnt/arch/x86_64/airootfs.sfs`
(именно там он лежит в archiso; при `copytoram` путь другой — поправьте
`modules/unpackfs.conf`).

**Установка падает на этапе `shellprocess@profile`** — это шаг удаления
пакетов. Он не считается фатальным (логи в `/var/log/flyarchos/profile.log`
уже внутри установленной системы), но если мешает — запустите
`flyarchos-profile --apply --desktop=... --extras=...` вручную после перезагрузки.

**Не тот загрузчик/не грузится после установки** — `install-finalize.sh`
проверяет наличие `/boot/grub/grub.cfg` и ставит GRUB, если загрузчика нет.
Логи: `/var/log/flyarchos-install.log`.

**Мало места на диске** — сократите наборы: уберите из `groups/` blender,
krita, kdenlive, libreoffice, virtualbox, qemu-full, nvidia — это самые тяжёлые
пакеты.

## 7. Проверки перед сборкой

```bash
make check
```

Проверяется: синтаксис Python и Bash, YAML Calamares, согласованность
`settings.conf` с модулями и экземплярами, существование скриптов, которые
запускает установщик, совпадение id в `packagechooser` с файлами групп,
наличие обоев/манифеста/пакетов Plasma, конфигов в `/etc/skel`, ярлыков
`.desktop`, брендинга и документации.

```bash
make test
```

22 модульных теста на логику `flyarchos-profile`: что удаляется, что остаётся,
как обрабатываются пересечения групп и неизвестные значения.
