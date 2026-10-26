# Hermes Themes Pack

All Omarchy themes as Hermes skins, plus one command to switch them: `/theme`.
A skin is Hermes' single theme unit: the CLI, the TUI and the Desktop app all
repaint from it within a second. Optionally Hermes follows the Omarchy theme:
pick a theme in Omarchy and Hermes switches with it.

No core patches, monkeypatches, load-time side effects, network calls or remote
fonts. MIT licensed. Independent community package, not an upstream Hermes or
Omarchy product. Replaces the separate `hermes-tokyo-night` and
`hermes-jade-horse` packages.

## Commands

```
/theme                 current skin, Omarchy theme, follow state and the list
/theme <name>          switch every Hermes surface (e.g. /theme nord, /theme "Tokyo Night")
/theme omarchy         match the current Omarchy theme once
/theme follow on|off   follow Omarchy theme changes automatically
/theme install         install/update all pack skins without selecting one
/theme uninstall       remove the pack's managed skins (selection unchanged)
```

`/theme` works in the CLI, the TUI, the Desktop composer and messaging
gateways. The same verbs are available as `hermes theme ...` in a shell when
`plugins.isolation` is `in_process` (Hermes wires plugin CLI subcommands only
then); otherwise use `/theme` or `python3 ~/.hermes/plugins/hermes-themes-pack/installer.py`.

Switching always goes through Hermes' own writer
(`hermes config set display.skin <name>`), which updates the active profile and
makes the running gateway broadcast the change to every surface.

## Install

```sh
hermes plugins install seppegadeyne/hermes-themes-pack --no-deps
hermes plugins enable hermes-themes-pack
```

Then in any session: `/theme nord`, or `/theme follow on`.

From a local clone use `hermes plugins install "file://$(pwd)" --no-deps`.
`--no-deps` keeps a plugin disabled until the explicit enable (the package has no
dependencies).

## Following Omarchy

`/theme follow on` installs a small hook at
`~/.config/omarchy/hooks/theme-set.d/50-hermes-themes-pack`. Omarchy runs it after
every theme switch with the theme slug; it calls this package's installer, which
selects the matching pack skin. A theme that is not in the pack (for example
`osaka-jade`, which ships no palette, or a theme you installed from git) falls
back to Omarchy's own generated `omarchy` skin. The hook does nothing when the
package is removed, and `/theme follow off` removes only an unmodified copy.

Omarchy itself also writes an `omarchy` skin on every theme switch and activates
it only when Hermes is on `default`/`omarchy`, so it never overrides a pack skin.

## Themes

Every Omarchy stock theme with a palette (23). Desktop built-in names are avoided
because a backend skin with such a name never paints in the Desktop app:
`catppuccin` → `catppuccin-mocha`, `everforest` → `everforest-dark`.
Tokyo Night and Jade Horse use hand-tuned skins; the others are generated from
the theme's `colors.toml` with recolored banner art.

Add a theme: create `themes/<slug>/colors.toml` (copy an Omarchy theme's file),
optionally `skin.yaml` (hand-made, wins) and `meta.json`
(`{"skin": "...", "label": "..."}`), then run `python3 tools/build.py` and commit
`skins/`. The slug should equal the Omarchy theme slug so following works.

## Desktop

There is no separate desktop half: the Desktop app converts the active skin into
its own palette, so `/theme` (or Appearance) covers it. Light themes paint light.
Desktop appearance is per profile; a switch from `/theme` is applied to the
profile it runs in.

## Uninstall

```
/theme follow off
/theme uninstall
```

```sh
hermes config set display.skin default
hermes plugins remove hermes-themes-pack
```

The installer keeps a receipt at `$HERMES_HOME/theme-packages/hermes-themes-pack.json`.
It never overwrites a personal skin with the same name (`/theme install --replace`
backs it up and restores it on uninstall), and it leaves skins you edited alone.

## Development and tests

```sh
python3 tools/build.py
python3 -m unittest discover -s tests -v
HERMES_REPO=/path/to/hermes-agent "$HERMES_REPO/venv/bin/python" tests/hermes-integration.py
hermes plugins validate .
```

The integration test uses a temporary `HERMES_HOME` and `XDG_CONFIG_HOME`.

## Credits

Palettes from the Omarchy stock themes by David Heinemeier Hansson and theme
contributors (MIT), https://github.com/basecamp/omarchy. Jade Horse:
https://github.com/dhh/omarchy-jade-horse-theme.
