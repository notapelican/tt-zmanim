"""Modern alternate layout for the sheet.

A second, independent presentation of the *same* block data produced by
``engine.assemble.generate``. It reuses the engine's layout-independent content
functions (``week_items`` / ``day_items`` from ``engine.render_html`` and
``_group_blocks`` from ``engine.render_docx``), so every time, label, section
and note is byte-identical to the classic sheet — this module only decides how
it looks. The engine is never modified and never recomputes a time here.

Design: a clean, elegant, contemporary sheet — a serif display face for
headings, a crisp sans for the data, hairline section rules, right-aligned
tabular times, generous whitespace, and a masthead logo slot. Sizing is driven
by a single ``--base`` font-size (everything else is in ``em``), so the whole
sheet scales proportionally; the layout is a responsive grid.

Customization (per sheet, from the dashboard) comes in via ``logo_url`` and a
``theme`` dict. Both are sanitized here — fonts must be one of a whitelisted set
of print-safe stacks and colors must be hex — so a caller can never inject
arbitrary CSS.
"""
from __future__ import annotations

import html as _html
import re

from engine.render_docx import _group_blocks
from engine.render_html import day_items, week_items

_NAME = "Tzemach Tzedek Community Centre"
_ADDR = "1 Penkivil St, Bondi NSW · www.ttcc.org.au · PO Box 477 Waverley NSW 2024"

# Whitelisted, print-safe font stacks (key -> CSS font-family value).
_FONTS = {
    "palatino": '"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif',
    "georgia": 'Georgia,"Times New Roman",Times,serif',
    "garamond": '"EB Garamond","Adobe Garamond Pro",Garamond,Georgia,serif',
    "times": '"Times New Roman",Times,serif',
    "system": '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif',
    "helvetica": '"Helvetica Neue",Helvetica,Arial,sans-serif',
}
_DEFAULT_HEADING = "palatino"
_DEFAULT_BODY = "system"
_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

_CSS = """
:root{
  --ink:#1b1e28; --soft:#464b5c; --muted:#8b90a0; --hair:#e8e9f0;
  --accent:#33417a; --accent-2:#9a6b2f; --paper:#fff;
  --warn:#a3324b; --warn-bg:#fbeef1;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,"Times New Roman",serif;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;background:var(--paper);color:var(--ink);
  font-family:var(--sans);-webkit-font-smoothing:antialiased;line-height:1.4;}
@page{size:A4;margin:0;}
/* Margins live on the sheet (not @page) so the preview, PNG and PDF all frame
   the content identically: text fills the page but keeps clear side margins. */
.sheet{max-width:1040px;margin:0 auto;font-size:15px;padding:9mm 14mm;}

.masthead{display:flex;align-items:center;gap:1.2em;
  padding-bottom:.95em;border-bottom:1px solid var(--ink);}
.logo{flex:0 0 auto;width:3.7em;height:3.7em;border-radius:50%;
  border:1.5px solid var(--accent);display:flex;align-items:center;
  justify-content:center;overflow:hidden;}
.logo img{width:100%;height:100%;object-fit:contain;}
.logo .ph{font-family:var(--sans);font-size:.58em;letter-spacing:.14em;
  text-transform:uppercase;color:var(--muted);}
.mast-txt{flex:1 1 auto;}
.mast-txt h1{margin:0;font-family:var(--serif);font-weight:600;color:var(--ink);
  letter-spacing:-.01em;font-size:2.05em;line-height:1.05;}
.mast-txt .addr{margin-top:.4em;color:var(--muted);font-size:.72em;letter-spacing:.03em;}
.bsd{flex:0 0 auto;align-self:flex-start;color:var(--muted);font-size:1em;font-family:var(--serif);}

.grid{display:grid;grid-template-columns:1fr;gap:1.7em;margin-top:1.3em;}
.grid.multi{grid-template-columns:repeat(2,1fr);gap:1.4em 2.2em;}
.wk{break-inside:avoid;}
.wk-h{margin-bottom:.4em;}
.wk-h h2{margin:0;font-family:var(--serif);font-weight:600;color:var(--ink);
  font-size:1.5em;letter-spacing:-.01em;}
.wk-sub{margin-top:.2em;color:var(--muted);font-size:.82em;letter-spacing:.02em;}

.sec{margin-top:1em;}
.sec.plain{margin-top:.5em;}
.sec-h{font-weight:700;text-transform:uppercase;letter-spacing:.13em;color:var(--accent);
  font-size:.76em;padding-bottom:.34em;margin-bottom:.2em;border-bottom:1.5px solid var(--accent);}
.sec.shabbos .sec-h{color:var(--accent-2);border-bottom-color:var(--accent-2);}
.row{display:flex;align-items:baseline;justify-content:space-between;gap:1.2em;
  padding:.42em 0;border-bottom:1px solid var(--hair);}
.row:last-child{border-bottom:none;}
.row .lbl{flex:1 1 auto;color:var(--soft);font-size:.98em;}
.row .val{flex:0 0 auto;color:var(--ink);font-weight:600;white-space:nowrap;
  font-variant-numeric:tabular-nums;font-size:.98em;}
.row.bullet .lbl::before{content:"\\2022\\00a0\\00a0";color:var(--accent-2);}
.subhead{font-weight:700;color:var(--ink);margin:.6em 0 .05em;font-size:.82em;}
.molad{color:var(--muted);font-style:italic;padding:.32em 0 .05em;font-size:.76em;}
.callout{margin-top:.85em;padding:.66em .9em;border-radius:8px;background:var(--warn-bg);
  border-left:3px solid var(--warn);color:var(--warn);font-weight:600;font-size:.9em;}
.notes{margin-top:1em;border-top:1px solid var(--hair);padding-top:.6em;}
.foot-notes{margin-top:1.4em;border-top:1px solid var(--ink);padding-top:.65em;}
.note{color:var(--muted);font-style:italic;margin:.2em 0;font-size:.76em;}
"""


