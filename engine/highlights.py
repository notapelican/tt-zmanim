"""Shabbos & Yom Tov highlights: the short public-facing data behind the
website banner widget and the piSignage "Shabbos screen".

Per week (Sunday..Shabbos) this extracts ONLY the headline times — candle
lighting, Shabbos / Yom Tov ends, fast begin/end — from the very same
assembled block data that drives the printed sheets (`assemble_week` /
`assemble_day`, including any overrides), so the public surfaces can never
disagree with the sheet. Nothing is recomputed or re-rounded here, with two
deliberate exceptions, both existing engine zmanim:

- "Shabbos ends" is `ZmanimEngine.tzeis_shabbos(shabbos, "nearest")` — the
  8.5-degree motzaei zman. The sheets carry this time only as the anchor of
  the `motzaei_maariv` rule (offset 0, same rounding), so it is the identical
  number; it just isn't printed as its own line there.
- Candle lighting for a Yom Tov that begins on Motzaei Shabbos is shown as
  "not before" `tzeis_shabbos(shabbos)` (from a pre-existing flame), the same
  convention the engine already applies to second-night candles
  (`yt_candles_2nd`). The erev-YT day block's before-shkia candle time is a
  weekday-erev convention and must never be displayed for a Saturday.
"""
from __future__ import annotations

from datetime import date, timedelta

from . import luach
from .assemble import _YOM_TOV, _is_yom_tov, assemble_day, assemble_week
from .rules import DEFAULT_NOTES, DEFAULT_PROFILES
from .zmanim import ZmanimEngine

_WD_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday"]

# rule_ids (stable per RENDERER-CONTRACT.md) that surface on the highlights.
_CANDLE_IDS = {"z_candles_fri", "erev_yt_candles", "yt_candles_2nd",
               "yt_candles_shabbos"}
_ENDS_IDS = {"yt_ends"}

_FAST_NAMES = {"Tzom Gedaliah", "Taanis Esther", "Taanis Bechorim"}


def _day_display(d: date) -> str:
    return f"{_WD_FULL[d.weekday()]}, {d.day} {d:%B}"


def _range_display(start: date, end: date) -> str:
    if start.year != end.year:
        return f"{start.day} {start:%b} {start.year} – {end.day} {end:%b} {end.year}"
    return f"{start.day} {start:%b} – {end.day} {end:%b} {end.year}"


def _item(kind: str, label: str, d: date, time_s: str, *,
          memo: str | None = None, qualifier: str | None = None) -> dict:
    return {"kind": kind, "label": label, "memo": memo,
            "date": d.isoformat(), "weekday": _WD_FULL[d.weekday()],
            "day_display": _day_display(d), "time": time_s,
            "qualifier": qualifier}


def _chip_kind(text: str) -> str:
    if text.startswith("Fast") or text in _FAST_NAMES:
        return "fast"
    if text in _YOM_TOV:
        return "yomtov"
    return "minor"


def _fmt(dt) -> str:
    return f"{dt.hour:02d}:{dt.minute:02d}"


