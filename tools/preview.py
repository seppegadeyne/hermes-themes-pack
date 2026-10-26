"""Render the catalog banner and screenshots from the committed skins (dev-only tool).

Needs Rich (run with a Hermes checkout's Python) and a local Chromium/Chrome:

    ~/.hermes/hermes-agent/venv/bin/python tools/preview.py

Everything is drawn from skins/*.yaml: banner art, palette and labels. Output goes to
docs/. Fonts are local monospace fonts only; nothing is fetched.
"""
import html
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from rich.console import Console
from rich.text import Text
import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SHOTS = ("tokyo-night", "jade-horse", "nord", "catppuccin-latte", "gruvbox", "rose-pine")
FONT = "'CaskaydiaMono Nerd Font Mono', 'JetBrainsMono Nerd Font Mono', 'DejaVu Sans Mono', monospace"
SWATCHES = ("ui_accent", "ui_tool", "ui_ok", "ui_warn", "ui_error", "syntax_keyword", "syntax_string")


def load(skin):
    return yaml.safe_load((ROOT / "skins" / f"{skin}.yaml").read_text(encoding="utf-8"))


def markup_html(markup, width):
    console = Console(record=True, width=width, file=open("/dev/null", "w"), color_system="truecolor")
    console.print(Text.from_markup(markup), overflow="crop", no_wrap=True)
    body = console.export_html(inline_styles=True, code_format="{code}")
    return f"<pre>{body}</pre>"


def swatches(colors):
    return "".join(f'<i style="background:{colors[key]}"></i>' for key in SWATCHES)


def tile(entry):
    skin = load(entry["skin"])
    c = skin["colors"]
    return (f'<div class="tile" style="background:{c["background"]};border-color:{c["ui_border"]}">'
            f'{markup_html(skin["banner_hero"], 30)}'
            f'<b style="color:{c["banner_title"]}">{html.escape(entry["label"])}</b>'
            f'<div class="sw">{swatches(c)}</div></div>')


def page(body, width, height, background="#0d0d0f"):
    return f"""<!doctype html><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0}}
body{{width:{width}px;height:{height}px;background:{background};font-family:{FONT};overflow:hidden}}
pre{{font-family:{FONT};line-height:1.0;margin:0}}
pre code, pre span{{font-family:{FONT}}}
.grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;padding:12px;height:100%}}
.tile{{border:1px solid;border-radius:6px;padding:8px 6px 6px;display:flex;flex-direction:column;align-items:center;justify-content:space-between;overflow:hidden}}
.tile pre{{font-size:6.4px}}
.tile b{{font-size:11px;margin-top:4px;white-space:nowrap}}
.sw{{display:flex;gap:3px;margin-top:4px}} .sw i{{width:12px;height:6px;border-radius:2px;display:block}}
.title{{display:flex;flex-direction:column;justify-content:center;padding:10px;color:#e6e6e6;border:1px solid #333;border-radius:6px}}
.title h1{{font-size:17px;line-height:1.15}} .title p{{font-size:10px;color:#9a9a9a;margin-top:8px;line-height:1.4}}
.shot{{padding:28px 32px;height:100%;display:flex;flex-direction:column;gap:18px}}
.shot .logo pre{{font-size:9.6px}} .shot .hero pre{{font-size:13px}}
.row{{display:flex;gap:36px;align-items:center}}
.lines{{font-size:15px;line-height:1.7}} .lines span{{display:block}}
.sw.big i{{width:34px;height:14px}}
</style><body>{body}</body>"""


def banner():
    entries = json.loads((ROOT / "skins" / "index.json").read_text(encoding="utf-8"))
    title = ('<div class="title"><h1>Hermes<br>Themes Pack</h1>'
             f'<p>{len(entries)} Omarchy themes as Hermes skins.<br>/theme &lt;name&gt; switches CLI, TUI and Desktop.</p></div>')
    return page(f'<div class="grid">{title}{"".join(tile(e) for e in entries)}</div>', 1200, 600)


def shot(skin_name):
    skin = load(skin_name)
    c = skin["colors"]
    label = skin["description"].split(" — ")[0]
    lines = [
        ("banner_title", f"/theme {skin_name}"),
        ("ui_ok", f"✓ Theme: {label} (skin {skin_name})"),
        ("ui_tool", "● terminal  python3 -m unittest discover -s tests"),
        ("ui_thinking", "thinking about the palette…"),
        ("ui_warn", "⚠ warning text"),
        ("ui_error", "✗ error text"),
        ("banner_dim", "muted / secondary text"),
    ]
    text = "".join(f'<span style="color:{c[key]}">{html.escape(value)}</span>' for key, value in lines)
    body = (f'<div class="shot" style="background:{c["background"]}">'
            f'<div class="logo">{markup_html(skin["banner_logo"], 110)}</div>'
            f'<div class="row"><div class="hero">{markup_html(skin["banner_hero"], 30)}</div>'
            f'<div class="lines">{text}<div class="sw big">{swatches(c)}</div></div></div></div>')
    return page(body, 1200, 600, c["background"])


def browser():
    for name in ("chromium", "google-chrome-stable", "google-chrome", "chrome"):
        if shutil.which(name):
            return shutil.which(name)
    sys.exit("Chromium or Chrome is required")


def render(document, target):
    with tempfile.TemporaryDirectory(prefix="themes-preview-") as tmp:
        source = Path(tmp) / "page.html"
        source.write_text(document, encoding="utf-8")
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([browser(), "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                        f"--user-data-dir={tmp}/profile", "--force-device-scale-factor=2",
                        "--window-size=1200,600", f"--screenshot={target}", source.as_uri()],
                       check=True, capture_output=True, timeout=120)
    print(f"wrote {target.relative_to(ROOT)}")


if __name__ == "__main__":
    render(banner(), DOCS / "catalog-banner.png")
    for name in SHOTS:
        render(shot(name), DOCS / "screenshots" / f"{name}.png")
