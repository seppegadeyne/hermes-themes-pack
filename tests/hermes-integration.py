"""Real Hermes: plugin install, /theme + `hermes theme`, native skin loader. Isolated homes.
Run with the Hermes checkout's Python and set HERMES_REPO.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

repo = Path(os.environ["HERMES_REPO"]).resolve()
package = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="themes-pack-") as tmp:
    home = Path(tmp) / "home"
    home.mkdir()
    env = {**os.environ, "HERMES_HOME": str(home), "HERMES_ENABLE_PROJECT_PLUGINS": "false",
           "XDG_CONFIG_HOME": str(Path(tmp) / "config")}

    def cli(*args, capture=False):
        result = subprocess.run([sys.executable, "-m", "hermes_cli.main", *args], cwd=repo, env=env,
                                check=True, capture_output=capture, text=True)
        return result.stdout.strip() if capture else None

    def py(code):
        subprocess.run([sys.executable, "-c", code], cwd=repo, env=env, check=True)

    cli("config", "set", "plugins.isolation", "in_process")
    cli("plugins", "install", package.as_uri(), "--no-deps")
    cli("plugins", "enable", "hermes-themes-pack")
    assert not (home / "skins").exists(), "plugin install must not copy skins"

    # Slash command through the real plugin manager (as CLI/TUI/Desktop dispatch it).
    py("""
from hermes_cli.plugins import get_plugin_commands
cmd = get_plugin_commands()['theme']
assert cmd['plugin'] == 'hermes-themes-pack', cmd
out = cmd['handler']('nord')
assert 'Nord' in out, out
print('PASS: /theme registered and dispatched:', out)
""")
    assert cli("config", "get", "display.skin", capture=True) == "nord"
    cli("theme", "Tokyo Night")
    assert cli("config", "get", "display.skin", capture=True) == "tokyo-night"
    py("""
from hermes_cli.skin_engine import load_skin, list_skins
s = load_skin('tokyo-night')
assert s.colors['background'] == '#1A1B26' and s.banner_logo and s.banner_hero
for name in ('nord', 'catppuccin-latte', 'jade-horse'):
    s = load_skin(name)
    assert s.name == name and s.colors['background'].startswith('#') and s.banner_logo, name
assert {'nord', 'tokyo-night'} <= {x['name'] for x in list_skins()}
print('PASS: real skin loader')
""")
    cli("theme", "follow", "on")
    hook = Path(tmp) / "config/omarchy/hooks/theme-set.d/50-hermes-themes-pack"
    assert hook.exists()
    cli("theme", "omarchy", "jade-horse")
    assert cli("config", "get", "display.skin", capture=True) == "jade-horse"
    cli("theme", "follow", "off")
    assert not hook.exists()
    cli("config", "set", "display.skin", "default")
    cli("theme", "uninstall")
    assert not list((home / "skins").glob("*.yaml"))
    cli("plugins", "remove", "hermes-themes-pack")
    assert not (home / "plugins/hermes-themes-pack").exists()
print("PASS: install, /theme, hermes theme, Omarchy follow, uninstall in an isolated home")
