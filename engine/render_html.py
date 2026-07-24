"""HTML renderer (proof of concept, warplan module 4 — presentation half,
alternate target): render the plain block data from `assemble.generate()` as
self-contained HTML/CSS matching the TTCC house style.

Why HTML alongside the .docx renderer: CSS has native primitives for exactly
this page (dotted leaders, colored section bars, two-column flow with a divider
rule, boxed notices), so it reaches the sample fidelity far more directly, and
the result opens in a browser, imports into Word/Google Docs for editing, and
prints to a clean PDF via headless Chromium.

Layout/styling ONLY — never computes or re-rounds a time. The section-ordering
and line-merge logic is format-independent and is reused verbatim from
render_docx (imported below), so both renderers agree on WHAT prints; this
module only decides how it looks.
"""
from __future__ import annotations

import html as _html
from datetime import date as _date

from .render_docx import (EARLY_ES, KEY_TIMES, SHABBOS_DAY,
                          _SHABBOS_DAY_RULE_PRIORITY, WEEKDAY, _fast_box_text,
                          _fmt_ampm, _fmt_civil_date, _fmt_civil_range,
                          _join_dayspec_group, _partition_week_entries)

# --- merge logic: block entries -> (label, value, bullet) lines -------------
# Mirrors render_docx._render_entry_group / _render_label_run, but returns
# plain (label, value) parts instead of drawing them.

def _label_run_parts(run, dayspec_before_leader, bullet):
    label = run[0]["label"]
    groups: list[tuple[str | None, list[dict]]] = []
    for e in run:
        if groups and groups[-1][0] == e["day_spec"]:
            groups[-1][1].append(e)
        else:
            groups.append((e["day_spec"], [e]))
    if len(groups) == 1:
        day_spec, ge = groups[0]
        value = _join_dayspec_group(ge)
        if day_spec and dayspec_before_leader:
            return (f"{label} {day_spec}", value, bullet)
        if day_spec:
            return (label, f"{day_spec} {value}", bullet)
        return (label, value, bullet)
    joined = "; ".join(
        f"{ds} {_join_dayspec_group(ge)}" if ds else _join_dayspec_group(ge)
        for ds, ge in groups)
    label_text = f"{label}:" if label == "Shacharis" else label
    return (label_text, joined, bullet)


def _emit_lines(items, ents, *, kind="line", bullet=False, dayspec_before_leader=False):
    """Append line items for a section's entries, emitting a no-time
    ``kind=='freetext'`` entry (e.g. a Kiddush notice) as a plain in-place
    'freeline' item and batching the surrounding timed entries through the
    normal label/day-spec merge."""
    batch = []

    def flush():
        for lbl, val, b in _group_lines(batch, dayspec_before_leader=dayspec_before_leader, bullet=bullet):
            items.append((kind, lbl, val, b))
        batch.clear()

    for e in ents:
        if e.get("kind") == "freetext":
            flush()
            items.append(("freeline", e.get("label", "")))
        else:
            batch.append(e)
    flush()


def _group_lines(entries, *, dayspec_before_leader=False, bullet=False):
    merged: list[dict] = []
    for e in entries:
        if (merged and merged[-1]["label"] == e["label"]
                and merged[-1]["day_spec"] == e["day_spec"]):
            merged[-1]["_group"].append(e)
        else:
            merged.append(dict(e, _group=[e]))
    out = []
    i = 0
    while i < len(merged):
        j = i
        while j + 1 < len(merged) and merged[j + 1]["label"] == merged[i]["label"]:
            j += 1
        run = [g for m in merged[i:j + 1] for g in m["_group"]]
        out.append(_label_run_parts(run, dayspec_before_leader, bullet))
        i = j + 1
    return out


# --- layout: block -> ordered list of typed items ---------------------------
# item kinds: title, subtitle, zman, fastbox, note, bar, subhead, line, molad

def week_items(block: dict, *, notes_inline: bool) -> list[tuple]:
    items: list[tuple] = [
        ("title", block["title"]),
        ("subtitle", f"{block['hebrew_dates']}  "
         f"({_fmt_civil_range(block['civil_start'], block['civil_end'])})"),
    ]
    zmanim, fast_runs, named, named_order = _partition_week_entries(block["entries"])
    _emit_lines(items, zmanim, kind="zman", dayspec_before_leader=True)
    for run in fast_runs:
        items.append(("fastbox", _fast_box_text(run)))
    if notes_inline:
        for n in block.get("notes", []):
            items.append(("note", n))

    shabbos_done = False

    def shabbos_bar():
        nonlocal shabbos_done
        if shabbos_done:
            return
        labels = ", ".join([block["parsha"]] + block["shabbos_labels"])
        items.append(("bar", f"Shabbos kodesh: {labels}", "purple"))
        shabbos_done = True

    for section in named_order:
        ents = named[section]
        if section == WEEKDAY:
            items.append(("bar", section, "blue"))
            _emit_lines(items, ents)
            continue
        shabbos_bar()
        if section == KEY_TIMES:
            items.append(("subhead", section))
            _emit_lines(items, ents)
        elif section == SHABBOS_DAY:
            items.append(("bar", section, "blue"))
            _shabbos_day_items(items, ents, block.get("molad"))
        else:
            items.append(("bar", section, "blue"))
            _emit_lines(items, ents, bullet=(section == EARLY_ES))
    shabbos_bar()
    return items


