"""Theme pack: reversible skin installation, switching and Omarchy follow. Stdlib only.

Usable three ways: the `/theme` slash command and `hermes theme` CLI (via
__init__.py), and standalone (`python3 installer.py ...`) for the Omarchy hook.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PACKAGE = "hermes-themes-pack"
ROOT = Path(__file__).resolve().parent
SKINS = ROOT / "skins"
HOOK_SOURCE = ROOT / "hooks" / "theme-set"
HOOK_NAME = "50-hermes-themes-pack"
FALLBACK_SKIN = "omarchy"  # rendered by Omarchy itself from the current theme


class ThemeError(RuntimeError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".themes-pack-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def catalog():
    return json.loads((SKINS / "index.json").read_text(encoding="utf-8"))


def find(query):
    """Match slug, skin name or label, case- and separator-insensitively."""
    key = query.strip().lower().replace(" ", "-").replace("_", "-")
    for entry in catalog():
        if key in (entry["slug"], entry["skin"], entry["label"].lower().replace(" ", "-")):
            return entry
    return None


def default_home():
    try:
        from hermes_constants import get_hermes_home
    except ImportError:
        return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
    return get_hermes_home()


def resolve_home(home):
    return Path(home if home is not None else default_home()).expanduser().resolve()


def guarded(home, path):
    # Never follow symlinks out of the chosen profile, including directory links.
    if path.is_symlink() or not path.resolve().is_relative_to(home):
        raise ThemeError(f"Refusing symlink or escaped target: {path}")
    return path


def receipt_path(home):
    return guarded(home, home / "theme-packages" / f"{PACKAGE}.json")


def load_receipt(home):
    path = receipt_path(home)
    return json.loads(path.read_text()) if path.exists() else {"skins": {}}


def save_receipt(home, state):
    path = receipt_path(home)
    if state["skins"]:
        atomic_write(path, (json.dumps(state, indent=2, sort_keys=True) + "\n").encode())
    elif path.exists():
        path.unlink()


def install(home=None, names=None, replace=False):
    """Install or update pack skins. Unmanaged or user-edited files are skipped, never clobbered.

    Returns (changed, skipped) lists of skin names.
    """
    home = resolve_home(home)
    state = load_receipt(home)
    wanted = [e["skin"] for e in catalog()] if names is None else names
    changed, skipped = [], []
    for name in wanted:
        data = (SKINS / f"{name}.yaml").read_bytes()
        target = guarded(home, home / "skins" / f"{name}.yaml")
        record = state["skins"].get(name)
        current = target.read_bytes() if target.exists() else None
        if record is not None:
            if current is None or digest(current) != record["installed_sha256"]:
                skipped.append(name)  # edited or removed by the user: theirs now
                continue
        elif current is not None:
            if not replace:
                skipped.append(name)  # personal file with the same name
                continue
            record = {"previous": base64.b64encode(current).decode()}
        else:
            record = {"previous": None}
        if current == data:
            state["skins"][name] = {**record, "installed_sha256": digest(data)}
            continue
        # Receipt first: an interruption fails closed on the next run instead of losing data.
        state["skins"][name] = {**record, "installed_sha256": digest(data)}
        save_receipt(home, state)
        atomic_write(target, data)
        changed.append(name)
    save_receipt(home, state)
    return changed, skipped


def uninstall(home=None):
    home = resolve_home(home)
    state = load_receipt(home)
    removed, kept = [], []
    for name, record in sorted(state["skins"].items()):
        target = guarded(home, home / "skins" / f"{name}.yaml")
        if not target.exists() or digest(target.read_bytes()) != record["installed_sha256"]:
            kept.append(name)
            continue
        if record["previous"] is None:
            target.unlink()
        else:
            atomic_write(target, base64.b64decode(record["previous"], validate=True))
        removed.append(name)
    for name in removed:
        del state["skins"][name]
    save_receipt(home, state)
    return removed, kept


def hermes_command():
    """The Hermes CLI that writes config through its own safe writer."""
    module = sys.modules.get("hermes_cli")
    if module is not None and getattr(module, "__file__", None):
        return [sys.executable, "-m", "hermes_cli.main"], Path(module.__file__).resolve().parents[1]
    found = shutil.which("hermes") or str(Path.home() / ".local" / "bin" / "hermes")
    if not Path(found).exists():
        raise ThemeError("hermes CLI not found on PATH")
    return [found], None


def run_hermes(home, *args):
    command, cwd = hermes_command()
    env = {**os.environ, "HERMES_HOME": str(home)}
    result = subprocess.run([*command, *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise ThemeError((result.stderr or result.stdout).strip().splitlines()[-1] if (result.stderr or result.stdout).strip() else "hermes failed")
    return result.stdout.strip()


def select(home, skin):
    run_hermes(home, "config", "set", "display.skin", skin)


def current_skin(home):
    try:
        return run_hermes(home, "config", "get", "display.skin") or "default"
    except (ThemeError, OSError, subprocess.TimeoutExpired):
        return "?"


def use(query, home=None):
    """Install (if needed) and select one pack theme on every Hermes surface."""
    home = resolve_home(home)
    entry = find(query)
    if entry is None:
        raise ThemeError(f"Unknown theme '{query}'. Try /theme list.")
    install(home, [entry["skin"]])
    if not (home / "skins" / f"{entry['skin']}.yaml").exists():
        raise ThemeError(f"Skin file for {entry['skin']} is missing")
    select(home, entry["skin"])
    return f"Theme: {entry['label']} (skin {entry['skin']})."


# ── Omarchy ────────────────────────────────────────────────────────────────

def omarchy_hooks_dir():
    config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return config / "omarchy" / "hooks" / "theme-set.d"


def omarchy_theme():
    path = Path.home() / ".local" / "state" / "omarchy" / "current" / "theme.name"
    try:
        return path.read_text().strip() or None
    except OSError:
        return None


def omarchy_sync(slug=None, home=None):
    """Select the pack theme matching an Omarchy slug, else Omarchy's own generated skin."""
    home = resolve_home(home)
    slug = slug or omarchy_theme()
    if not slug:
        raise ThemeError("No current Omarchy theme found")
    entry = find(slug)
    if entry is not None:
        return use(entry["skin"], home)
    if (home / "skins" / f"{FALLBACK_SKIN}.yaml").exists():
        select(home, FALLBACK_SKIN)
        return f"Omarchy theme '{slug}' is not in the pack; using Omarchy's generated '{FALLBACK_SKIN}' skin."
    return f"Omarchy theme '{slug}' is not in the pack and no '{FALLBACK_SKIN}' skin exists; skin unchanged."