def week_highlights(sunday: date, *, engine: ZmanimEngine | None = None,
                    profiles=DEFAULT_PROFILES, notes=DEFAULT_NOTES,
                    overrides: dict[str, dict] | None = None) -> dict:
    """Highlights for the week of `sunday` (must be a Sunday)."""
    engine = engine or ZmanimEngine()
    shabbos = sunday + timedelta(days=6)
    week = assemble_week(sunday, engine=engine, profiles=profiles,
                         notes=notes, overrides=overrides)

    day_blocks = []
    for i in range(7):
        d = sunday + timedelta(days=i)
        if _is_yom_tov(d) or (_is_yom_tov(d + timedelta(days=1)) and not _is_yom_tov(d)):
            day_blocks.append((d, assemble_day(d, engine=engine, overrides=overrides)))

    items: list[dict] = []
    candle_dates: set[str] = set()

    # --- day-block candle / ends lines (yom tov weeks) ---
    for d, block in day_blocks:
        title = block.get("title")
        for e in block.get("entries", []):
            rid = e.get("rule_id")
            if rid in _CANDLE_IDS:
                time_s, qual, memo = e["time"], e.get("qualifier"), title
                if rid == "erev_yt_candles" and d.weekday() == 5:
                    # Yom Tov beginning on Motzaei Shabbos: candles only after
                    # Shabbos ends, from a pre-existing flame (see module doc).
                    time_s = _fmt(engine.tzeis_shabbos(d, "nearest"))
                    qual = "not before"
                if qual == "not before":
                    memo = (f"{title} — from a pre-existing flame"
                            if title else "From a pre-existing flame")
                items.append(_item("candles", "Candle lighting", d, time_s,
                                   memo=memo, qualifier=qual))
                candle_dates.add(d.isoformat())
            elif rid in _ENDS_IDS:
                label = ("Shabbos & Yom Tov end" if d.weekday() == 5
                         else "Yom Tov ends")
                items.append(_item("ends", label, d, e["time"], memo=title))

    # --- regular Friday candle lighting (from the week block) ---
    for e in week["entries"]:
        if e.get("rule_id") == "z_candles_fri" and e.get("date") \
                and e["date"] not in candle_dates:
            d = date.fromisoformat(e["date"])
            items.append(_item("candles", "Candle lighting", d, e["time"],
                               qualifier=e.get("qualifier")))
            candle_dates.add(e["date"])

    # --- Shabbos ends (skip when Shabbos itself is Yom Tov — the day block
    #     already carries the ends / second-night line) ---
    if not _is_yom_tov(shabbos):
        if _is_yom_tov(shabbos + timedelta(days=1)):
            pass  # flows into Yom Tov; the "not before" candles row covers it
        else:
            items.append(_item("ends", "Shabbos ends", shabbos,
                               _fmt(engine.tzeis_shabbos(shabbos, "nearest"))))

    # --- fasts (start/end pairs already assembled on the week block) ---
    for e in week["entries"]:
        if e.get("kind") == "fast" and e.get("date"):
            d = date.fromisoformat(e["date"])
            begins = e.get("label", "").lower().startswith("fast start")
            items.append(_item("fast_begins" if begins else "fast_ends",
                               "Fast begins" if begins else "Fast ends",
                               d, e["time"], memo=e.get("section")))

    items.sort(key=lambda i: (i["date"], i["time"]))

    # --- chips: labels for every day of the week, collapsed and deduped ---
    chips: list[dict] = []
    seen: set[str] = set()

    def add_chip(text: str, kind: str | None = None):
        if text.startswith("Chanukah day"):
            text = "Chanukah"
        if text and text not in seen:
            seen.add(text)
            chips.append({"text": text, "kind": kind or _chip_kind(text)})

    for lbl in week.get("shabbos_labels", []):
        add_chip("Shabbos Mevorchim" if lbl == "Mevorchim" else lbl, "minor")
    for i in range(7):
        for lbl in luach.day_labels(sunday + timedelta(days=i)):
            if lbl != "Erev Yom Tov":
                add_chip(lbl)

    parsha = week.get("parsha")
    if parsha:
        title = f"Parshas {parsha}"
    else:
        yt = [c["text"] for c in chips if c["kind"] == "yomtov"]
        title = yt[0] if yt else "Shabbos times"

    return {
        "type": "highlights",
        "civil_start": week["civil_start"],
        "civil_end": week["civil_end"],
        "friday": week["friday"],
        "shabbos": week["shabbos"],
        "parsha": parsha,
        "title": title,
        "hebrew_dates": week["hebrew_dates"],
        "range_display": _range_display(sunday, shabbos),
        "chips": chips,
        "items": items,
    }


def highlights(start: date, end: date, *, engine: ZmanimEngine | None = None,
               profiles=DEFAULT_PROFILES, notes=DEFAULT_NOTES,
               overrides: dict[str, dict] | None = None) -> dict:
    """Highlights for every Sunday..Shabbos week intersecting [start, end]
    (same week-selection rule as `assemble.generate`)."""
    engine = engine or ZmanimEngine()
    weeks: list[dict] = []
    sunday = start - timedelta(days=(start.weekday() + 1) % 7)
    while sunday <= end:
        weeks.append(week_highlights(sunday, engine=engine, profiles=profiles,
                                     notes=notes, overrides=overrides))
        sunday += timedelta(days=7)
    return {"format": "highlights", "start": start.isoformat(),
            "end": end.isoformat(), "weeks": weeks}
