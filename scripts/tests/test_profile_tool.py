#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Модульные тесты логики установщика FlyArchOs.

Запуск::

    make test
    python3 -m unittest discover -s scripts/tests -v

Тесты не требуют Arch Linux и не трогают систему: pacman не вызывается,
проверяется только математика выбора групп пакетов.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROFILE_TOOL = REPO / "profile" / "airootfs" / "usr" / "lib" / "flyarchos" / "profile_tool.py"
GEN_PACKAGES = REPO / "scripts" / "gen-packages.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


profile_tool = load_module("flyarchos_profile_tool", PROFILE_TOOL)
gen_packages = load_module("gen_packages", GEN_PACKAGES)


class NormalizeTest(unittest.TestCase):
    def test_desktop_values(self):
        self.assertEqual(profile_tool.normalize_desktop("hyprland"), "hyprland")
        self.assertEqual(profile_tool.normalize_desktop("plasma"), "plasma")
        self.assertEqual(profile_tool.normalize_desktop("Hyprland,Plasma"), "both")
        self.assertEqual(profile_tool.normalize_desktop(""), "both")
        self.assertEqual(profile_tool.normalize_desktop(None), "both")
        self.assertEqual(profile_tool.normalize_desktop("both"), "both")

    def test_desktop_unknown(self):
        with self.assertRaises(profile_tool.ProfileError):
            profile_tool.normalize_desktop("gnome")

    def test_extras(self):
        self.assertEqual(profile_tool.normalize_extras("dev,gaming"), ["dev", "gaming"])
        self.assertEqual(profile_tool.normalize_extras("dev; gaming"), ["dev", "gaming"])
        self.assertEqual(profile_tool.normalize_extras(""), [])
        self.assertEqual(profile_tool.normalize_extras("dev,dev"), ["dev"])

    def test_extras_unknown(self):
        with self.assertRaises(profile_tool.ProfileError):
            profile_tool.normalize_extras("minecraft")


class GroupLogicTest(unittest.TestCase):
    def setUp(self):
        self.groups = {
            "core": ["linux", "pacman"],
            "common": ["swww", "grim"],
            "apps": ["firefox"],
            "hyprland": ["hyprland", "waybar"],
            "plasma": ["plasma-meta", "dolphin"],
            "dev": ["git-lfs", "code"],
            "gaming": ["steam"],
            "media": ["vlc"],
            "office": ["libreoffice-fresh"],
            "live": ["calamares"],
        }

    def test_kept_groups_both(self):
        kept = profile_tool.kept_groups("both", ["dev"], remove_live=True)
        self.assertEqual(kept, ["core", "common", "apps", "hyprland", "plasma", "dev"])

    def test_kept_groups_hyprland_only(self):
        kept = profile_tool.kept_groups("hyprland", [], remove_live=True)
        self.assertNotIn("plasma", kept)
        self.assertIn("hyprland", kept)
        self.assertNotIn("live", kept)

    def test_keep_live_flag(self):
        kept = profile_tool.kept_groups("plasma", [], remove_live=False)
        self.assertIn("live", kept)

    def test_plasma_removed_for_hyprland(self):
        plan = profile_tool.packages_to_remove(self.groups, profile_tool.kept_groups("hyprland", [], True))
        self.assertIn("plasma", plan)
        self.assertIn("plasma-meta", plan["plasma"])
        self.assertNotIn("hyprland", plan)
        self.assertNotIn("waybar", sum(plan.values(), []))

    def test_shared_package_is_kept(self):
        """Пакет, входящий и в выбранную, и в невыбранную группу, не удаляется."""
        self.groups["media"].append("firefox")  # firefox есть и в apps
        plan = profile_tool.packages_to_remove(self.groups, profile_tool.kept_groups("both", [], True))
        all_removed = sum(plan.values(), [])
        self.assertNotIn("firefox", all_removed)
        self.assertIn("vlc", all_removed)

    def test_core_is_never_removed(self):
        plan = profile_tool.packages_to_remove(self.groups, profile_tool.kept_groups("hyprland", [], True))
        all_removed = sum(plan.values(), [])
        for pkg in ("linux", "pacman", "swww", "grim", "firefox"):
            self.assertNotIn(pkg, all_removed)

    def test_live_removed_only_when_asked(self):
        plan = profile_tool.packages_to_remove(self.groups, profile_tool.kept_groups("both", [], True))
        self.assertIn("calamares", plan["live"])
        plan = profile_tool.packages_to_remove(self.groups, profile_tool.kept_groups("both", [], False))
        self.assertNotIn("live", plan)

    def test_removal_order(self):
        plan = profile_tool.packages_to_remove(self.groups, profile_tool.kept_groups("hyprland", [], True))
        order = list(plan)
        self.assertEqual(order, ["live", "office", "media", "gaming", "dev", "plasma"])


