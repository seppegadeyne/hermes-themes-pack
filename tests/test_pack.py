"""Unit tests: generated assets, installer receipts, matching, Omarchy hook. Stdlib only."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("installer", ROOT / "installer.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
bspec = importlib.util.spec_from_file_location("build", ROOT / "tools" / "build.py")
build = importlib.util.module_from_spec(bspec)
bspec.loader.exec_module(build)

# Desktop built-in theme names a skin must not reuse (it would never paint there).
DESKTOP_BUILTINS = {"nous", "github", "catppuccin", "everforest", "solarized", "nous-alt",
                    "classic", "midnight", "ember", "mono", "slate", "cyberpunk", "default", "omarchy"}


class AssetTests(unittest.TestCase):
    def test_generated_skins_are_current(self):
        before = {p.name: p.read_bytes() for p in (ROOT / "skins").iterdir()}
        build.build()
        after = {p.name: p.read_bytes() for p in (ROOT / "skins").iterdir()}
        self.assertEqual(before, after, "run python3 tools/build.py and commit skins/")

    def test_catalog_matches_theme_dirs(self):
        slugs = sorted(p.name for p in (ROOT / "themes").iterdir() if p.is_dir())
        entries = m.catalog()
        self.assertEqual(sorted(e["slug"] for e in entries), slugs)
        self.assertGreaterEqual(len(entries), 20)
        for e in entries:
            self.assertNotIn(e["skin"], DESKTOP_BUILTINS)
            self.assertRegex(e["skin"], r"^[a-z0-9-]+$")
            self.assertIn(e["mode"], ("dark", "light"))

    def test_every_skin_has_hex_palette_and_banner_art(self):
        for e in m.catalog():
            text = (ROOT / "skins" / f"{e['skin']}.yaml").read_text(encoding="utf-8")
            self.assertTrue(text.startswith(f"name: {e['skin']}\n"), e["skin"])
            colors = re.findall(r"^  (\w+): '([^']*)'$", text, re.M)
            self.assertGreaterEqual(len(colors), 30, e["skin"])
            for key, value in colors:
                self.assertRegex(value, r"^#[0-9A-Fa-f]{6}$", f"{e['skin']}.{key}")
            self.assertIn("  background: '#", text)
            for art in ("banner_logo:", "banner_hero:"):
                self.assertIn(f"\n{art}", text, f"{e['skin']} lacks {art}")
            for flavor in ("branding:", "spinner:", "tool_prefix:"):
                self.assertNotIn(f"\n{flavor}", text, f"{e['skin']} ships personal {flavor}")

    def test_catalog_metadata(self):
        manifest = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
        version = re.search(r'^version: "([0-9.]+)"$', manifest, re.M).group(1)
        self.assertRegex(manifest, re.compile(r'^requires_hermes: ">=\d+\.\d+\.\d+"$', re.M))
        self.assertEqual(json.loads((ROOT / "package.json").read_text())["version"], version)
        self.assertIn(f"- {version}:", (ROOT / "README.md").read_text(encoding="utf-8"))
        for image in ["catalog-banner.png", *(f"screenshots/{n}.png" for n in ("tokyo-night", "nord"))]:
            self.assertTrue((ROOT / "docs" / image).is_file(), image)

    def test_no_bytecode_or_binaries_tracked(self):
        try:
            tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                                     check=True, timeout=30).stdout.split()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        self.assertFalse([p for p in tracked if p.endswith((".pyc", ".pyo")) or "__pycache__" in p])

    def test_mix(self):
        self.assertEqual(build.mix("#000000", "#FFFFFF", 0.5), "#808080")


class InstallerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name).resolve()
        self.skins = self.home / "skins"

    def test_install_idempotent_uninstall(self):
        changed, skipped = m.install(self.home)
        self.assertEqual(len(changed), len(m.catalog()))
        self.assertEqual(skipped, [])
        receipt = m.receipt_path(self.home).read_bytes()
        self.assertEqual(m.install(self.home), ([], []))
        self.assertEqual(m.receipt_path(self.home).read_bytes(), receipt)
        removed, kept = m.uninstall(self.home)
        self.assertEqual((len(removed), kept), (len(m.catalog()), []))
        self.assertEqual(list(self.skins.iterdir()), [])
        self.assertFalse(m.receipt_path(self.home).exists())

    def test_personal_skin_skipped_or_backed_up(self):
        self.skins.mkdir()
        (self.skins / "nord.yaml").write_bytes(b"personal\n")
        _, skipped = m.install(self.home)
        self.assertEqual(skipped, ["nord"])
        self.assertEqual((self.skins / "nord.yaml").read_bytes(), b"personal\n")
        m.install(self.home, ["nord"], replace=True)
        self.assertNotEqual((self.skins / "nord.yaml").read_bytes(), b"personal\n")
        m.uninstall(self.home)
        self.assertEqual((self.skins / "nord.yaml").read_bytes(), b"personal\n")

    def test_user_edit_survives_update_and_uninstall(self):
        m.install(self.home, ["nord"])
        (self.skins / "nord.yaml").write_bytes(b"tweaked\n")
        self.assertEqual(m.install(self.home, ["nord"]), ([], ["nord"]))
        self.assertEqual(m.uninstall(self.home), ([], ["nord"]))
        self.assertEqual((self.skins / "nord.yaml").read_bytes(), b"tweaked\n")

    def test_symlink_refused(self):
        self.skins.mkdir()
        (self.skins / "nord.yaml").symlink_to(self.home / "elsewhere")
        with self.assertRaises(m.ThemeError):
            m.install(self.home, ["nord"], replace=True)

    def test_use_installs_and_selects_via_hermes(self):
        with mock.patch.object(m, "select") as select:
            self.assertIn("Tokyo Night", m.use("Tokyo Night", self.home))
            select.assert_called_once_with(self.home, "tokyo-night")
        self.assertEqual(len(list(self.skins.glob("*.yaml"))), len(m.catalog()))
        (self.skins / "nord.yaml").write_text("name: nord\n# tweaked\n")
        with mock.patch.object(m, "select"):
            self.assertIn("your own", m.use("nord", self.home))
        with self.assertRaises(m.ThemeError):
            m.use("does-not-exist", self.home)

    def test_find_aliases(self):
        self.assertEqual(m.find("catppuccin")["skin"], "catppuccin-mocha")
        self.assertEqual(m.find("Catppuccin Latte")["skin"], "catppuccin-latte")
        self.assertEqual(m.find("JADE_HORSE")["skin"], "jade-horse")
        self.assertIsNone(m.find("osaka-jade"))


class OmarchyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        self.home = self.base / "hermes"
        self.home.mkdir()
        patcher = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.base / "config")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_sync_known_and_unknown(self):
        with mock.patch.object(m, "select") as select:
            m.omarchy_sync("jade-horse", self.home)
            select.assert_called_with(self.home, "jade-horse")
            self.assertIn("skin unchanged", m.omarchy_sync("osaka-jade", self.home))
            (self.home / "skins" / "omarchy.yaml").write_text("name: omarchy\n")
            m.omarchy_sync("osaka-jade", self.home)
            select.assert_called_with(self.home, "omarchy")

    def test_follow_on_off_only_removes_own_hook(self):
        hook = m.omarchy_hooks_dir() / m.HOOK_NAME
        m.follow(True)
        self.assertTrue(m.following())
        self.assertTrue(os.access(hook, os.X_OK))
        m.follow(False)
        self.assertFalse(hook.exists())
        hook.write_text("#!/bin/bash\n# mine\n")
        with self.assertRaises(m.ThemeError):
            m.follow(False)
        self.assertTrue(hook.exists())

    def test_hook_script_is_inert_without_installer(self):
        text = (ROOT / "hooks" / "theme-set").read_text()
        self.assertIn('[[ -n ${1:-} ]] || exit 0', text)
        self.assertIn('[[ -f $installer ]] || continue', text)
        self.assertIn("exit 0", text)

    def test_hook_switches_default_and_every_profile_with_the_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, log = Path(tmp) / "hermes", Path(tmp) / "calls"
            for home in (root, root / "profiles" / "a", root / "profiles" / "b"):
                pkg = home / "plugins" / "hermes-themes-pack"
                pkg.mkdir(parents=True)
                (pkg / "installer.py").write_text(
                    f"import sys\nopen({str(log)!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n")
            (root / "profiles" / "without-pack").mkdir()
            env = {**os.environ, "HERMES_HOME": str(root)}
            subprocess.run(["bash", str(ROOT / "hooks" / "theme-set"), "nord"], env=env, check=True)
            calls = sorted(log.read_text().splitlines())
            self.assertEqual(calls, sorted(f"omarchy nord --home {h}" for h in
                                           (root, root / "profiles" / "a", root / "profiles" / "b")))


class DispatchTests(unittest.TestCase):
    def test_usage_and_follow_status(self):
        self.assertIn("/theme <name>", m.dispatch(["help"], tempfile.gettempdir()))
        with mock.patch.object(m, "following", return_value=False):
            self.assertIn("follow is off", m.dispatch(["follow"], tempfile.gettempdir()))

    def test_replace_flag_only_applies_to_install(self):
        import argparse
        parser = argparse.ArgumentParser()
        m.configure_parser(parser)
        seen = []
        with mock.patch.object(m, "dispatch", side_effect=lambda words, home: seen.append(words) or "ok"):
            m.run(parser.parse_args(["nord", "--replace"]))
            m.run(parser.parse_args(["install", "--replace"]))
        self.assertEqual(seen, [["nord"], ["install", "--replace"]])

    def test_timeout_is_reported_not_raised(self):
        import subprocess as sp
        spec2 = importlib.util.spec_from_file_location(
            "themes_pack_pkg", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
        pkg = importlib.util.module_from_spec(spec2)
        import sys
        with mock.patch.dict(sys.modules, {"themes_pack_pkg": pkg}):
            spec2.loader.exec_module(pkg)
        with mock.patch.object(pkg, "dispatch", side_effect=sp.TimeoutExpired("hermes", 60)):
            self.assertTrue(pkg.handle_theme("nord").startswith("Theme:"))

    def test_uninstall_ignores_unknown_receipt_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            m.save_receipt(home, {"skins": {"../config": {"previous": None, "installed_sha256": "x"}}})
            (home / "config.yaml").write_text("keep\n")
            removed, kept = m.uninstall(home)
            self.assertEqual((removed, kept), ([], ["../config"]))
            self.assertTrue((home / "config.yaml").exists())

    def test_follow_on_notes_default_profile(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(m, "follow", return_value="hook installed"), \
             mock.patch.object(m, "omarchy_theme", return_value=None):
            self.assertIn("every profile", m.dispatch(["follow", "on"], tmp))

    def test_listing_marks_current(self):
        with mock.patch.object(m, "current_skin", return_value="nord"), \
             mock.patch.object(m, "omarchy_theme", return_value=None):
            text = m.dispatch([], tempfile.gettempdir())
        self.assertRegex(text, r"● Nord\s+nord\s+dark")
        self.assertEqual(text.count("●"), 1)


if __name__ == "__main__":
    unittest.main()
