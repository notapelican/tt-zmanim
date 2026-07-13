"""WhatsApp broadcast message from the sheet's block data.

A compact, essential-times-only text rendering (WhatsApp markdown: ``*bold*``
plus emoji) of the *same* block data produced by ``engine.assemble.generate``.
It reuses the engine's content functions (``week_items`` / ``day_items`` and
``_group_blocks``), so every time and label is byte-identical to the printed
sheet — this module only selects the essentials and formats them. The engine is
never modified and no time is recomputed.

"Essential" = the davening/minyan times people actually need in a broadcast:
weekday Shacharis/Mincha/Maariv, Erev Shabbos candle lighting + davening, and
Shabbos-day davening. The astronomical zmanim (Mi'sheyakir, Netz, Shema, Shkia,
Tzeis, Plag) — the "Erev Shabbos key times" block, and the Shabbos-morning
Shema — are dropped. Notes carry through.

Selection-aware: a range spanning several weeks and/or yom-tov day blocks
becomes one message (each week/day as its own section, divided by a rule).
"""
from __future__ import annotations

from datetime import date as _date
from datetime import timedelta as _td

from engine.render_docx import (
    KEY_TIMES,
    SHABBOS_DAY,
    WEEKDAY,
    _fmt_civil_date,
    _fmt_civil_range,
    _group_blocks,
)
from engine.render_html import day_items, week_items

SHORT_NAME = "Tzemach Tzedek"

# label keyword (lowercase, first match wins) -> emoji
_EMOJI = (
    ("candle", "🕯️🕯️"),
    ("kabbol", "🎶"),
    ("kabbal", "🎶"),
    ("chassidus", "📜"),
    ("tehillim", "📜"),
    ("halacha", "📖"),
    ("shacharis", "🌅"),
    ("mincha", "🌇"),
    ("motzaei", "🌃"),
    ("maariv", "🌃"),
)


def _emoji(label: str) -> str:
    low = label.lower()
    for key, em in _EMOJI:
        if key in low:
            return em
    return "🕰️"


def _skip_line(label: str) -> bool:
    # The Shabbos-morning Shema is a zman, not a minyan — omit from the broadcast.
    return "shema" in label.lower()


def _week_message(block: dict) -> str:
    items = week_items(block, notes_inline=False)
    parsha = block.get("parsha", "")
    labels = block.get("shabbos_labels", []) or []
    civ = _fmt_civil_range(block["civil_start"], block["civil_end"])
    head_bits = ([f"Parshas {parsha}"] if parsha else []) + list(labels)
    head = ", ".join(head_bits) if head_bits else "This week"

    weekday: list[tuple[str, str]] = []
    erev: list[tuple[str, str]] = []
    shab: list[tuple[str, str]] = []
    fasts: list[str] = []
    cat = None
    for it in items:
        kind = it[0]
        if kind in ("zman", "molad", "title", "subtitle"):
            continue
        if kind == "fastbox":
            fasts.append(it[1])
            continue
        if kind == "note":
            continue  # rendered from block["notes"] below
        if kind == "bar":
            text, color = it[1], it[2]
            if color == "purple":
                cat = "skip"           # 'Shabbos kodesh' divider (no lines of its own)
            elif text == WEEKDAY:
                cat = "weekday"
            elif text == SHABBOS_DAY:
                cat = "shab"
            else:
                cat = "erev"           # candle lighting / early minyan sections
            continue
        if kind == "subhead":
            if it[1] == KEY_TIMES:
                cat = "skip"           # drop Plag/Shkia/Tzeis
            continue
        if kind == "line":
            lbl, val = it[1], it[2]
            if _skip_line(lbl):
                continue
            if cat == "weekday":
                weekday.append((lbl, val))
            elif cat == "erev":
                erev.append((lbl, val))
            elif cat == "shab":
                shab.append((lbl, val))

    out: list[str] = [f"*🕍 {SHORT_NAME} – {head} ({civ})*", ""]

    for lbl, val in weekday:
        out.append(f"*{_emoji(lbl)} {lbl.rstrip(':')}:*")
        out.extend(val.split("; "))

    for f in fasts:
        out.append("")
        out.append(f"⚠️ {f}")

    if erev:
        friday = _date.fromisoformat(block["civil_start"]) + _td(days=5)
        out.append("")
        out.append(f"*Erev Shabbos (Fri {_fmt_civil_date(friday.isoformat())})*")
        for lbl, val in erev:
            out.append(f"{_emoji(lbl)} {lbl} {val}")

    if shab:
        out.append("")
        out.append("*🕍 Shabbos Day*")
        for lbl, val in shab:
            out.append(f"{_emoji(lbl)} {lbl} {val}")

    for n in block.get("notes", []):
        out.append("")
        out.append(f"*Note:* {n}")

    return "\n".join(out)


def _day_message(day: dict) -> str:
    items = day_items(day)
    heading = items[0][1] if items and items[0][0] == "bar" else (day.get("title") or "")
    out = [f"*🕍 {heading}*"]
    for it in items[1:]:
        if it[0] == "line":
            lbl, val = it[1], it[2]
            if _skip_line(lbl):
                continue
            out.append(f"{_emoji(lbl)} {lbl} {val}")
        elif it[0] == "note":
            out.append(f"*Note:* {it[1]}")
    return "\n".join(out)


def render_whatsapp(doc_data: dict) -> str:
    """Build the WhatsApp broadcast text for the whole selection (one message)."""
    groups = _group_blocks(doc_data["blocks"])
    parts: list[str] = []
    for g in groups:
        parts.append(_week_message(g["week"]))
        for day in g.get("days", []):
            parts.append(_day_message(day))
    return "\n\n———\n\n".join(parts)