class RealGroupsTest(unittest.TestCase):
    """Проверяем на настоящих файлах groups/ — как это будет в системе."""

    @classmethod
    def setUpClass(cls):
        cls.groups = profile_tool.load_groups(REPO / "groups")

    def test_groups_loaded(self):
        for name in ("core", "common", "hyprland", "plasma", "apps", "dev", "gaming", "media", "office", "live"):
            self.assertIn(name, self.groups)
            self.assertTrue(self.groups[name])

    def test_no_desktop_packages_in_removal_when_both(self):
        plan = profile_tool.packages_to_remove(self.groups, profile_tool.kept_groups("both", [], True))
        removed = set(sum(plan.values(), []))
        for pkg in ("hyprland", "waybar", "plasma-meta", "dolphin", "sddm"):
            self.assertNotIn(pkg, removed, f"{pkg} не должен удаляться при выборе «оба»")

    def test_plasma_only_removes_hyprland(self):
        plan = profile_tool.packages_to_remove(self.groups, profile_tool.kept_groups("plasma", [], True))
        self.assertIn("hyprland", plan)
        self.assertIn("hyprland", plan["hyprland"])
        self.assertNotIn("plasma", plan)

    def test_hyprland_only_removes_plasma(self):
        plan = profile_tool.packages_to_remove(self.groups, profile_tool.kept_groups("hyprland", [], True))
        self.assertIn("plasma-meta", plan["plasma"])
        self.assertNotIn("hyprland", plan)

    def test_extras_are_removed_when_not_selected(self):
        kept = profile_tool.kept_groups("both", ["gaming"], True)
        plan = profile_tool.packages_to_remove(self.groups, kept)
        self.assertNotIn("gaming", plan)
        for group in ("dev", "media", "office"):
            self.assertIn(group, plan)

    def test_dolphin_survives_hyprland_only(self):
        """Dolphin тянется Plasma — но он же файловый менеджер KDE-приложений."""
        plan = profile_tool.packages_to_remove(self.groups, profile_tool.kept_groups("hyprland", [], True))
        self.assertIn("dolphin", plan["plasma"])


class GenPackagesTest(unittest.TestCase):
    def test_all_groups_parse(self):
        groups = gen_packages.load_groups(REPO / "groups")
        self.assertTrue(groups)
        for name, _path, packages in groups:
            self.assertTrue(packages, f"пустая группа: {name}")
            self.assertNotIn("-", name, f"в имени группы не должно быть дефисов: {name}")

    def test_render_is_deterministic(self):
        groups = gen_packages.load_groups(REPO / "groups")
        self.assertEqual(gen_packages.render(groups, "x"), gen_packages.render(groups, "x"))

    def test_render_contains_every_package(self):
        groups = gen_packages.load_groups(REPO / "groups")
        text = gen_packages.render(groups, "packages.x86_64")
        for _name, _path, packages in groups:
            for pkg in packages:
                self.assertIn(f"\n{pkg}\n", text + "\n")

    def test_bad_package_name_rejected(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "10-bad.txt"
            bad.write_text("good-pkg\nBAD_PKG 1.0\n", encoding="utf-8")
            with self.assertRaises(gen_packages.PackageError):
                gen_packages.parse_group(bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
