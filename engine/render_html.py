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
                          SELICHOS_SUBHEAD, _SHABBOS_DAY_RULE_PRIORITY,
                          _SHABBOS_SHACHARIS_RULES, WEEKDAY, _fast_box_text,
                          selichos_pivot,
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
        # A Yom Tov Shabbos is named by the Yom Tov, not the parsha (`.get`:
        # sheets archived before the field existed fall back to the parsha).
        lead = block.get("shabbos_yom_tov") or [block["parsha"]]
        labels = ", ".join(lead + block["shabbos_labels"])
        items.append(("bar", f"Shabbos kodesh: {labels}", "purple"))
        shabbos_done = True

    for section in named_order:
        ents = named[section]
        if section == WEEKDAY:
            items.append(("bar", section, "blue"))
            pivot_rows, ents = selichos_pivot(ents)
            if pivot_rows:
                items.append(("subhead", SELICHOS_SUBHEAD))
                for day_label, value in pivot_rows:
                    items.append(("line", day_label, value, False))
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
        if e["rule_id"] in _SHABBOS_SHACHARIS_RULES:
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


# --- Tishrei (flow) composition ---------------------------------------------
#
# The one-page Tishrei sheet is navigated by DAY, not by week: every header
# names the day or day-run it covers, stamped with its Hebrew and civil dates,
# and Tishrei-specific names outrank the regular section headings ("Shabbos
# Kodesh: Ha'azinu, Shuva: 8 Tishrei (19 Sept.)" rather than a generic
# "Shabbos Day and Motzaei Shabbos"). The week's astronomical zmanim move out
# of the line flow into a bordered "General times for the week" box, so the
# minyanim read uninterrupted. This is a re-presentation of week_items'
# stream — content and order come from there, so every line stays identical
# to the weekly sheets'; only headers and grouping change.

def _tishrei_chol_header(week: dict) -> str | None:
    """'3–7 Tishrei (Mon.–Fri. 14–18 Sept.)' — the run of chol days the
    weekday davening section actually covers (its own day_specs)."""
    from datetime import date as _d, timedelta as _t
    from .assemble import SECTION_TITLES, _SUN_FIRST_ABBR, expand_day_spec
    from .hebcal import to_hebrew
    from .rules import WEEKDAY
    title = SECTION_TITLES[WEEKDAY]
    idxs = sorted({_SUN_FIRST_ABBR.index(day)
                   for e in week["entries"] if e.get("section") == title
                   for day in expand_day_spec(e.get("day_spec"))})
    if not idxs:
        return None
    sunday = _d.fromisoformat(week["civil_start"])
    d1, d2 = sunday + _t(days=idxs[0]), sunday + _t(days=idxs[-1])
    h1, h2 = to_hebrew(d1), to_hebrew(d2)
    if (h1.year, h1.month) == (h2.year, h2.month):
        heb = f"{h1.day} {h1.month_name}" if h1.day == h2.day else f"{h1.day}–{h2.day} {h1.month_name}"
    else:
        heb = f"{h1.day} {h1.month_name} – {h2.day} {h2.month_name}"
    wd = (_SUN_FIRST_ABBR[idxs[0]] if idxs[0] == idxs[-1]
          else f"{_SUN_FIRST_ABBR[idxs[0]]}–{_SUN_FIRST_ABBR[idxs[-1]]}")
    civ = (_fmt_civil_date(d1.isoformat()) if d1 == d2
           else _fmt_civil_range(d1.isoformat(), d2.isoformat()))
    return f"{heb} ({wd} {civ})"


def _tishrei_es_header(week: dict, es_bar_text: str) -> str:
    """'Erev Shabbos & Rosh Hashana: 29 Elul (Fri. 11 Sept.)' — the section
    bar's own name (which already carries a coinciding Yom Tov), date-stamped,
    prefixed with the Friday's specific day name (e.g. Hoshana Rabbah) when it
    has one. A calendar-label lookup, not a time computation."""
    from datetime import date as _d
    from . import luach
    from .hebcal import to_hebrew
    base = es_bar_text
    for suffix in (" candle lighting & davening", " candle lighting and davening"):
        base = base.replace(suffix, "")
    base = base.replace(" regular times:", "")
    friday = week.get("friday")
    if not friday:
        return base
    d = _d.fromisoformat(friday)
    h = to_hebrew(d)
    generic = {"Erev Yom Tov", "Erev Shabbos"}
    # Drop a label the header already carries: "Erev Succos" adds nothing to
    # "Erev Shabbos & Succos" (the base names the Yom Tov the evening brings in).
    extra = [l for l in luach.day_labels(d)
             if l not in generic and l not in base
             and l.replace("Erev ", "") not in base]
    if extra:
        base = f"{', '.join(extra)}, {base}"
    return f"{base}: {h.day} {h.month_name} (Fri. {_fmt_civil_date(friday)})"


