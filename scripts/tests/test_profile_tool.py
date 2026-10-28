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
theme_tool = load_module("flyarchos_theme_tool",
                         REPO / "profile" / "airootfs" / "usr" / "lib" / "flyarchos" / "theme_tool.py")
backup_tool = load_module("flyarchos_backup_tool",
                          REPO / "profile" / "airootfs" / "usr" / "lib" / "flyarchos" / "backup_tool.py")


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


class ProfilesTest(unittest.TestCase):
    def all_packages(self) -> set[str]:
        groups = gen_packages.load_groups(REPO / "groups")
        return {pkg for _n, _p, pkgs in groups for pkg in pkgs}

    def test_profiles_exist(self):
        self.assertEqual(set(gen_packages.PROFILES), {"full", "slim", "mini"})

    def test_slim_groups_are_real(self):
        known = {name for name, _p, _pkgs in gen_packages.load_groups(REPO / "groups")}
        for name in gen_packages.SLIM_GROUPS:
            self.assertIn(name, known)

    def test_mini_exclude_names_are_real_packages(self):
        unknown = set(gen_packages.MINI_EXCLUDE) - self.all_packages()
        self.assertEqual(unknown, set(), f"MINI_EXCLUDE содержит несуществующие пакеты: {unknown}")

    def test_mini_keeps_essentials(self):
        # mini-образ обязан оставаться полноценной системой с обоими DE
        essentials = {"linux", "hyprland", "plasma-desktop", "kwin", "sddm", "firefox",
                      "networkmanager", "grub", "snapper", "kitty", "dolphin"}
        self.assertFalse(essentials & set(gen_packages.MINI_EXCLUDE))
        self.assertTrue(essentials <= self.all_packages())

    def test_mini_render_header(self):
        groups = gen_packages.load_groups(REPO / "groups")
        text = gen_packages.render(groups, "x", gen_packages.SLIM_GROUPS, "mini", 33)
        self.assertIn("# Профиль: mini", text)


class ThemePresetsTest(unittest.TestCase):
    def test_presets_reference_real_wallpapers(self):
        import json

        manifest = json.loads((REPO / "profile" / "airootfs" / "usr" / "share"
                               / "flyarchos" / "wallpapers.json").read_text(encoding="utf-8"))
        ids = [entry["id"].lower() for entry in manifest["wallpapers"]]
        for name, (wallpaper, accent, accent2, _label) in theme_tool.PRESETS.items():
            self.assertTrue(any(wallpaper.lower() in i for i in ids),
                            f"пресет {name}: нет обоев {wallpaper}")
            self.assertEqual(len(theme_tool.hex_to_rgb(accent)), 3)
            self.assertEqual(len(theme_tool.hex_to_rgb(accent2)), 3)


