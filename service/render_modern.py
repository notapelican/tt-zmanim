"""Modern alternate layout for the sheet.

A second presentation of the *same* block data produced by
``engine.assemble.generate``. It reuses the engine's layout-independent content
functions (``week_items`` / ``day_items`` from ``engine.render_html``, and
``_group_blocks`` from ``engine.render_docx``), so every time, label, section
and note is byte-identical to the classic sheet — this module only decides how
it looks. The engine is never modified and never recomputes a time here.

Design goals (vs the faithful "classic" reproduction):
  - Clean, contemporary, high legibility: generous whitespace, a strong
    typographic hierarchy, right-aligned tabular times, colored section headers.
  - Fluid: ``clamp()`` typography + a responsive grid so it reads well and
    fills the page at any page/canvas size (A4 PDF, portrait PNG, on screen).
"""
from __future__ import annotations

import html as _html

from engine.render_docx import _group_blocks
from engine.render_html import day_items, week_items

# Same shul identity strings as the classic renderer.
_NAME = "Tzemach Tzedek Community Centre"
_ADDR = ("1 Penkivil St, Bondi, NSW.&nbsp;&nbsp;www.ttcc.info<br>"
         "Mailing address: PO Box 477 Waverley NSW 2024")

_CSS = """
:root{
  --ink:#1b1f2a; --muted:#6b7280; --line:#e6e8ef;
  --blue:#1d4ed8; --purple:#6d28d9; --paper:#fff;
  --warn:#e11d48; --warn-bg:#fff1f2; --warn-ink:#9f1239;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;background:var(--paper);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  -webkit-font-smoothing:antialiased;line-height:1.35;}
@page{size:A4;margin:14mm;}
.sheet{max-width:1000px;margin:0 auto;}
.masthead{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;
  padding-bottom:10px;border-bottom:3px solid var(--blue);}
.masthead h1{margin:0;color:var(--blue);font-weight:800;letter-spacing:-.02em;
  font-size:clamp(21px,3.1vw,34px);}
.masthead .addr{color:var(--muted);margin-top:5px;font-size:clamp(11px,1.15vw,13px);}
.masthead .bsd{color:var(--muted);font-size:15px;white-space:nowrap;}
.grid{display:grid;grid-template-columns:1fr;gap:22px;margin-top:16px;}
.grid.multi{grid-template-columns:repeat(2,1fr);gap:18px 26px;}
.wk{break-inside:avoid;}
.wk-h h2{margin:0;font-weight:750;color:var(--ink);font-size:clamp(17px,2.3vw,25px);}
.wk-sub{color:var(--muted);margin-top:2px;font-size:clamp(12px,1.35vw,15px);}
.sec{margin-top:13px;border:1px solid var(--line);border-radius:12px;overflow:hidden;}
.sec-h{padding:7px 14px;color:#fff;background:var(--blue);font-weight:700;
  text-transform:uppercase;letter-spacing:.06em;font-size:clamp(11px,1.25vw,13.5px);}
.sec.purple .sec-h{background:var(--purple);}
.sec.plain{border:none;border-radius:0;}
.rows{padding:4px 14px;}
.sec.plain .rows{padding:2px 2px;}
.row{display:flex;align-items:baseline;gap:12px;padding:7px 0;border-bottom:1px solid var(--line);}
.row:last-child{border-bottom:none;}
.row .lbl{flex:1 1 auto;font-size:clamp(12.5px,1.5vw,16px);}
.row .val{font-variant-numeric:tabular-nums;font-weight:700;white-space:nowrap;
  font-size:clamp(12.5px,1.5vw,16px);}
.row.bullet .lbl::before{content:"\\2022\\00a0\\00a0";color:var(--blue);}
.subhead{font-weight:700;margin:9px 0 1px;font-size:clamp(11.5px,1.3vw,14px);}
.molad{color:var(--muted);font-style:italic;padding:5px 0 2px;font-size:clamp(11px,1.2vw,13px);}
.callout{margin-top:12px;border-left:4px solid var(--warn);background:var(--warn-bg);
  color:var(--warn-ink);border-radius:8px;padding:10px 14px;font-weight:600;
  font-size:clamp(12px,1.4vw,15px);}
.notes{margin-top:13px;border-top:1px solid var(--line);padding-top:8px;}
.note{color:var(--muted);font-style:italic;margin:3px 0;font-size:clamp(11px,1.2vw,13px);}
"""


def _esc(s) -> str:
    return _html.escape(str(s), quote=False)


def _row(lbl: str, val: str, bullet: bool) -> str:
    cls = "row bullet" if bullet else "row"
    return (f'<div class="{cls}"><span class="lbl">{_esc(lbl)}</span>'
            f'<span class="val">{_esc(val)}</span></div>')


class _SectionBuilder:
    """Walks the engine's typed item stream and emits modern section cards."""

    def __init__(self) -> None:
        self.parts: list[str] = []
        self._open = False

    def _close(self) -> None:
        if self._open:
            self.parts.append("</div></div>")
            self._open = False

    def _open_titled(self, label: str, color: str) -> None:
        self._close()
        cls = "sec purple" if color == "purple" else "sec"
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
                continue  # handled by the caller as the card header
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


def _notes_html(notes) -> str:
    if not notes:
        return ""
    body = "".join(f'<div class="note">{_esc(n)}</div>' for n in notes)
    return f'<div class="notes">{body}</div>'


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
    sb.feed(items[1:])  # skip the leading bar; it becomes the card header
    return (
        '<section class="wk">'
        f'<header class="wk-h"><h2>{_esc(heading)}</h2></header>'
        f'{sb.html()}'
        '</section>')


def render_modern(doc_data: dict, *, variant: str = "print") -> str:
    """Render the block data as a self-contained modern HTML sheet.

    ``variant`` is accepted for signature parity with the classic renderer; the
    layout is fluid, so portrait sizing is handled by the rasterizer's fit step.
    """
    groups = _group_blocks(doc_data["blocks"])
    multi = len(groups) > 1

    cards: list[str] = []
    for g in groups:
        cards.append(_week_html(g["week"]))
        for day in g.get("days", []):
            cards.append(_day_html(day))

    masthead = (
        '<div class="masthead">'
        f'<div><h1>{_esc(_NAME)}</h1><div class="addr">{_ADDR}</div></div>'
        '<div class="bsd">בס״ד</div>'
        '</div>')
    grid_cls = "grid multi" if multi else "grid"
    body = f'{masthead}<div class="{grid_cls}">{"".join(cards)}</div>'
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<style>{_CSS}</style></head>'
        f'<body class="sheet-body"><div class="sheet">{body}</div></body></html>')