def _shabbos_day_items(items, entries, molad):
    ordered = sorted(enumerate(entries),
                     key=lambda ie: (_SHABBOS_DAY_RULE_PRIORITY.get(ie[1]["rule_id"], 99), ie[0]))
    ents = [e for _, e in ordered]
    split = None
    for idx, e in enumerate(ents):
        if e["rule_id"] in ("shab_shacharis_mev", "shab_shacharis"):
            split = idx + 1
            break
    if molad and split is not None:
        _emit_lines(items, ents[:split])
        items.append(("molad", molad))
        _emit_lines(items, ents[split:])
    else:
        _emit_lines(items, ents)
        if molad:
            items.append(("molad", molad))


def day_items(block: dict) -> list[tuple]:
    title = block["title"] or ", ".join(block["labels"])
    heading = (f"{title}: {block['hebrew_date']} "
               f"({block['weekday']} {_fmt_civil_date(block['date'])})")
    items: list[tuple] = [("bar", heading, "blue")]
    if block.get("omer_day"):
        items.append(("note", f"Day {block['omer_day']} of the Omer"))
    _emit_lines(items, block["entries"])
    return items


# --- HTML emission ----------------------------------------------------------

def _esc(s: str) -> str:
    return _html.escape(s, quote=False)


def _item_html(it: tuple) -> str:
    kind = it[0]
    if kind == "title":
        return f'<div class="title">{_esc(it[1])}</div>'
    if kind == "subtitle":
        return f'<div class="subtitle">{_esc(it[1])}</div>'
    if kind in ("zman", "line"):
        lbl, val = _esc(it[1]), _esc(it[2])
        bullet = len(it) > 3 and it[3]
        cls = "row bullet" if bullet else "row"
        return (f'<div class="{cls}"><span class="lbl">{lbl}</span>'
                f'<span class="dots"></span><span class="val">{val}</span></div>')
    if kind == "fastbox":
        return f'<div class="fastbox">{_esc(it[1])}</div>'
    if kind == "freeline":
        return f'<div class="freeline">{_esc(it[1])}</div>'
    if kind == "note":
        return f'<div class="note">{_esc(it[1])}</div>'
    if kind == "molad":
        return f'<div class="molad">{_esc(it[1])}</div>'
    if kind == "subhead":
        return f'<div class="subhead">{_esc(it[1])}</div>'
    if kind == "bar":
        return f'<div class="barwrap"><span class="bar {it[2]}">{_esc(it[1])}</span></div>'
    return ""


def _week_cell_html(week: dict, *, notes_inline: bool) -> str:
    body = "".join(_item_html(it) for it in week_items(week, notes_inline=notes_inline))
    return f'<div class="week">{body}</div>'


def _day_cell_html(day: dict) -> str:
    body = "".join(_item_html(it) for it in day_items(day))
    return f'<div class="week">{body}</div>'


