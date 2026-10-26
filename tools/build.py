#!/usr/bin/env python3
"""Generate skins/*.yaml and skins/index.json from themes/<slug>/. Stdlib only.

One directory per theme under themes/:
  colors.toml  Omarchy palette (the same file an Omarchy theme ships); generated into a skin
  skin.yaml    optional hand-made skin; copied verbatim and wins over colors.toml
  meta.json    optional {"skin": "<skin name>", "label": "...", "description": "..."}

Run after adding or changing a theme:  python3 tools/build.py
"""
import json
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
THEMES = ROOT / "themes"
SKINS = ROOT / "skins"
ART = json.loads((ROOT / "tools" / "banner-art.json").read_text(encoding="utf-8"))
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
REQUIRED = ("accent", "background", "foreground", "dark_background", "lighter_background",
            "selection", "muted", "dark_foreground", "bright_foreground",
            "red", "yellow", "green", "cyan", "blue", "magenta", "bright_red")


def mix(a, b, weight):
    """Blend hex a toward b by weight (0 = a, 1 = b)."""
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * weight):02X}" for x, y in zip(pa, pb))


def skin_colors(c):
    up = {k: v.upper() for k, v in c.items() if isinstance(v, str) and HEX.match(v)}
    missing = [k for k in REQUIRED if k not in up]
    if missing:
        raise ValueError(f"colors.toml lacks {', '.join(missing)}")
    acc, bg, fg = up["accent"], up["background"], up["foreground"]
    title = mix(acc, fg, 0.3)
    orange = up.get("orange", up["bright_red"])
    return {
        "banner_border": up["muted"], "banner_title": title, "banner_accent": up["cyan"],
        "banner_dim": up["dark_foreground"], "banner_text": fg,
        "ui_accent": acc, "ui_label": up["cyan"], "ui_ok": up["green"],
        "ui_error": up["red"], "ui_warn": up["yellow"],
        "prompt": up["bright_foreground"], "input_rule": up["selection"],
        "response_border": acc, "session_label": up["cyan"], "session_border": up["muted"],
        "status_bar_bg": up["dark_background"], "status_bar_text": fg,
        "status_bar_strong": title, "status_bar_dim": up["dark_foreground"],
        "status_bar_good": up["green"], "status_bar_warn": up["yellow"],
        "status_bar_bad": orange, "status_bar_critical": up["red"],
        "voice_status_bg": up["dark_background"],
        "completion_menu_bg": up["lighter_background"],
        "completion_menu_current_bg": up["selection"],
        "completion_menu_meta_bg": up["dark_background"],
        "completion_menu_meta_current_bg": up["selection"],
        "background": bg, "ui_text": fg, "ui_primary": title, "ui_tool": up["cyan"],
        "ui_thinking": up["dark_foreground"], "ui_border": up["muted"],
        "shell_dollar": up["blue"], "selection_bg": up["selection"],
        "diff_added": mix(bg, up["green"], 0.15), "diff_removed": mix(bg, up["red"], 0.15),
        "diff_added_word": up["green"], "diff_removed_word": up["red"],
        "syntax_string": up["green"], "syntax_number": orange,
        "syntax_keyword": up["magenta"], "syntax_comment": up["muted"],
    }


def banner(colors):
    """Recolor the shipped glyph art (logo 6 rows, hero 15 rows) with the theme."""
    fg, acc, cyan = colors["ui_text"], colors["ui_accent"], colors["banner_accent"]
    bg, muted, sel = colors["background"], colors["ui_border"], colors["selection_bg"]
    magenta = colors["syntax_keyword"]
    deep = mix(acc, bg, 0.15)
    logo = [f"bold {fg}", f"bold {fg}", cyan, acc, deep, deep]
    hero = [sel, muted, acc, cyan, magenta, magenta, cyan, acc, mix(magenta, bg, 0.2),
            mix(magenta, bg, 0.2), fg, f"dim {muted}", f"dim {muted}", f"dim {sel}", f"dim {sel}"]
    assert len(logo) == len(ART["logo"]) and len(hero) == len(ART["hero"])
    render = lambda styles, rows: "\n".join(f"[{s}]{r}[/]" for s, r in zip(styles, rows))
    return render(logo, ART["logo"]), render(hero, ART["hero"])


def q(text):
    # JSON strings are valid YAML double-quoted scalars.
    return json.dumps(text, ensure_ascii=False)


def generated_skin(name, description, colors):
    logo, hero = banner(colors)
    lines = [f"name: {name}", f"description: {q(description)}", "colors:"]
    lines += [f"  {k}: '{v}'" for k, v in colors.items()]
    lines += [f"banner_logo: {q(logo)}", f"banner_hero: {q(hero)}", ""]
    return "\n".join(lines)


def build():
    entries, outputs = [], {}
    for theme in sorted(p for p in THEMES.iterdir() if p.is_dir()):
        slug = theme.name
        meta_file = theme / "meta.json"
        meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
        name = meta.get("skin", slug)
        label = meta.get("label", " ".join(w.capitalize() for w in slug.split("-")))
        palette = tomllib.loads((theme / "colors.toml").read_text()) if (theme / "colors.toml").exists() else {}
        mode = palette.get("mode", meta.get("mode", "dark"))
        if (theme / "skin.yaml").exists():
            text = (theme / "skin.yaml").read_text(encoding="utf-8")
            if not text.startswith(f"name: {name}\n"):
                raise ValueError(f"{slug}/skin.yaml must start with 'name: {name}'")
        elif palette:
            description = meta.get("description", f"{label} — Omarchy palette ({mode})")
            text = generated_skin(name, description, skin_colors(palette))
        else:
            raise ValueError(f"{slug}: needs colors.toml or skin.yaml")
        if name in outputs:
            raise ValueError(f"duplicate skin name {name}")
        outputs[name] = text
        entries.append({"slug": slug, "skin": name, "label": label, "mode": mode})
    SKINS.mkdir(exist_ok=True)
    for stale in SKINS.glob("*.yaml"):
        if stale.stem not in outputs:
            stale.unlink()
    for name, text in outputs.items():
        (SKINS / f"{name}.yaml").write_text(text, encoding="utf-8")
    (SKINS / "index.json").write_text(json.dumps(entries, indent=1) + "\n")
    return entries


if __name__ == "__main__":
    built = build()
    print(f"Built {len(built)} skins into {SKINS.relative_to(ROOT)}/", file=sys.stderr)