def _tishrei_shabbos_header(week: dict) -> str:
    """'Shabbos Kodesh: Ha'azinu, Shuva: 8 Tishrei (19 Sept.)' — special
    Shabbos names lead, then the parsha."""
    from datetime import date as _d
    from .hebcal import to_hebrew
    names = (week.get("shabbos_yom_tov")
             or (list(week.get("shabbos_labels") or []) + [week["parsha"]]))
    shabbos = week["shabbos"]
    h = to_hebrew(_d.fromisoformat(shabbos))
    return (f"Shabbos Kodesh: {', '.join(names)}: "
            f"{h.day} {h.month_name} ({_fmt_civil_date(shabbos)})")


def tishrei_week_items(group: dict) -> list[tuple]:
    """week_group_items re-headed for the one-page Tishrei sheet (see the
    section comment above). Same lines, same order — only the framing moves:
    the top zmanim into a ("genbox", header, [(lbl, val)…]) item, and the
    generic week/section headings into date-stamped day headers."""
    from .render_docx import EARLY_ES
    week = group["week"]
    items = week_group_items(group, notes_inline=True)
    gen: list[tuple] = []
    out: list[tuple] = []
    es_done = False
    for it in items:
        kind = it[0]
        if kind in ("title", "subtitle"):
            continue                       # headers carry the dates instead
        if kind == "zman":
            gen.append((it[1], it[2]))
            continue
        if kind == "subhead" and it[1] == KEY_TIMES:
            # The key times open the Erev Shabbos block under ITS header.
            es_bar = next((i[1] for i in items if i[0] == "bar"
                           and i[1].startswith("Erev Shabbos") and i[1] != EARLY_ES),
                          "Erev Shabbos")
            out.append(("bar", _tishrei_es_header(week, es_bar), "blue"))
            es_done = True
            continue
        if kind == "bar":
            if it[1] == WEEKDAY:
                out.append(("bar", _tishrei_chol_header(week) or it[1], "blue"))
                continue
            if len(it) > 2 and it[2] == "purple" and it[1].startswith("Shabbos kodesh"):
                continue                   # replaced by the specific headers
            if it[1].startswith("Erev Shabbos") and it[1] != EARLY_ES:
                if es_done:
                    continue               # merged under the key-times header
                out.append(("bar", _tishrei_es_header(week, it[1]), "blue"))
                es_done = True
                continue
            if it[1] == SHABBOS_DAY:
                out.append(("bar", _tishrei_shabbos_header(week), "purple"))
                continue
        out.append(it)
    if gen:
        header = (f"General times for the week: {week['hebrew_dates']} "
                  f"({_fmt_civil_range(week['civil_start'], week['civil_end'])})")
        out.insert(0, ("genbox", header, gen))
    return out


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
    if kind == "genbox":
        lines = "".join(f'<div class="gb-l">{_esc(l)} {_esc(v)}</div>' for l, v in it[2])
        return f'<div class="genbox"><div class="gb-h">{_esc(it[1])}</div>{lines}</div>'
    if kind == "bar":
        return f'<div class="barwrap"><span class="bar {it[2]}">{_esc(it[1])}</span></div>'
    return ""


def week_group_items(group: dict, *, notes_inline: bool) -> list[tuple]:
    """A week's items with its yom-tov / chol-hamoed days folded in where they
    actually fall in the calendar.

    The days arrive from the engine as their own blocks, and appending them after
    the whole week put the Shabbos section — always the last day of the week —
    above a yom tov or chol hamoed that falls earlier in it. So the days that
    come before Shabbos go before the Shabbos bar, and a day that IS the Shabbos
    follows it: the Shabbos section opens with candle lighting and the erev
    Shabbos times, which belong to the Friday before.

    Shared by the classic and modern renderers so both read in the same order.
    """
    week = group["week"]
    items = week_items(week, notes_inline=notes_inline)
    days = sorted(group.get("days", []), key=lambda d: d.get("date", ""))
    if not days:
        return items

    # The purple bar opens the Shabbos section; ISO dates compare lexically.
    shabbos = week.get("civil_end", "")
    cut = len(items)
    for i, it in enumerate(items):
        if it[0] == "bar" and len(it) > 2 and it[2] == "purple":
            cut = i
            break

    out = list(items[:cut])
    for day in days:
        if day.get("date", "") < shabbos:
            out += day_items(day)
    out += items[cut:]
    for day in days:
        if day.get("date", "") >= shabbos:
            out += day_items(day)
    return out


