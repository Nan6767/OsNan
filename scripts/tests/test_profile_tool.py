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
import os
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

    def test_sddm_survives_every_desktop_choice(self):
        # SDDM — единственный менеджер входа для обеих сессий. Когда он
        # жил в группе plasma, установка «только Hyprland» удаляла его
        # вместе с Plasma и система оставалась без графического входа.
        self.assertIn("sddm", self.groups["common"])
        self.assertNotIn("sddm", self.groups["plasma"])
        for desktop in ("hyprland", "plasma", "both"):
            plan = profile_tool.packages_to_remove(
                self.groups, profile_tool.kept_groups(desktop, [], True))
            removed = set(sum(plan.values(), []))
            self.assertNotIn("sddm", removed, f"sddm удаляется при выборе {desktop}")

    def test_live_only_installer_package_is_explicit(self):
        # Calamares приходит из AUR (packages.aux) и в нумерованные
        # группы не входит, поэтому profile_tool удаляет его явно.
        self.assertIn("calamares", profile_tool.LIVE_ONLY_PACKAGES)

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


class ThemeLuaTest(unittest.TestCase):
    def test_theme_writes_lua_not_legacy_conf(self):
        # Hyprland 0.57+ не читает .conf: тема обязана быть Lua.
        self.assertEqual(theme_tool.HYPR_THEME.name, "theme.lua")
        source = Path(theme_tool.__file__).read_text(encoding="utf-8")
        self.assertIn("hl.config", source)
        self.assertNotIn("col.active_border   =", source)


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