def _esc(s) -> str:
    return _html.escape(str(s), quote=False)


def _color(v) -> str | None:
    if isinstance(v, str) and _HEX_RE.match(v.strip()):
        return v.strip()
    return None


_GF_RE = re.compile(r"[^A-Za-z0-9 ]")


def _gfamily(v) -> str | None:
    """Sanitize a Google-Fonts family name to letters/digits/spaces so it can be
    safely dropped into a stylesheet URL and a font-family value."""
    if not isinstance(v, str):
        return None
    name = _GF_RE.sub("", v).strip()
    return name[:50] if name else None


def _kit(v) -> str | None:
    """Sanitize an Adobe Fonts (Typekit) web-project id to lowercase alnum."""
    if not isinstance(v, str):
        return None
    k = re.sub(r"[^a-z0-9]", "", v.strip().lower())
    return k[:20] if k else None


def _webfont_links(theme: dict | None) -> str:
    """<link> tags for custom web fonts. Adobe loads its whole kit (families come
    from the project); Google loads each requested family. Chromium fetches these
    at render time; if egress/licensing blocks them the fallback stack is used."""
    if not isinstance(theme, dict):
        return ""
    links: list[str] = []
    kit = _kit(theme.get("adobe_kit"))
    if kit:
        links.append(f'<link rel="stylesheet" href="https://use.typekit.net/{kit}.css">')
    if "adobe" != theme.get("font_source"):  # default/Google: load each family
        fams: list[str] = []
        for k in ("custom_heading", "custom_body"):
            fam = _gfamily(theme.get(k))
            if fam and fam not in fams:
                fams.append(fam)
        for fam in fams:
            links.append(
                '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
                f'family={fam.replace(" ", "+")}:wght@400;600;700&display=swap">')
    return "".join(links)


def _theme_css(theme: dict | None) -> str:
    """Build a sanitized ``:root`` / ``.sheet`` override block from the theme
    dict. Only whitelisted fonts and hex colors are honored; everything else is
    ignored, so a caller can never inject arbitrary CSS."""
    if not isinstance(theme, dict):
        return ""
    root: list[str] = []
    hf = theme.get("heading_font")
    if hf in _FONTS:
        root.append(f"--serif:{_FONTS[hf]};")
    bf = theme.get("body_font")
    if bf in _FONTS:
        root.append(f"--sans:{_FONTS[bf]};")
    # Custom families (Google or Adobe) win over the whitelisted stacks
    # (appended after, so the later --serif/--sans declaration takes effect).
    ch = _gfamily(theme.get("custom_heading"))
    if ch:
        root.append(f'--serif:"{ch}",Georgia,"Times New Roman",serif;')
    cb = _gfamily(theme.get("custom_body"))
    if cb:
        root.append(f'--sans:"{cb}",-apple-system,"Segoe UI",Arial,sans-serif;')
    text = _color(theme.get("text_color"))
    if text:
        root.append(f"--ink:{text};--soft:{text};")
    cbg = _color(theme.get("callout_bg"))
    if cbg:
        root.append(f"--warn-bg:{cbg};")
    ctext = _color(theme.get("callout_text"))
    if ctext:
        root.append(f"--warn:{ctext};")

    sheet = ""
    try:
        base = float(theme.get("base"))
    except (TypeError, ValueError):
        base = None
    if base is not None:
        base = max(11.0, min(24.0, base))
        sheet = f".sheet{{font-size:{base:g}px;}}"

    if not root and not sheet:
        return ""
    root_css = f":root{{{''.join(root)}}}" if root else ""
    return f'<style id="ttcc-theme">{root_css}{sheet}</style>'


def _row(lbl: str, val: str, bullet: bool) -> str:
    cls = "row bullet" if bullet else "row"
    return (f'<div class="{cls}"><span class="lbl">{_esc(lbl)}</span>'
            f'<span class="val">{_esc(val)}</span></div>')