_CSS = """
:root { --blue:#0000ff; --purple:#800080; }
* { box-sizing: border-box; }
body { font-family: "Times New Roman", Times, serif; color:#000; margin:0; }
.sheet { }
/* The title fills the row (so it can take any text-align) with בס״ד as a
   fixed flex item in the corner — the two can never overlap. Both header
   lines are single-line by contract (.fit-line). */
.hdr-row { display:flex; align-items:flex-start; }
.hdr-title { flex:1 1 auto; min-width:0; color:var(--blue); font-weight:bold; white-space:nowrap; }
.hdr-title .url { text-decoration:underline; margin-left:1.2em; font-size:0.72em; }
.bsd { flex:0 0 auto; font-weight:bold; margin-left:10px; order:2; }
.hdr-sub { color:var(--blue); font-weight:bold; text-align:center; white-space:nowrap; }
.rule { border:0; border-top:3px double #000; margin:4px 0 8px; }
.title { color:var(--blue); font-weight:bold; margin-top:2px; }
.subtitle { color:var(--blue); font-weight:bold; margin-bottom:5px; }
.row { display:flex; align-items:baseline; margin:1px 0; }
.row .lbl { white-space:pre; }
.row.bullet .lbl::before { content:"\\2022  "; }
.row .dots { flex:1 1 auto; border-bottom:1px dotted #000; margin:0 3px; transform:translateY(-3px); }
/* Long merged values (e.g. a fast week's three-way Shacharis split) wrap onto
   right-aligned continuation lines instead of clipping, as on the printed
   sheets. min-width keeps flex from forcing a single overflowing line. */
.row .val { white-space:normal; text-align:right; min-width:0; flex:0 1 auto; }
.barwrap { margin:5px 0 2px; }
.bar { display:inline-block; color:#fff; font-weight:bold; padding:0 5px; }
.bar.blue { background:var(--blue); }
.bar.purple { background:var(--purple); }
.subhead { font-weight:bold; margin:4px 0 1px; }
.note { font-style:italic; margin:1px 0; }
/* free-text (no-time) line, e.g. a Kiddush notice placed within a section */
.freeline { margin:1px 0; font-weight:bold; }
.molad { font-style:italic; margin:1px 0 1px 4mm; }
.fastbox { border:2px solid #ee0000; background:#fff2cc; text-align:center;
           font-style:italic; font-weight:bold; padding:4px 8px; margin:6px auto; width:88%; }
.week { padding:0 0 5px; }
/* House-style dividers between grid cells (vertical rule between columns,
   horizontal rule between grid rows). Gaps come from the cell padding. */
.page-cells.grid > .cell, .page-cells.two > .cell { padding:0 3mm 2mm 0; }
.page-cells.grid > .cell:nth-child(2n), .page-cells.two > .cell:nth-child(2n) {
  border-left:1px solid #000; padding:0 0 2mm 3mm; }
.page-cells.grid > .cell:nth-child(n+3) { border-top:1px solid #000; padding-top:2mm; }
.foot { border-top:1px solid #000; margin-top:6px; padding-top:4px;
        text-align:center; font-size:0.92em; }
.single { font-size:11pt; }
.single .hdr-title { font-size:18pt; }
.single .hdr-sub { font-size:12pt; }
.multi { font-size:8.5pt; }
.multi .hdr-title { font-size:17pt; }
.multi .hdr-sub { font-size:11.5pt; text-align:left; }
.multi .row { margin:0.3px 0; }
.multi .barwrap { margin:3px 0 1px; }
.multi .subtitle { margin-bottom:3px; }
.multi .subhead { margin:2px 0 0; }
.multi .fastbox { width:96%; padding:3px 6px; margin:4px auto; }
"""


def render_html(doc_data: dict) -> str:
    from .page_layout import FIT_JS, page_css, paginate, pages_html
    from .render_docx import _group_blocks
    groups = _group_blocks(doc_data["blocks"])
    n_cells = sum(1 + len(g["days"]) for g in groups)
    multi = n_cells > 1  # multiple blocks share pages (grid/columns)

    # Hoist notes common to every week to a single last-page footer.
    shared_notes: list[str] = []
    if len(groups) > 1:
        common = set.intersection(*(set(g["week"]["notes"]) for g in groups))
        shared_notes = [n for n in groups[0]["week"]["notes"] if n in common]
        for g in groups:
            g["week"] = dict(g["week"],
                             notes=[n for n in g["week"]["notes"] if n not in common])

    cells: list[str] = []
    for g in groups:
        cells.append(_week_cell_html(g["week"], notes_inline=multi))
        for day in g["days"]:
            cells.append(_day_cell_html(day))

    # One header for every layout; name and location are single lines by
    # contract (.fit-line + nowrap — the fit script shrinks them to fit).
    header = (
        '<div class="hdr-row"><span class="bsd">בס״ד</span>'
        '<div class="hdr-title fit-line">Tzemach Tzedek Community Centre'
        '<span class="url">www.ttcc.org.au</span></div></div>'
        '<div class="hdr-sub fit-line">Location: 1 Penkivil St, Bondi, NSW.&nbsp;&nbsp;'
        'Mailing address: PO Box 477 Waverley NSW 2024</div>')
    chrome = header + '<hr class="rule">'

    if multi:
        foot = "".join(f'<div class="foot"><b>Note:</b> {_esc(n)}</div>' for n in shared_notes)
    else:  # single week: notes render as the page footer, not inline
        foot = "".join(f'<div class="foot">{_esc(n)}</div>'
                       for g in groups for n in g["week"].get("notes", []))

    body = pages_html(paginate(cells), chrome=chrome, foot=foot)
    return (f'<!doctype html><html><head><meta charset="utf-8">'
            f'<style>{page_css(12)}{_CSS}</style></head>'
            f'<body class="sheet">{body}{FIT_JS}</body></html>')


def save_html(doc_data: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_html(doc_data))