def _week_cell_html(week: dict, *, notes_inline: bool) -> str:
    body = "".join(_item_html(it) for it in week_items(week, notes_inline=notes_inline))
    return f'<div class="week">{body}</div>'


def _week_group_cell_html(group: dict, *, notes_inline: bool) -> str:
    body = "".join(_item_html(it)
                   for it in week_group_items(group, notes_inline=notes_inline))
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
.genbox { border:1.5px solid #223; background:#eef2fa; padding:2px 8px 3px; margin:5px 0; }
.genbox .gb-h { font-weight:bold; font-style:italic; }
.genbox .gb-l { font-style:italic; }
.flow-title { text-align:center; font-weight:bold; font-size:13.5pt; margin:0 0 3px; }
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
/* On a single-week sheet the marker sat at full body size, which read as loud
   next to the 18pt masthead; half size matches the printed sheets. A Settings
   בס״ד size still wins — the service injects it after this stylesheet. */
.single .bsd { font-size:0.5em; }
.multi { font-size:8.5pt; }
.multi .hdr-title { font-size:17pt; }
.multi .hdr-sub { font-size:11.5pt; text-align:left; }
.multi .row { margin:0.3px 0; }
.multi .barwrap { margin:3px 0 1px; }
.multi .subtitle { margin-bottom:3px; }
.multi .subhead { margin:2px 0 0; }
.multi .fastbox { width:96%; padding:3px 6px; margin:4px auto; }
"""


def render_html(doc_data: dict, *, page_layout: str | None = None) -> str:
    """``page_layout="flow"`` puts every block on ONE page as two newspaper
    columns with a vertical rule — the Tishrei-sheet layout. Anything else
    uses the standard week-count pagination (see page_layout.paginate)."""
    from .page_layout import FIT_JS, page_css, paginate, pages_html
    from .render_docx import _group_blocks
    groups = _group_blocks(doc_data["blocks"])
    flow = page_layout == "flow"
    # flow uses the compact multi styles too: a whole-Tishrei page is dense.
    multi = flow or len(groups) > 1  # several weeks share pages (grid/columns)

    # Hoist notes common to every week to a single last-page footer.
    shared_notes: list[str] = []
    if len(groups) > 1:
        common = set.intersection(*(set(g["week"]["notes"]) for g in groups))
        shared_notes = [n for n in groups[0]["week"]["notes"] if n in common]
        for g in groups:
            g["week"] = dict(g["week"],
                             notes=[n for n in g["week"]["notes"] if n not in common])

    # One cell per week, its yom-tov days folded in at their calendar position.
    # That is also what keeps a lone week on one page in one column: it is a
    # single cell however much Tishrei it carries.
    if flow:
        # Day-headed Tishrei composition (see tishrei_week_items).
        cells: list[str] = ['<div class="week">'
                            + "".join(_item_html(it) for it in tishrei_week_items(g))
                            + '</div>' for g in groups]
    else:
        cells = [_week_group_cell_html(g, notes_inline=multi) for g in groups]

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

    if flow:
        # Name the sheet by the Hebrew month most of the range sits in.
        from datetime import date as _d
        from .hebcal import to_hebrew
        a, b = _d.fromisoformat(doc_data["start"]), _d.fromisoformat(doc_data["end"])
        h = to_hebrew(a + (b - a) / 2)
        civ = str(a.year) if a.year == b.year else f"{a.year}\u2013{b.year}"
        chrome += (f'<div class="flow-title">Times for {h.month_name} {h.year} '
                   f'({civ})</div>')
    pages = [("flow", cells)] if flow else paginate(cells)
    body = pages_html(pages, chrome=chrome, foot=foot)
    return (f'<!doctype html><html><head><meta charset="utf-8">'
            f'<style>{page_css(12)}{_CSS}</style></head>'
            f'<body class="sheet">{body}{FIT_JS}</body></html>')


def save_html(doc_data: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_html(doc_data))