class BackupToolTest(unittest.TestCase):
    """Резервное копирование без rsync (запасной копировщик) на временном доме."""

    def _make_home(self, tmp: str) -> Path:
        home = Path(tmp) / "home"
        (home / "docs").mkdir(parents=True)
        (home / "docs" / "a.txt").write_text("hello", encoding="utf-8")
        (home / ".cache" / "junk").mkdir(parents=True)
        (home / ".cache" / "junk" / "x.bin").write_text("x" * 64, encoding="utf-8")
        return home

    def test_create_excludes_cache_and_dest_itself(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            home = self._make_home(tmp)
            dest = home / "FlyArchOs-Backups"  # внутри дома — не должно быть рекурсии
            snap = backup_tool.create_snapshot(home, dest, keep=5, rsync_path="")
            self.assertEqual((snap / "docs" / "a.txt").read_text(encoding="utf-8"), "hello")
            self.assertFalse((snap / ".cache").exists())
            self.assertFalse((snap / "FlyArchOs-Backups").exists())
            self.assertTrue((dest / "latest").is_symlink())

    def test_prune_and_restore(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            home = self._make_home(tmp)
            dest = Path(tmp) / "ext"
            backup_tool.create_snapshot(home, dest, keep=5, rsync_path="")
            (home / "docs" / "a.txt").write_text("changed", encoding="utf-8")
            last = backup_tool.create_snapshot(home, dest, keep=1, rsync_path="")
            self.assertEqual(backup_tool.list_snapshots(dest), [last])

            target = Path(tmp) / "home2"
            target.mkdir()
            backup_tool.restore_snapshot(dest, last, target, rsync_path="")
            self.assertEqual((target / "docs" / "a.txt").read_text(encoding="utf-8"), "changed")
            self.assertFalse((target / backup_tool.MANIFEST).exists())


class BackupAutoTest(unittest.TestCase):
    """Автобэкап: имена юнитов совпадают с файлами в образе, мусорный режим — код 2."""

    def test_units_match_shipped_files(self):
        service, timer = backup_tool.auto_units()
        base = REPO / "profile" / "airootfs" / "usr" / "lib" / "systemd" / "user"
        self.assertTrue((base / service).is_file(), service)
        self.assertTrue((base / timer).is_file(), timer)

    def test_auto_bogus_mode_returns_2(self):
        self.assertEqual(backup_tool.cmd_auto("bogus"), 2)


class VersionTest(unittest.TestCase):
    """Бета-версия одинаковая в profiledef, os-release, файле версии и брендинге."""

    def test_version_consistency(self):
        import re

        profiledef = (REPO / "profile" / "profiledef.sh").read_text(encoding="utf-8")
        m = re.search(r'iso_version="([^"]+)"', profiledef)
        self.assertIsNotNone(m)
        ver = m.group(1)
        # Стабильная линия — 1.0.0; в дереве разработки держим только беты.
        self.assertTrue(ver.endswith("-beta"), ver)
        osrel = (REPO / "profile" / "airootfs" / "usr" / "share" / "flyarchos" / "os-release").read_text(
            encoding="utf-8")
        self.assertIn(f"VERSION_ID={ver}", osrel)
        self.assertIn(f'PRETTY_NAME="FlyArchOs {ver}"', osrel)
        version = (REPO / "profile" / "airootfs" / "usr" / "share" / "flyarchos" / "version").read_text(
            encoding="utf-8").strip()
        self.assertEqual(version, ver)
        branding = (REPO / "profile" / "airootfs" / "etc" / "calamares" / "branding"
                    / "flyarchos" / "branding.desc").read_text(encoding="utf-8")
        self.assertIn(f'"{ver}"', branding)
        setup = (REPO / "profile" / "airootfs" / "usr" / "lib" / "flyarchos"
                 / "live-setup.sh").read_text(encoding="utf-8")
        self.assertIn("install -Dm644 /usr/share/flyarchos/os-release /usr/lib/os-release", setup)


class InstallerFinalizeTest(unittest.TestCase):
    """Финализатор включает файрвол только при наборе «Приватность»."""

    def test_firewall_block(self):
        fin = (REPO / "profile" / "airootfs" / "usr" / "lib" / "flyarchos"
               / "install-finalize.sh").read_text(encoding="utf-8")
        self.assertIn("*privacy*)", fin)
        self.assertIn("systemctl enable ufw.service", fin)
        self.assertIn('DEFAULT_INPUT_POLICY="DROP"', fin)


class DoctorSecurityTest(unittest.TestCase):
    """У доктора есть раздел безопасности, и он вызывается из main."""

    def test_security_check_wired(self):
        doc = (REPO / "profile" / "airootfs" / "usr" / "lib" / "flyarchos"
               / "doctor_tool.py").read_text(encoding="utf-8")
        self.assertIn("def check_security()", doc)
        self.assertGreaterEqual(doc.count("check_security()"), 2)


class WineToolTest(unittest.TestCase):
    """flyarchos-exe: интеграция .exe в систему и аккуратные коды возврата."""

    def _run_tool(self, *args):
        import subprocess

        exe = REPO / "profile" / "airootfs" / "usr" / "lib" / "flyarchos" / "flyarchos-exe"
        return subprocess.run(["bash", str(exe), *args],
                              capture_output=True, text=True, timeout=30)

    def test_bogus_action_returns_2(self):
        self.assertEqual(self._run_tool("bogus").returncode, 2)

    def test_missing_file_returns_1(self):
        self.assertEqual(self._run_tool("run", "/definitely/not/here.exe").returncode, 1)

    def test_desktop_and_mimeapps(self):
        desk = (REPO / "profile" / "airootfs" / "usr" / "share" / "applications"
                / "flyarchos-exe.desktop").read_text(encoding="utf-8")
        self.assertIn("application/x-ms-dos-executable", desk)
        self.assertIn("Exec=flyarchos-exe run %f", desk)
        mime = (REPO / "profile" / "airootfs" / "etc" / "xdg"
                / "mimeapps.list").read_text(encoding="utf-8")
        self.assertIn("application/x-ms-dos-executable=flyarchos-exe.desktop", mime)


class PresetTest(unittest.TestCase):
    """Пресеты установщика: слияние наборов и синхронность с конфигом Calamares."""

    def test_merge_extras(self):
        self.assertEqual(profile_tool.merge_extras("custom", ["dev"]), ["dev"])
        self.assertEqual(profile_tool.merge_extras("gaming", []), ["gaming", "media"])
        self.assertEqual(profile_tool.merge_extras("gaming", ["dev"]),
                         ["dev", "gaming", "media"])
        self.assertEqual(profile_tool.merge_extras("workstation", ["gaming"]),
                         ["dev", "gaming", "media", "office"])
        self.assertEqual(profile_tool.merge_extras("full", []),
                         list(profile_tool.EXTRA_GROUPS))
        self.assertEqual(profile_tool.merge_extras("", []), [])

    def test_unknown_preset_rejected(self):
        with self.assertRaises(profile_tool.ProfileError):
            profile_tool.normalize_preset("bogus")

    def test_all_extra_groups_registered(self):
        # Регрессия 1.2.0–1.5.0: группа privacy существовала в установщике,
        # но не в EXTRA_GROUPS — её выбор ронял применение профиля.
        for name in ("dev", "gaming", "media", "office", "privacy"):
            self.assertIn(name, profile_tool.EXTRA_GROUPS)
            self.assertEqual(profile_tool.normalize_extras(name), [name])
            self.assertIn(name, profile_tool.GROUP_TITLES)
            self.assertIn(name, profile_tool.REMOVAL_ORDER)

    def test_preset_conf_ids_match_presets(self):
        import re

        conf = (REPO / "profile" / "airootfs" / "etc" / "calamares" / "modules"
                / "packagechooser_preset.conf").read_text(encoding="utf-8")
        ids = set(re.findall(r'^\s*- id: "(\w+)"', conf, re.M))
        self.assertEqual(ids, set(profile_tool.PRESETS))


class WineBottleTest(unittest.TestCase):
    """Бутылки Wine: валидация имён и список без установленного Wine."""

    def _run_tool(self, home, *args):
        import os
        import subprocess

        exe = REPO / "profile" / "airootfs" / "usr" / "lib" / "flyarchos" / "flyarchos-exe"
        env = dict(os.environ, HOME=str(home))
        return subprocess.run(["bash", str(exe), *args],
                              capture_output=True, text=True, timeout=30, env=env)

    def test_bottle_list_default(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            res = self._run_tool(tmp, "bottle", "list")
            self.assertEqual(res.returncode, 0)
            self.assertIn("default", res.stdout)

    def test_bad_bottle_names_rejected(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._run_tool(tmp, "--bottle", "../evil", "status").returncode, 2)
            self.assertEqual(self._run_tool(tmp, "bottle", "create", "bad/name").returncode, 2)
            self.assertEqual(self._run_tool(tmp, "bottle", "create", "default").returncode, 2)
            self.assertEqual(self._run_tool(tmp, "bottle", "remove", "default").returncode, 2)
            self.assertEqual(self._run_tool(tmp, "bottle", "remove", "ghost").returncode, 1)


class LiveSessionTest(unittest.TestCase):
    """Live-сессия без customize_airootfs.sh (archiso 91+ его не выполняет).

    Пользователь, пароли, sudo и службы заданы статичными файлами
    оверлея; сборочные действия выполняет pacman-хук live-setup.
    """

    AI = REPO / "profile" / "airootfs"

    def test_no_customize_script(self):
        self.assertFalse((REPO / "profile" / "customize_airootfs.sh").exists())

    def test_live_user_static(self):
        passwd = (self.AI / "etc" / "passwd").read_text(encoding="utf-8")
        self.assertIn("root:x:0:0:", passwd)
        self.assertIn("fly:x:1000:1000:", passwd)
        shadow = (self.AI / "etc" / "shadow").read_text(encoding="utf-8")
        for user in ("root", "fly"):
            line = [ln for ln in shadow.splitlines()
                    if ln.startswith(user + ":")][0]
            self.assertTrue(line.split(":")[1].startswith("$"), user)
        sysusers = (self.AI / "usr" / "lib" / "sysusers.d"
                    / "flyarchos-live.conf").read_text(encoding="utf-8")
        self.assertIn("m fly wheel", sysusers)

    def test_live_hook_and_sudo(self):
        hook = (self.AI / "etc" / "pacman.d" / "hooks"
                / "flyarchos-live-setup.hook").read_text(encoding="utf-8")
        self.assertIn("live-setup.sh", hook)
        sudoers = (self.AI / "etc" / "sudoers.d"
                   / "10-flyarchos-live").read_text(encoding="utf-8")
        self.assertIn("NOPASSWD", sudoers)
        prepare = (self.AI / "usr" / "lib" / "flyarchos"
                   / "install-prepare.sh").read_text(encoding="utf-8")
        self.assertIn("rm -f /etc/sudoers.d/10-flyarchos-live", prepare)
        self.assertIn("flyarchos-live-setup.hook", prepare)
        self.assertIn("flyarchos-live.conf", prepare)

    def test_services_enabled_by_symlinks(self):
        system = self.AI / "etc" / "systemd" / "system"
        dm = system / "display-manager.service"
        self.assertTrue(dm.is_symlink())
        self.assertEqual(str(dm.readlink()),
                         "/usr/lib/systemd/system/sddm.service")
        self.assertTrue((system / "multi-user.target.wants"
                         / "NetworkManager.service").is_symlink())

    def test_build_iso_home_and_mini_noextract(self):
        build = (REPO / "scripts" / "build-iso.sh").read_text(encoding="utf-8")
        self.assertIn("airootfs/home/fly", build)
        self.assertIn("NoExtract", build)


class LiveBootTest(unittest.TestCase):
    """Live-загрузка: без archiso-хуков ISO падает на Switch Root (баг до 1.7.0)."""

    def test_archiso_hooks_present(self):
        conf = (REPO / "profile" / "airootfs" / "etc" / "mkinitcpio.conf.d"
                / "archiso.conf").read_text(encoding="utf-8")
        self.assertIn("HOOKS=(", conf)
        for hook in ("archiso", "archiso_loop_mnt", "udev"):
            self.assertIn(hook, conf)

    def test_initramfs_size_contract(self):
        # mini должен влезать в один файл <2 ГиБ: initramfs сжат xz,
        # а UEFI грузится через GRUB (одна копия initramfs, а не две).
        conf = (REPO / "profile" / "airootfs" / "etc" / "mkinitcpio.conf.d"
                / "archiso.conf").read_text(encoding="utf-8")
        self.assertIn('COMPRESSION="xz"', conf)
        profiledef = (REPO / "profile" / "profiledef.sh").read_text(encoding="utf-8")
        self.assertIn("'uefi.grub'", profiledef)
        self.assertNotIn("uefi.systemd-boot", profiledef)

    def test_live_group_has_mkinitcpio_archiso(self):
        live = (REPO / "groups" / "99-live.txt").read_text(encoding="utf-8")
        self.assertIn("mkinitcpio-archiso", live)

    def test_prepare_removes_live_hooks(self):
        prep = (REPO / "profile" / "airootfs" / "usr" / "lib" / "flyarchos"
                / "install-prepare.sh").read_text(encoding="utf-8")
        self.assertIn("rm -f /etc/mkinitcpio.conf.d/archiso.conf", prep)

    def test_initcpiocfg_has_no_btrfs_hook(self):
        conf = (REPO / "profile" / "airootfs" / "etc" / "calamares" / "modules"
                / "initcpiocfg.conf").read_text(encoding="utf-8")
        self.assertNotIn("[ btrfs ]", conf)


if __name__ == "__main__":
    unittest.main(verbosity=2)
