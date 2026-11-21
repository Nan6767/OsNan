# NanOs — Kali Rolling + one Hyprland desktop.
# ISO builds run only in GitHub Actions; local targets perform static checks.

PYTHON ?= python3
SHELL  := /bin/bash

.PHONY: help check test iso clean

help:
	@printf '%s\n' \
	  'make check   static checks for NanOs Kali config' \
	  'make test    check + shell syntax checks' \
	  'make iso     explain how to run the GitHub Actions build' \
	  'make clean   remove generated work/ and out/'

check:
	$(PYTHON) scripts/check-nanos-config.py

test:
	$(PYTHON) scripts/check-nanos-config.py
	bash -n scripts/build-kali-iso.sh

iso:
	@echo 'ISO is built only in GitHub Actions: Actions -> Build NanOs ISO.'

clean:
	rm -rf work out