class _SectionBuilder:
    """Walks the engine's typed item stream and emits elegant section blocks.

    Sections from the Shabbos portion of the week (everything at/after the
    purple 'Shabbos kodesh' divider) get the warm bronze accent; the rest get
    the indigo accent.
    """

    def __init__(self) -> None:
        self.parts: list[str] = []
        self._open = False
        self._shabbos = False

    def _close(self) -> None:
        if self._open:
            self.parts.append("</div></div>")
            self._open = False

    def _open_titled(self, label: str, color: str) -> None:
        if color == "purple":
            self._shabbos = True
        self._close()
        cls = "sec shabbos" if self._shabbos else "sec"
        self.parts.append(
            f'<div class="{cls}"><div class="sec-h">{_esc(label)}</div><div class="rows">')
        self._open = True

    def _ensure_plain(self) -> None:
        if not self._open:
            self.parts.append('<div class="sec plain"><div class="rows">')
            self._open = True

    def feed(self, items) -> None:
        for it in items:
            kind = it[0]
            if kind in ("title", "subtitle"):
                continue  # the caller renders these as the card header
            if kind == "bar":
                self._open_titled(it[1], it[2])
            elif kind == "subhead":
                self._ensure_plain()
                self.parts.append(f'<div class="subhead">{_esc(it[1])}</div>')
            elif kind in ("zman", "line"):
                self._ensure_plain()
                bullet = len(it) > 3 and bool(it[3])
                self.parts.append(_row(it[1], it[2], bullet))
            elif kind == "molad":
                self._ensure_plain()
                self.parts.append(f'<div class="molad">{_esc(it[1])}</div>')
            elif kind == "fastbox":
                self._close()
                self.parts.append(f'<div class="callout">{_esc(it[1])}</div>')
            elif kind == "note":
                self._ensure_plain()
                self.parts.append(f'<div class="note">{_esc(it[1])}</div>')

    def html(self) -> str:
        self._close()
        return "".join(self.parts)


def _notes_html(notes, cls: str = "notes") -> str:
    if not notes:
        return ""
    body = "".join(f'<div class="note">{_esc(n)}</div>' for n in notes)
    return f'<div class="{cls}">{body}</div>'


def _week_html(block: dict) -> str:
    items = week_items(block, notes_inline=False)
    title = next((it[1] for it in items if it[0] == "title"), block.get("title", ""))
    subtitle = next((it[1] for it in items if it[0] == "subtitle"), "")
    sb = _SectionBuilder()
    sb.feed(items)
    return (
        '<section class="wk">'
        f'<header class="wk-h"><h2>{_esc(title)}</h2>'
        f'<div class="wk-sub">{_esc(subtitle)}</div></header>'
        f'{sb.html()}{_notes_html(block.get("notes", []))}'
        '</section>')


def _day_html(day: dict) -> str:
    items = day_items(day)
    heading = items[0][1] if items and items[0][0] == "bar" else (day.get("title") or "")
    sb = _SectionBuilder()
    sb.feed(items[1:])  # the leading bar becomes the card header
    return (
        '<section class="wk">'
        f'<header class="wk-h"><h2>{_esc(heading)}</h2></header>'
        f'{sb.html()}'
        '</section>')


def _logo_html(logo_url: str | None) -> str:
    if isinstance(logo_url, str) and logo_url.strip():
        return f'<div class="logo"><img src="{_esc(logo_url.strip())}" alt="logo"></div>'
    return '<div class="logo"><span class="ph">logo</span></div>'


def render_modern(doc_data: dict, *, variant: str = "print",
                  logo_url: str | None = None, theme: dict | None = None) -> str:
    """Render the block data as a self-contained modern HTML sheet.

    ``logo_url`` (URL or data: URI) fills the masthead logo slot; without it a
    subtle placeholder marks the space. ``theme`` optionally overrides fonts,
    base size and colors (sanitized). ``variant`` is accepted for signature
    parity; the layout is fluid, so portrait sizing is handled by the
    rasterizer's fit step.
    """
    groups = _group_blocks(doc_data["blocks"])
    multi = len(groups) > 1

    # Hoist notes common to every week to a single sheet footer (like classic).
    shared_notes: list[str] = []
    if multi and groups:
        common = set.intersection(*(set(g["week"].get("notes", [])) for g in groups))
        shared_notes = [n for n in groups[0]["week"].get("notes", []) if n in common]
        for g in groups:
            g["week"] = dict(g["week"],
                             notes=[n for n in g["week"].get("notes", []) if n not in common])

    cards: list[str] = []
    for g in groups:
        cards.append(_week_html(g["week"]))
        for day in g.get("days", []):
            cards.append(_day_html(day))

    masthead = (
        '<div class="masthead">'
        f'{_logo_html(logo_url)}'
        f'<div class="mast-txt"><h1>{_esc(_NAME)}</h1>'
        f'<div class="addr">{_esc(_ADDR)}</div></div>'
        '<div class="bsd">בס״ד</div>'
        '</div>')
    grid_cls = "grid multi" if multi else "grid"
    body = (f'{masthead}<div class="{grid_cls}">{"".join(cards)}</div>'
            f'{_notes_html(shared_notes, "foot-notes")}')
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<style>{_CSS}</style>{_webfont_links(theme)}{_theme_css(theme)}</head>'
        f'<body class="sheet-body"><div class="sheet">{body}</div></body></html>')