def follow(enabled):
    target = omarchy_hooks_dir() / HOOK_NAME
    if enabled:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise ThemeError(f"Refusing symlinked hook path {target}")
        atomic_write(target, HOOK_SOURCE.read_bytes())
        target.chmod(0o755)
        return f"Following Omarchy: hook installed at {target}"
    if target.exists() and target.read_bytes() == HOOK_SOURCE.read_bytes():
        target.unlink()
        return "No longer following Omarchy theme changes."
    if target.exists():
        raise ThemeError(f"{target} was changed by hand; remove it yourself")
    return "Omarchy follow was not enabled."


def following():
    target = omarchy_hooks_dir() / HOOK_NAME
    return target.exists() and target.read_bytes() == HOOK_SOURCE.read_bytes()


# ── command surface (shared by /theme, `hermes theme` and the hook) ────────

USAGE = """Usage: /theme [list | <name> | omarchy | follow on|off | install [--replace] | uninstall]
  /theme              current theme, Omarchy state and the list
  /theme <name>       switch every Hermes surface (CLI, TUI, Desktop) to a pack theme
  /theme omarchy      match the current Omarchy theme once
  /theme follow on    switch Hermes automatically whenever the Omarchy theme changes"""


def listing(home):
    skin = current_skin(home)
    rows = []
    for e in catalog():
        mark = "●" if e["skin"] == skin else " "
        rows.append(f" {mark} {e['label']:<18} {e['skin']:<18} {e['mode']}")
    omarchy = omarchy_theme()
    head = [f"Current skin: {skin}"]
    if omarchy is not None:
        head.append(f"Omarchy theme: {omarchy} · follow {'on' if following() else 'off'}")
    return "\n".join(head + ["", *rows, "", "Switch with /theme <name>."])


def dispatch(words, home=None):
    home = resolve_home(home)
    if not words or words == ["list"]:
        return listing(home)
    verb, rest = words[0].lower(), words[1:]
    if verb in ("help", "-h", "--help"):
        return USAGE
    if verb == "install":
        changed, skipped = install(home, replace="--replace" in rest)
        note = f" Skipped (personal or edited, kept): {', '.join(skipped)}." if skipped else ""
        return f"Installed/updated {len(changed)} skins; selection unchanged.{note}"
    if verb == "uninstall":
        removed, kept = uninstall(home)
        note = f" Kept (edited by you): {', '.join(kept)}." if kept else ""
        return f"Removed {len(removed)} managed skins; selection unchanged.{note}"
    if verb == "omarchy":
        return omarchy_sync(rest[0] if rest else None, home)
    if verb == "follow":
        if rest[:1] not in (["on"], ["off"]):
            return f"Omarchy follow is {'on' if following() else 'off'}. Use /theme follow on|off."
        message = follow(rest[0] == "on")
        if rest[0] == "on" and omarchy_theme():
            message += "\n" + omarchy_sync(None, home)
        return message
    return use(" ".join(words), home)


def configure_parser(parser):
    parser.add_argument("words", nargs="*", help="list | <name> | omarchy [slug] | follow on|off | install | uninstall")
    parser.add_argument("--home", help="Explicit Hermes home; otherwise active profile/HERMES_HOME")
    parser.add_argument("--replace", action="store_true", help="With install: back up and replace personal skins")


def run(args):
    words = list(args.words) + (["--replace"] if args.replace else [])
    try:
        print(dispatch(words, args.home))
    except ThemeError as error:
        print(f"Theme: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    configure_parser(parser)
    try:
        sys.exit(run(parser.parse_args()))
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Theme: {error}\n")
