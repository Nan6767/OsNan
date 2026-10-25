# FlyArchOs — Arch Linux + Hyprland + KDE Plasma в одном установочном ISO.
#
#   make help        показать эту справку
#   make check       проверить дерево (скрипты, YAML, обои, согласованность)
#   make test        модульные тесты логики установщика
#   make packages    пересобрать profile/packages.x86_64 из groups/
#   make wallpapers  собрать обои (AI-исходники + процедурные) и Plasma-пакеты
#   make branding    собрать графику установщика из assets/logo-src
#   make assets      wallpapers + branding
#   make aur         собрать AUR-пакеты в локальный репозиторий (нужен Arch)
#   make iso         собрать ISO (нужен Arch Linux с archiso и root)
#   make all         check + test + packages + iso
#   make clean       удалить work/ и out/

PYTHON ?= python3
SHELL  := /bin/bash

.PHONY: help check test packages wallpapers branding assets aur iso all clean

help:
	@sed -n '1,18p' Makefile | sed 's/^# \{0,1\}//'

check:
	$(PYTHON) scripts/check.py

test:
	$(PYTHON) -m unittest discover -s scripts/tests -v

packages:
	$(PYTHON) scripts/gen-packages.py --stats
	$(PYTHON) scripts/gen-packages.py

wallpapers:
	$(PYTHON) scripts/pack-wallpapers.py

branding:
	$(PYTHON) scripts/make-branding.py

assets: wallpapers branding

aur:
	./scripts/build-aur.sh

iso:
	./scripts/build-iso.sh

all: check test packages iso

clean:
	rm -rf work out
	@echo "Удалены work/ и out/ (ISO и рабочие каталоги)"
