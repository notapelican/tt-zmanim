"""Modern alternate layout for the sheet.

A second, independent presentation of the *same* block data produced by
``engine.assemble.generate``. It reuses the engine's layout-independent content
functions (``week_items`` / ``day_items`` from ``engine.render_html`` and
``_group_blocks`` from ``engine.render_docx``), so every time, label, section
and note is byte-identical to the classic sheet — this module only decides how
it looks. The engine is never modified and never recomputes a time here.

Design: a clean, elegant, contemporary sheet — a serif display face for
headings, a crisp sans for the data, a restrained indigo/bronze palette, hairline
rules instead of heavy bars, right-aligned tabular times, and generous
whitespace. Typography is fluid (``clamp()``) and the layout is a responsive
grid, so it reads well and fills the page at any size (A4 PDF, portrait PNG,
screen). A logo slot sits in the masthead.
"""
from __future__ import annotations

import html as _html

from engine.render_docx import _group_blocks
from engine.render_html import day_items, week_items

_NAME = "Tzemach Tzedek Community Centre"
_ADDR = "1 Penkivil St, Bondi NSW · www.ttcc.info · PO Box 477 Waverley NSW 2024"

_CSS = """
:root{
  --ink:#1b1e28; --soft:#464b5c; --muted:#8b90a0; --hair:#e8e9f0;
  --accent:#33417a; --accent-2:#9a6b2f; --panel:#faf9f7; --paper:#fff;
  --warn:#a3324b; --warn-bg:#fbeef1;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,"Times New Roman",serif;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;background:var(--paper);color:var(--ink);
  font-family:var(--sans);-webkit-font-smoothing:antialiased;line-height:1.4;}
@page{size:A4;margin:15mm;}
.sheet{max-width:1040px;margin:0 auto;}

/* masthead */
.masthead{display:flex;align-items:center;gap:18px;
  padding-bottom:14px;border-bottom:1px solid var(--ink);}
.logo{flex:0 0 auto;width:clamp(46px,6vw,64px);height:clamp(46px,6vw,64px);
  border-radius:50%;border:1.5px solid var(--accent);display:flex;
  align-items:center;justify-content:center;overflow:hidden;}
.logo img{width:100%;height:100%;object-fit:contain;}
.logo .ph{font-family:var(--sans);font-size:9px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--muted);}
.mast-txt{flex:1 1 auto;}
.mast-txt h1{margin:0;font-family:var(--serif);font-weight:600;color:var(--ink);
  letter-spacing:-.01em;font-size:clamp(20px,3vw,32px);line-height:1.05;}
.mast-txt .addr{margin-top:6px;color:var(--muted);font-size:clamp(10px,1.1vw,12px);
  letter-spacing:.03em;}
.bsd{flex:0 0 auto;align-self:flex-start;color:var(--muted);
  font-size:15px;font-family:var(--serif);}

/* layout */
.grid{display:grid;grid-template-columns:1fr;gap:26px;margin-top:20px;}
.grid.multi{grid-template-columns:repeat(2,1fr);gap:22px 34px;}
.wk{break-inside:avoid;}
.wk-h{margin-bottom:6px;}
.wk-h h2{margin:0;font-family:var(--serif);font-weight:600;color:var(--ink);
  font-size:clamp(17px,2.3vw,25px);letter-spacing:-.01em;}
.wk-sub{margin-top:3px;color:var(--muted);font-size:clamp(11px,1.3vw,14px);
  letter-spacing:.02em;}

/* sections — elegant label + hairline, no heavy bars */
.sec{margin-top:15px;}
.sec.plain{margin-top:8px;}
.sec-h{font-weight:700;text-transform:uppercase;letter-spacing:.13em;
  color:var(--accent);font-size:clamp(10.5px,1.15vw,12.5px);
  padding-bottom:5px;margin-bottom:3px;border-bottom:1.5px solid var(--accent);}
.sec.shabbos .sec-h{color:var(--accent-2);border-bottom-color:var(--accent-2);}
.rows{}
.row{display:flex;align-items:baseline;justify-content:space-between;gap:18px;
  padding:6.5px 0;border-bottom:1px solid var(--hair);}
.row:last-child{border-bottom:none;}
.row .lbl{flex:1 1 auto;color:var(--soft);font-size:clamp(12.5px,1.5vw,15.5px);}
.row .val{flex:0 0 auto;color:var(--ink);font-weight:600;white-space:nowrap;
  font-variant-numeric:tabular-nums;font-size:clamp(12.5px,1.5vw,15.5px);}
.row.bullet .lbl::before{content:"\\2022\\00a0\\00a0";color:var(--accent-2);}
.subhead{font-weight:700;color:var(--ink);margin:9px 0 1px;
  font-size:clamp(11px,1.25vw,13.5px);}
.molad{color:var(--muted);font-style:italic;padding:5px 0 1px;
  font-size:clamp(10.5px,1.15vw,12.5px);}
.callout{margin-top:13px;padding:10px 14px;border-radius:8px;
  background:var(--warn-bg);border-left:3px solid var(--warn);color:var(--warn);
  font-weight:600;font-size:clamp(11.5px,1.35vw,14px);}
.notes{margin-top:16px;border-top:1px solid var(--hair);padding-top:9px;}
.foot-notes{margin-top:22px;border-top:1px solid var(--ink);padding-top:10px;}
.note{color:var(--muted);font-style:italic;margin:3px 0;
  font-size:clamp(10.5px,1.2vw,12.5px);}
"""


def _esc(s) -> str:
    return _html.escape(str(s), quote=False)


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
    inner = (f'<img src="{_esc(logo_url)}" alt="logo">' if logo_url
             else '<span class="ph">logo</span>')
    return f'<div class="logo">{inner}</div>'


def render_modern(doc_data: dict, *, variant: str = "print",
                  logo_url: str | None = None) -> str:
    """Render the block data as a self-contained modern HTML sheet.

    ``logo_url`` (URL or data: URI) fills the masthead logo slot; without it a
    subtle placeholder marks the space. ``variant`` is accepted for signature
    parity with the classic renderer; the layout is fluid, so portrait sizing is
    handled by the rasterizer's fit step.
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
        f'<style>{_CSS}</style></head>'
        f'<body class="sheet-body"><div class="sheet">{body}</div></body></html>')