class AuditRegressionTest(unittest.TestCase):
    """Регрессии из аудита образов №40/41: права на исполнение утилит,
    пароль root и ядра на целевой системе, связка ключей pacman,
    демон обоев awww вместо переименованного swww."""

    AI = REPO / "profile" / "airootfs"

    def test_all_tools_executable_in_image(self):
        import re

        profiledef = (REPO / "profile" / "profiledef.sh").read_text(encoding="utf-8")
        perms = dict(re.findall(r'\["([^"]+)"\]="([^"]+)"', profiledef))
        tools = self.AI / "usr" / "lib" / "flyarchos"
        for f in sorted(tools.iterdir()):
            if f.is_file() and f.read_bytes()[:2] == b"#!":
                entry = perms.get(f"/usr/lib/flyarchos/{f.name}", "")
                self.assertTrue(entry.endswith(":755"),
                                f"{f.name}: нет 755 в file_permissions")

    def test_initcpio_all_kernels(self):
        conf = (self.AI / "etc" / "calamares" / "modules"
                / "initcpio.conf").read_text(encoding="utf-8")
        # иначе в полном образе не соберётся initramfs для linux-lts
        self.assertIn("kernel: all", conf)
        prep = (self.AI / "usr" / "lib" / "flyarchos"
                / "install-prepare.sh").read_text(encoding="utf-8")
        # а пресет для отсутствующего ядра уронит mkinitcpio -P
        self.assertIn("пресет пропущен", prep)

    def test_no_snapper_timers_without_config(self):
        # таймеры включает flyarchos-snapshot setup после создания конфига
        svc = (self.AI / "etc" / "calamares" / "modules"
               / "services-systemd.conf").read_text(encoding="utf-8")
        self.assertNotIn("snapper-timeline", svc)
        prep = (self.AI / "usr" / "lib" / "flyarchos"
                / "install-prepare.sh").read_text(encoding="utf-8")
        self.assertNotIn("snapper-timeline", prep)

    def test_installer_actually_present(self):
        # AUR-PKGBUILD пропускает packagechooser: build-aur обязан снять
        # пропуск, а CI — проверить бинарь и модуль в готовом образе,
        # иначе Calamares не стартует из-за отсутствующего модуля.
        build_aur = (REPO / "scripts" / "build-aur.sh").read_text(encoding="utf-8")
        self.assertIn('"$pkg" = "calamares"', build_aur)
        self.assertIn("packagechooser", build_aur)
        ci = (REPO / "scripts" / "ci-build.sh").read_text(encoding="utf-8")
        self.assertIn("/usr/bin/calamares", ci)
        self.assertIn("modules/packagechooser", ci)
        # и вообще каждый модуль последовательности + GS-инвариант
        self.assertIn("module.desc", ci)
        self.assertIn("shown_choosers", ci)
        # unsquashfs -l <путь> возвращает 0 и без файла — существование
        # проверяется по выводу (sfs_has), иначе проверки врут в обе стороны
        self.assertIn("sfs_has()", ci)
        self.assertIn("grep -aF", ci)

    def test_profile_cli_dry_run(self):
        """Реальный вызов CLI, как в shellprocess@profile (без --apply).

        Регрессия: основной парсер создаёт remove_live, а cmd_apply читал
        args.keep_live — установщик падал с AttributeError на любом образе.
        """
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(PROFILE_TOOL), "--groups-dir", str(REPO / "groups"),
             "--desktop=hyprland", "--preset=custom", "--extras=", "--remove-live"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        self.assertNotIn("AttributeError", proc.stderr)
        # установщик из AUR удаляется явно, а не через нумерованные группы
        self.assertIn("calamares", proc.stderr)

    def test_slim_mini_profile_command_rewrite(self):
        # В slim/mini страниц preset/extras нет — GS-ключей не будет, и
        # build-iso обязан убрать их из команды shellprocess@profile.
        build = (REPO / "scripts" / "build-iso.sh").read_text(encoding="utf-8")
        self.assertIn("shellprocess_profile.conf", build)
        self.assertIn("--preset=custom --extras=", build)
        self.assertIn("assert key not in text", build)

    def test_aux_packages_merged_into_mkarchiso_list(self):
        # mkarchiso читает только packages.x86_64; packages.aux игнорируется.
        # Регрессия №55: Calamares собирался, но в образ не устанавливался.
        build = (REPO / "scripts" / "build-iso.sh").read_text(encoding="utf-8")
        self.assertIn('cat "$WORK/profile/packages.aux"', build)
        self.assertIn('>> "$WORK/profile/packages.x86_64"', build)

    def test_target_pacman_config_and_mirrors(self):
        conf = (self.AI / "etc" / "pacman.conf").read_text(encoding="utf-8")
        self.assertIn("[multilib]", conf)
        for line in conf.splitlines():
            stripped = line.strip()
            self.assertFalse(stripped.startswith("Server") and "file://" in stripped, line)
            self.assertFalse(stripped.startswith("NoExtract"), line)
            self.assertNotEqual(stripped, "[flyarchos]")
        mirrors = (self.AI / "etc" / "pacman.d" / "mirrorlist").read_text(encoding="utf-8")
        self.assertRegex(mirrors, r"(?m)^Server = https://")
        template = (REPO / "profile" / "pacman.conf.in").read_text(encoding="utf-8")
        self.assertEqual(template.count("@FLYARCHOS_REPO@"), 1)

    def test_luks1_for_grub(self):
        conf = (self.AI / "etc" / "calamares" / "modules"
                / "partition.conf").read_text(encoding="utf-8")
        self.assertIn("luksGeneration: luks1", conf)
        self.assertNotIn("luksGeneration: luks2", conf)

    def test_finalize_checks_real_bootloader_and_sddm_theme(self):
        fin = (self.AI / "usr" / "lib" / "flyarchos"
               / "install-finalize.sh").read_text(encoding="utf-8")
        # загрузчик: артефакты на ESP и повтор bootctl, а не один grub.cfg
        self.assertIn("systemd_boot_entries_ok", fin)
        self.assertIn("bootctl --path", fin)
        self.assertIn("lsblk -dn -o PKNAME", fin)  # диск BIOS через родителей
        # тема SDDM выбирается из фактически оставшихся после профиля
        self.assertIn("elarun", fin)
        self.assertIn("zz-flyarchos-finalize.conf", fin)
        # страховочное удаление установщика из целевой системы
        self.assertIn("pacman -Rns", fin)
        self.assertIn("flyarchos-install.desktop", fin)

    def test_prepare_target_safety(self):
        prep = (self.AI / "usr" / "lib" / "flyarchos"
                / "install-prepare.sh").read_text(encoding="utf-8")
        # root не наследует известный live-пароль flyarchos
        self.assertIn("usermod -p '!' root", prep)
        # ядра восстанавливаются в /boot из /usr/lib/modules
        self.assertIn("/usr/lib/modules", prep)
        self.assertIn("vmlinuz-linux", prep)
        # у установленной системы своя связка ключей pacman
        self.assertIn("pacman-key --init", prep)
        self.assertIn("pacman-key --populate", prep)

    def test_pacman_init_live(self):
        unit = self.AI / "etc" / "systemd" / "system" / "pacman-init.service"
        self.assertTrue(unit.is_file())
        self.assertIn("pacman-key --init", unit.read_text(encoding="utf-8"))
        wants = (self.AI / "etc" / "systemd" / "system"
                 / "multi-user.target.wants" / "pacman-init.service")
        self.assertTrue(wants.is_symlink())
        setup = (self.AI / "usr" / "lib" / "flyarchos"
                 / "live-setup.sh").read_text(encoding="utf-8")
        self.assertIn("rm -rf /etc/pacman.d/gnupg", setup)

    def test_wallpaper_daemon_is_awww(self):
        conf = (self.AI / "etc" / "skel" / ".config" / "hypr"
                / "hyprland.lua").read_text(encoding="utf-8")
        self.assertIn("awww-daemon", conf)
        self.assertNotIn("swww", conf)
        groups = "\n".join(p.read_text(encoding="utf-8")
                            for p in (REPO / "groups").glob("*.txt"))
        self.assertRegex(groups, r"(?m)^awww$")
        self.assertNotRegex(groups, r"(?m)^swww$")

    def test_hyprland_config_is_lua(self):
        # Hyprland 0.57 убрал поддержку .conf: с legacy-конфигом сессия
        # стартует без автозапуска, панели, обоев и наших биндов.
        hypr = self.AI / "etc" / "skel" / ".config" / "hypr"
        lua = (hypr / "hyprland.lua").read_text(encoding="utf-8")
        self.assertFalse((hypr / "hyprland.conf").exists())
        self.assertFalse((hypr / "theme.conf").exists())
        theme = (hypr / "theme.lua").read_text(encoding="utf-8")
        self.assertIn("hl.config", theme)
        for needle in ('hl.on("hyprland.start"', "hl.bind", "hl.monitor",
                       'require("theme")', "wpctl set-volume",
                       "flyarchos-welcome --autostart", "waybar"):
            self.assertIn(needle, lua)
        for legacy in ("exec-once", "windowrulev2", "source =", "pamixer -"):
            self.assertNotIn(legacy, lua)
        idle = (hypr / "hypridle.conf").read_text(encoding="utf-8")
        self.assertIn("hl.dsp.dpms", idle)
        self.assertNotIn("dispatch dpms on", idle)

    def test_vm_performance_mode(self):
        lua = (self.AI / "etc" / "skel" / ".config" / "hypr"
               / "hyprland.lua").read_text(encoding="utf-8")
        for needle in (
            "/sys/class/dmi/id/product_name",
            "detect_performance_mode",
            "flyarchos/performance-mode",
            "blur = {\n            enabled = visual_effects",
            "shadow = {\n            enabled = visual_effects",
            "animations = {\n        enabled = visual_effects",
            "new_render_scheduling = performance_mode",
            'mainMod .. " + F1"',
            "flyarchos-performance toggle",
            "--transition-type \" .. wallpaper_transition",
            "seq 1 50",
        ):
            self.assertIn(needle, lua)

        tool = self.AI / "usr" / "lib" / "flyarchos" / "flyarchos-performance"
        self.assertTrue(tool.is_file())
        self.assertTrue(tool.stat().st_mode & 0o111)
        link = self.AI / "usr" / "bin" / "flyarchos-performance"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), "../lib/flyarchos/flyarchos-performance")

        script = tool.read_text(encoding="utf-8")
        for needle in (
            "systemd-detect-virt --vm",
            "AnimationDurationFactor",
            "blurEnabled",
            "magiclampEnabled",
            "plasma-performance",
            "apply-plasma",
        ):
            self.assertIn(needle, script)

        autostart = (self.AI / "etc" / "xdg" / "autostart"
                     / "flyarchos-performance.desktop").read_text(encoding="utf-8")
        self.assertIn("Exec=/usr/bin/flyarchos-performance apply-plasma", autostart)
        self.assertIn("OnlyShowIn=KDE;", autostart)

    def test_virtualbox_guest_integration_packaged(self):
        groups = (REPO / "groups" / "00-core.txt").read_text(encoding="utf-8")
        self.assertRegex(groups, r"(?m)^virtualbox-guest-utils$")

        wants = (self.AI / "etc" / "systemd" / "system"
                 / "multi-user.target.wants" / "vboxservice.service")
        self.assertTrue(wants.is_symlink())
        self.assertEqual(os.readlink(wants),
                         "/usr/lib/systemd/system/vboxservice.service")

        sysusers = (self.AI / "usr" / "lib" / "sysusers.d"
                    / "flyarchos-live.conf").read_text(encoding="utf-8")
        self.assertIn("m fly vboxsf", sysusers)

        users = (self.AI / "etc" / "calamares" / "modules"
                 / "users.conf").read_text(encoding="utf-8")
        self.assertIn("name: vboxsf", users)

        services = (self.AI / "etc" / "calamares" / "modules"
                    / "services-systemd.conf").read_text(encoding="utf-8")
        self.assertIn('"vboxservice.service"', services)


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
        setup = (self.AI / "usr" / "lib" / "flyarchos"
                 / "live-setup.sh").read_text(encoding="utf-8")
        self.assertIn("localedef", setup)  # locale.gen бывает пустым
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
