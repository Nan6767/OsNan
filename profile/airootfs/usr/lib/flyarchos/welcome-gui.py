#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FlyArchOs — помощник первого запуска.

Запускается один раз после первого входа (через /etc/xdg/autostart) и
предлагает:

* выбрать обои (12 штук + случайные + генератор своих);
* изменить набор ПО (окружение и группы пакетов, как при установке);
* обновить систему;
* посмотреть краткую справку.

Если Qt не установлен — работает текстовое меню в терминале.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MANIFEST = Path("/usr/share/flyarchos/wallpapers.json")
LOGO = Path("/usr/share/pixmaps/flyarchos.png")
STATE_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "flyarchos"
DONE_FLAG = STATE_DIR / "welcome-done"

APP_TITLE = "FlyArchOs — помощник первого запуска"


# --------------------------------------------------------------------------- #
# Данные
# --------------------------------------------------------------------------- #
def wallpapers() -> list[dict]:
    """Список обоев из манифеста (id, название, файл, превью)."""
    if not MANIFEST.is_file():
        return []
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = data.get("wallpapers", []) if isinstance(data, dict) else data
    return [item for item in items if Path(item["file"]).is_file()]


def run_visible(command: list[str]) -> None:
    """Запустить команду «как видно пользователю»: в терминале или через pkexec."""
    term = shutil.which("kitty") or shutil.which("konsole") or shutil.which("xterm")
    needs_root = command[0] in ("flyarchos-profile", "pacman", "paru", "yay")
    if needs_root:
        if shutil.which("pkexec"):
            command = ["pkexec", *command]
        elif shutil.which("kdesu"):
            command = ["kdesu", "-c", " ".join(command)]
        elif shutil.which("sudo") and term:
            command = [term, "-e", "sudo", *command]
    if needs_root or not term:
        subprocess.Popen(command, start_new_session=True)
    else:
        subprocess.Popen([term, "-e", *command], start_new_session=True)


def set_wallpaper(identifier: str) -> bool:
    """Поставить обои через flyarchos-wallpaper."""
    if not shutil.which("flyarchos-wallpaper"):
        return False
    return subprocess.run(
        ["flyarchos-wallpaper", "set", identifier], capture_output=True
    ).returncode == 0


def set_done(done: bool) -> None:
    """Флаг «больше не показывать»."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if done:
        DONE_FLAG.write_text("done\n", encoding="utf-8")
    elif DONE_FLAG.exists():
        DONE_FLAG.unlink()


# --------------------------------------------------------------------------- #
# Текстовый режим (fallback без Qt)
# --------------------------------------------------------------------------- #
def cli_mode() -> int:
    items = wallpapers()
    print(APP_TITLE)
    print()
    print("1) Выбрать обои")
    print("2) Случайные обои")
    print("3) Изменить набор ПО")
    print("4) Обновить систему")
    print("5) Справка о системе")
    print("0) Выход")
    choice = input("\nВыберите пункт: ").strip()
    if choice == "1":
        for i, item in enumerate(items, 1):
            print(f"  {i:>2}) {item['id']:<20} {item.get('title', '')}")
        idx = input("Номер обоев: ").strip()
        try:
            set_wallpaper(items[int(idx) - 1]["id"])
        except (ValueError, IndexError):
            print("не понял номер")
    elif choice == "2":
        set_wallpaper("random")
    elif choice == "3":
        run_visible(["flyarchos-profile", "--apply", "--desktop=both", "--extras=dev,media"])
    elif choice == "4":
        run_visible(["pacman", "-Syu"])
    elif choice == "5":
        subprocess.run(["flyarchos-info"])
    return 0


# --------------------------------------------------------------------------- #
# Графический режим
# --------------------------------------------------------------------------- #
def gui_mode() -> int:
    try:
        from PyQt6.QtCore import Qt, QSize
        from PyQt6.QtGui import QIcon, QPixmap, QFont
        from PyQt6.QtWidgets import (
            QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QGridLayout,
            QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
            QPushButton, QTextEdit, QVBoxLayout, QWidget,
        )
    except ImportError:
        try:
            from PySide6.QtCore import Qt, QSize
            from PySide6.QtGui import QIcon, QPixmap, QFont
            from PySide6.QtWidgets import (
                QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QGridLayout,
                QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                QPushButton, QTextEdit, QVBoxLayout, QWidget,
            )
        except ImportError:
            print("Qt не найден — переключаюсь в текстовый режим.", file=sys.stderr)
            return cli_mode()

    app = QApplication(sys.argv)
    app.setApplicationName("flyarchos-welcome")

    window = QMainWindow()
    window.setWindowTitle(APP_TITLE)
    if LOGO.is_file():
        window.setWindowIcon(QIcon(str(LOGO)))
    window.resize(880, 620)

    central = QWidget()
    layout = QVBoxLayout(central)
    layout.setContentsMargins(28, 24, 28, 20)
    layout.setSpacing(16)

    # --- шапка ------------------------------------------------------------
    header = QHBoxLayout()
    if LOGO.is_file():
        logo = QLabel()
        pixmap = QPixmap(str(LOGO)).scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
        logo.setPixmap(pixmap)
        header.addWidget(logo)
    titles = QVBoxLayout()
    title = QLabel("Добро пожаловать в FlyArchOs")
    title.setFont(QFont("Noto Sans", 20, QFont.Weight.Bold))
    subtitle = QLabel("Arch Linux с Hyprland и KDE Plasma. Ниже — всё, что обычно нужно сразу после установки.")
    subtitle.setWordWrap(True)
    titles.addWidget(title)
    titles.addWidget(subtitle)
    header.addLayout(titles, 1)
    layout.addLayout(header)

    # --- обои -------------------------------------------------------------
    layout.addWidget(QLabel("<b>Обои</b>"))
    grid = QGridLayout()
    items = wallpapers()
    for index, item in enumerate(items):
        button = QPushButton()
        button.setToolTip(item.get("title", item["id"]))
        thumb = item.get("thumb")
        if thumb and Path(thumb).is_file():
            button.setIcon(QIcon(thumb))
            button.setIconSize(QSize(200, 112))
        button.setFixedSize(212, 150)
        button.setText(item.get("title", item["id"]))
        button.setStyleSheet("QPushButton { padding-top: 4px; }")
        button.clicked.connect(lambda _checked=False, ident=item["id"]: (
            set_wallpaper(ident),
            status.setText(f"Обои установлены: {ident}"),
        ))
        grid.addWidget(button, index // 6, index % 6)
    layout.addLayout(grid)

    wall_row = QHBoxLayout()
    def pick_random() -> None:
        set_wallpaper("random")
        status.setText("Выбраны случайные обои")

    random_btn = QPushButton("Случайные обои")
    random_btn.clicked.connect(pick_random)
    gen_btn = QPushButton("Сгенерировать свои…")
    gen_btn.clicked.connect(lambda: run_visible(["flyarchos-wallpaper-gen", "--all", "--out",
                                                 str(Path.home() / "Изображения" / "flyarchos")]))
    wall_row.addWidget(random_btn)
    wall_row.addWidget(gen_btn)
    wall_row.addStretch(1)
    layout.addLayout(wall_row)

    # --- набор ПО ---------------------------------------------------------
    layout.addWidget(QLabel("<b>Наборы ПО</b> (как при установке — лишнее будет удалено)"))
    software_row = QHBoxLayout()
    desktop_combo = QComboBox()
    desktop_combo.addItem("Hyprland + KDE Plasma (оба)", "both")
    desktop_combo.addItem("Только Hyprland", "hyprland")
    desktop_combo.addItem("Только KDE Plasma", "plasma")
    software_row.addWidget(QLabel("Окружение:"))
    software_row.addWidget(desktop_combo)
    extras: dict[str, QCheckBox] = {}
    for key, label in (("dev", "Разработка"), ("gaming", "Игры"),
                       ("media", "Мультимедиа"), ("office", "Офис")):
        box = QCheckBox(label)
        box.setChecked(True)
        extras[key] = box
        software_row.addWidget(box)
    software_row.addStretch(1)
    layout.addLayout(software_row)

    def apply_software() -> None:
        chosen = [key for key, box in extras.items() if box.isChecked()]
        desktop = desktop_combo.currentData()
        answer = QMessageBox.question(
            window, "Изменить набор ПО",
            f"Окружение: {desktop}\nНаборы: {', '.join(chosen) or 'нет'}\n\n"
            "Пакеты невыбранных групп будут удалены. Продолжить?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            run_visible(["flyarchos-profile", "--apply",
                         f"--desktop={desktop}", f"--extras={','.join(chosen)}"])
            status.setText("Изменения применяются в отдельном окне.")

    # --- кнопки действий --------------------------------------------------
    actions = QHBoxLayout()
    apply_btn = QPushButton("Применить набор ПО")
    apply_btn.clicked.connect(apply_software)
    update_btn = QPushButton("Обновить систему")
    update_btn.clicked.connect(lambda: run_visible(["flyarchos-update"]))
    info_btn = QPushButton("О системе")
    info_btn.clicked.connect(lambda: run_visible(["flyarchos-info"]))
    actions.addWidget(apply_btn)
    actions.addWidget(update_btn)
    actions.addWidget(info_btn)
    actions.addStretch(1)
    layout.addLayout(actions)

    # --- инструменты FlyArchOs ---------------------------------------------
    hold = lambda cmd: ["sh", "-c", cmd + "; echo; read -p 'Enter — закрыть окно' _"]
    tools = QHBoxLayout()
    doctor_btn = QPushButton("Диагностика")
    doctor_btn.clicked.connect(lambda: run_visible(hold("flyarchos-doctor")))
    theme_btn = QPushButton("Следующая тема")
    theme_btn.clicked.connect(
        lambda: subprocess.Popen(["flyarchos-theme", "next"], start_new_session=True))
    snap_btn = QPushButton("Снимки системы")
    snap_btn.clicked.connect(lambda: run_visible(hold("flyarchos-snapshot")))
    backup_btn = QPushButton("Резервная копия")
    backup_btn.clicked.connect(lambda: run_visible(hold("flyarchos-backup")))
    clean_btn = QPushButton("Уборка")
    clean_btn.clicked.connect(lambda: run_visible(hold("flyarchos-clean")))
    aur_btn = QPushButton("AUR (yay)")
    aur_btn.clicked.connect(lambda: run_visible(hold("flyarchos-aur install")))
    autobak_btn = QPushButton("Автобэкап")
    autobak_btn.clicked.connect(lambda: run_visible(hold("flyarchos-backup auto status")))
    exe_btn = QPushButton("Программы .exe")
    exe_btn.clicked.connect(lambda: run_visible(hold("flyarchos-exe setup")))
    for btn in (doctor_btn, theme_btn, snap_btn, backup_btn, clean_btn,
                aur_btn, autobak_btn, exe_btn):
        tools.addWidget(btn)
    tools.addStretch(1)
    layout.addLayout(tools)

    # --- низ окна ---------------------------------------------------------
    status = QLabel("")
    status.setWordWrap(True)
    show_box = QCheckBox("Показывать это окно при следующем входе")
    show_box.setChecked(True)
    show_box.stateChanged.connect(lambda _state: set_done(not show_box.isChecked()))
    bottom = QHBoxLayout()
    bottom.addWidget(show_box, 1)
    close_btn = QPushButton("Закрыть")
    close_btn.clicked.connect(window.close)
    bottom.addWidget(close_btn)
    layout.addStretch(1)
    layout.addWidget(status)
    layout.addLayout(bottom)

    window.setCentralWidget(central)
    window.show()
    return app.exec()


def main() -> int:
    autostart = "--autostart" in sys.argv
    if autostart and DONE_FLAG.exists() and "--force" not in sys.argv:
        return 0
    if "--cli" in sys.argv:
        return cli_mode()
    return gui_mode()


if __name__ == "__main__":
    raise SystemExit(main())
