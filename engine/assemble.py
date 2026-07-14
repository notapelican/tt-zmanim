"""Block assembly (warplan module 4, data half): combine zmanim + luach +
schedule rules into the final sheet content as PLAIN DATA.

`generate(start, end)` returns a JSON-serializable dict of week blocks (and
day blocks for yom tov / fast days in range) whose shape mirrors the fixture
JSON: typed lines with label / kind / day_spec / time / qualifier / section,
plus luach-triggered notes. No layout, no styling, no docx — the renderer
contract for this structure is RENDERER-CONTRACT.md.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from . import luach
from .hebcal import to_hebrew
from .rules import (DEFAULT_NOTES, DEFAULT_PROFILES, EREV_SHABBOS,
                    EREV_SHABBOS_EARLY, SHABBOS_DAY, WEEKDAY, WeekContext,
                    active_profiles, apply_overrides, davening_lines)
from .zmanim import ZmanimEngine

# Printed section headings for the rule-section keys (renderer may restyle).
SECTION_TITLES = {
    WEEKDAY: "Davening times during the week",
    EREV_SHABBOS: "Erev Shabbos candle lighting and davening",
    EREV_SHABBOS_EARLY: "Erev Shabbos early minyan (and essential halachic details)",
    SHABBOS_DAY: "Shabbos Day and Motzaei Shabbos",
}
KEY_TIMES = "Erev Shabbos key times"

# Days on which melacha is prohibited (full yom tov); these leave the weekday
# davening lines and get their own day blocks.
_YOM_TOV = {"Rosh Hashana Day 1", "Rosh Hashana Day 2", "Yom Kippur",
            "Succos day 1", "Succos day 2", "Shemini Atzeres", "Simchas Torah",
            "Pesach day 1", "Pesach day 2", "Shevi'i Shel Pesach",
            "Acharon Shel Pesach", "Shavuos day 1", "Shavuos day 2"}

_WD_ABBR = ["Mon.", "Tues.", "Wed.", "Thurs.", "Fri.", "Shabbos", "Sun."]
_YOM_NAMES = ["yom sheini", "yom shlishi", "yom revi'i", "yom chamishi",
              "erev Shabbos", "Shabbos kodesh", "yom rishon"]


def _fmt(dt: datetime) -> str:
    return f"{dt.hour:02d}:{dt.minute:02d}"


def _is_yom_tov(d: date) -> bool:
    return any(l in _YOM_TOV for l in luach.day_labels(d))


def format_day_spec(days: list[date]) -> str | None:
    """'Sun.', 'Mon.–Fri.', 'Sun. & Mon.', 'Mon., Wed.–Fri.' from a date list
    (all within one week, ordered)."""
    if not days:
        return None
    # Sheet order: Sunday first.
    order = sorted(days, key=lambda d: (d.weekday() + 1) % 7)
    runs: list[list[date]] = [[order[0]]]
    for d in order[1:]:
        if (d - runs[-1][-1]).days == 1:
            runs[-1].append(d)
        else:
            runs.append([d])
    parts = []
    for run in runs:
        a, b = _WD_ABBR[run[0].weekday()], _WD_ABBR[run[-1].weekday()]
        if len(run) == 1:
            parts.append(a)
        elif len(run) == 2:
            parts.append(f"{a} & {b}")
        else:
            parts.append(f"{a}–{b}")
    return ", ".join(parts)


def _zman_line(label: str, time_s: str, section: str | None, *, kind: str = "zman",
               day_spec: str | None = None, qualifier: str | None = None,
               date_iso: str | None = None, rule_id: str | None = None,
               source: str = "zmanim") -> dict:
    return {"rule_id": rule_id, "section": section, "label": label, "kind": kind,
            "day_spec": day_spec, "date": date_iso, "time": time_s,
            "qualifier": qualifier, "source": source}


def molad_text(shabbos: date) -> str | None:
    ann = luach.rosh_chodesh_announcement(shabbos)
    if ann is None:
        return None
    m = ann["molad"]
    wd_names = ["Sun.", "Mon.", "Tues.", "Wed.", "Thurs.", "Fri.", "Shabbos"]
    rc = " and ".join(_YOM_NAMES[d.weekday()] for d in ann["rosh_chodesh_days"])
    return (f"Molad for {ann['month']}: {wd_names[m['weekday']]} "
            f"{m['hour']}:{m['minute']:02d}{m['ampm']} and {m['chalakim']} chalakim, "
            f"Jerusalem Standard Time.  Rosh Chodesh {ann['month']}: {rc}.")


def _dst_on(d: date, engine: ZmanimEngine) -> bool:
    return datetime(d.year, d.month, d.day, 12,
                    tzinfo=engine.loc.tz).dst() != timedelta(0)


def week_notes(sunday: date, shabbos: date, engine: ZmanimEngine,
               notes=DEFAULT_NOTES) -> list[str]:
    out = []
    trans = luach.dst_transition(sunday, shabbos + timedelta(days=1), engine.loc.tz)
    dst = _dst_on(shabbos, engine)
    for n in notes:
        if n.trigger == "dst" and dst:
            out.append(n.text)
        elif n.trigger == "standard_time" and not dst:
            out.append(n.text)
        elif n.trigger == "dst_change_week" and trans:
            direction = "begins" if _dst_on(trans, engine) else "ends"
            out.append(n.text.format(
                dst_date=f"{_WD_ABBR[trans.weekday()]} {trans.day} {trans:%b}",
                dst_direction=direction))
    hols = luach.nsw_public_holidays(sunday.year) | luach.nsw_public_holidays(shabbos.year)
    for i in range(7):
        d = sunday + timedelta(days=i)
        if d in hols and d.weekday() < 5:  # Mon-Fri public holiday
            out.append(f"{_WD_ABBR[d.weekday()]} {d.day} {d:%b} is a public holiday "
                       f"({hols[d]}): Shacharis follows the Sunday schedule.")
    return out


def _fast_entries(sunday: date, shabbos: date, engine: ZmanimEngine) -> list[dict]:
    """Fast-box entries for fasts falling in the week (start/end pairs)."""
    out = []
    hy = to_hebrew(shabbos).year
    for year in (hy, hy - 1, hy + 1):
        for f in luach.fasts(year):
            d = f["date"]
            if not sunday <= d <= shabbos or f["name"] == "Yom Kippur":
                continue
            sec = f["name"] if f["name"].startswith("Fast") else f"Fast of {f['name']}"
            # 9 Av starts the previous evening at shkia; dawn fasts start at
            # alos (floor: never start late). Both end at the 6-degree tzeis
            # (corpus: 5786 9 Av ends 5:37pm = tzeis 6 deg); only Yom Kippur
            # ends at the stricter 8.4-degree Shabbos-style tzeis, and YK is
            # handled on its yom tov sheet, not here.
            if f["kind"] == "night":
                start_d = d - timedelta(days=1)
                start = engine.shkia(start_d, "floor")
            else:
                start_d = d
                start = engine.alos(d, "floor")
            end = engine.tzeis(d, "ceil")
            out.append(_zman_line("Fast start", _fmt(start), sec, kind="fast",
                                  date_iso=start_d.isoformat(),
                                  day_spec=_WD_ABBR[start_d.weekday()]))
            out.append(_zman_line("Fast end", _fmt(end), sec, kind="fast",
                                  date_iso=d.isoformat(),
                                  day_spec=_WD_ABBR[d.weekday()]))
    return out


def build_week_context(sunday: date, engine: ZmanimEngine | None = None) -> WeekContext:
    engine = engine or ZmanimEngine()
    friday, shabbos = sunday + timedelta(days=5), sunday + timedelta(days=6)
    weekdays = tuple(sunday + timedelta(days=i) for i in range(5)
                     if not _is_yom_tov(sunday + timedelta(days=i)))
    return WeekContext(
        sunday=sunday,
        friday=None if _is_yom_tov(friday) else friday,
        shabbos=shabbos,
        weekdays=weekdays,
        mevorchim=luach.mevorchim_month(shabbos) is not None,
        engine=engine)


def scope_overrides(overrides: dict[str, dict] | None, block_key: str) -> dict[str, dict]:
    """Reduce a sheet-wide overrides dict to one block's overrides.

    Keys may be block-scoped as "<block_key>|<rule_id>" where block_key is
    "week:<civil_start ISO>" or "day:<date ISO>" (the same keys the plugin
    uses for note edits). Scoped keys apply only to their block, with the
    prefix stripped so apply_overrides sees plain rule_ids (including
    "add:<id>" insertions). Bare legacy keys apply to every block, which
    preserves the behaviour of overrides stored before scoping existed.
    """
    if not overrides:
        return {}
    out: dict[str, dict] = {}
    for key, ov in overrides.items():
        if "|" in key and key.split("|", 1)[0].startswith(("week:", "day:")):
            bk, rid = key.split("|", 1)
            if bk == block_key and rid:
                out[rid] = ov
        else:
            out[key] = ov
    return out


def assemble_week(sunday: date, *, engine: ZmanimEngine | None = None,
                  profiles=DEFAULT_PROFILES, notes=DEFAULT_NOTES,
                  overrides: dict[str, dict] | None = None) -> dict:
    """One week block (Sunday..Shabbos), fixture-shaped plain data."""
    engine = engine or ZmanimEngine()
    ctx = build_week_context(sunday, engine)
    friday, shabbos = sunday + timedelta(days=5), sunday + timedelta(days=6)
    week_days = [sunday + timedelta(days=i) for i in range(6)]      # Sun..Fri
    sun_thu = [d for d in week_days[:5] if not _is_yom_tov(d)]
    sun_fri = [d for d in week_days if not _is_yom_tov(d)]

    entries: list[dict] = []

    # --- weekly zmanim (day-selection rules per engine/validate.py) ---
    # Ranged lines print the safe extreme BY TIME OF DAY across the covered
    # days (same convention as rules.ZmanAnchored) — a bare max()/min() over
    # datetimes on different dates would always pick the last/first DAY, not
    # the latest/earliest clock time.
    tod = lambda dt: dt.time()
    if sun_fri:
        spec_sf = format_day_spec(sun_fri)
        entries.append(_zman_line(
            "Mi'sheyakir (earliest tallis & tefillin)",
            _fmt(max((engine.misheyakir(d, "ceil") for d in sun_fri), key=tod)),
            None, day_spec=spec_sf, qualifier="approx", rule_id="z_misheyakir"))
        entries.append(_zman_line(
            "Netz Hachamah (sunrise)",
            _fmt(max((engine.netz(d, "ceil") for d in sun_fri), key=tod)),
            None, day_spec=spec_sf, rule_id="z_netz"))
        entries.append(_zman_line(
            "Morning Shema",
            _fmt(min((engine.sof_zman_shema(d, "floor") for d in sun_fri), key=tod)),
            None, day_spec=spec_sf, qualifier="finish by", rule_id="z_shema_wk"))
    if sun_thu:
        spec_st = format_day_spec(sun_thu)
        entries.append(_zman_line(
            "Shkia", _fmt(min((engine.shkia(d, "floor") for d in sun_thu), key=tod)),
            None, day_spec=spec_st, rule_id="z_shkia_wk"))
        entries.append(_zman_line(
            "Tzeis", _fmt(max((engine.tzeis(d, "ceil") for d in sun_thu), key=tod)),
            None, day_spec=spec_st, rule_id="z_tzeis_wk"))

    # --- davening lines from the rules engine ---
    lines = davening_lines(ctx, profiles, overrides=None)  # overrides applied at end
    early_active = any(l["section"] == EREV_SHABBOS_EARLY for l in lines)

    # Public holidays: Mon-Fri holidays use the Sunday Shacharis schedule.
    hols = luach.nsw_public_holidays(sunday.year) | luach.nsw_public_holidays(shabbos.year)
    sunday_like = [sunday] + [d for d in week_days[1:] if d in hols and not _is_yom_tov(d)]
    plain_weekdays = [d for d in week_days[1:] if d not in sunday_like and not _is_yom_tov(d)]
    for l in lines:
        if l["rule_id"].startswith("shacharis_sun"):
            l["day_spec"] = format_day_spec(sunday_like)
        elif l["rule_id"].startswith("shacharis_wk"):
            l["day_spec"] = format_day_spec(plain_weekdays)
        elif l["section"] == WEEKDAY and l["day_spec"] == "Sun.–Thurs.":
            l["day_spec"] = format_day_spec(sun_thu)

    # Pirkei Avos / Seder Nigunim decoration on the Shabbos Mincha line.
    pa = luach.pirkei_avos(shabbos)
    for l in lines:
        if l["rule_id"] == "shab_mincha":
            if pa:
                chapters = " & ".join(str(c) for c in pa)
                l["label"] = f"Mincha, Pirkei Avos {chapters}, Seder Nigunim"
            else:
                l["label"] = "Mincha followed by Seder Nigunim"

    entries.extend(l for l in lines if l["section"] == WEEKDAY)
    if early_active:
        entries.extend(l for l in lines if l["section"] == EREV_SHABBOS_EARLY)

    # --- Erev Shabbos key times + candle lighting (pure zmanim) ---
    if ctx.friday is not None:
        entries.append(_zman_line("Plag Hamincha", _fmt(engine.plag_hamincha(friday, "ceil")),
                                  KEY_TIMES, date_iso=friday.isoformat(), rule_id="z_plag_fri"))
        entries.append(_zman_line("Shkia", _fmt(engine.shkia(friday, "floor")),
                                  KEY_TIMES, date_iso=friday.isoformat(), rule_id="z_shkia_fri"))
        entries.append(_zman_line("Tzeis hachochavim", _fmt(engine.tzeis(friday, "ceil")),
                                  KEY_TIMES, date_iso=friday.isoformat(), rule_id="z_tzeis_fri"))
        entries.append(_zman_line("Candle lighting", _fmt(engine.candle_lighting(friday)),
                                  SECTION_TITLES[EREV_SHABBOS], date_iso=friday.isoformat(),
                                  rule_id="z_candles_fri"))
    entries.extend(l for l in lines if l["section"] == EREV_SHABBOS)

    # --- Shabbos day ---
    entries.append(_zman_line("Morning Shema", _fmt(engine.sof_zman_shema(shabbos, "floor")),
                              SECTION_TITLES[SHABBOS_DAY], date_iso=shabbos.isoformat(),
                              qualifier="finish by", rule_id="z_shema_shab"))
    entries.extend(l for l in lines if l["section"] == SHABBOS_DAY)

    # --- fasts in the week ---
    entries.extend(_fast_entries(sunday, shabbos, engine))

    # Map rule-section keys to printed headings; regular ES section is renamed
    # when the early minyan runs.
    es_title = ("Erev Shabbos regular times: candle lighting and davening"
                if early_active else SECTION_TITLES[EREV_SHABBOS])
    for l in entries:
        if l["section"] in SECTION_TITLES:
            l["section"] = SECTION_TITLES[l["section"]]
        if l["section"] == SECTION_TITLES[EREV_SHABBOS]:
            l["section"] = es_title

    entries = apply_overrides(
        entries, scope_overrides(overrides, f"week:{sunday.isoformat()}"))

    parsha = luach.week_parsha(shabbos)
    block = {
        "type": "week",
        "title": f"The week of Parshas {parsha}:",
        "parsha": parsha,
        "shabbos_labels": luach.shabbos_labels(shabbos),
        "hebrew_dates": luach.hebrew_date_range(sunday, shabbos),
        "civil_start": sunday.isoformat(),
        "civil_end": shabbos.isoformat(),
        "friday": friday.isoformat(),
        "shabbos": shabbos.isoformat(),
        "active_profiles": [p.id for p in active_profiles(ctx, profiles)],
        "entries": entries,
        "molad": molad_text(shabbos),
        "notes": week_notes(sunday, shabbos, engine, notes),
    }
    return block


def assemble_day(d: date, *, engine: ZmanimEngine | None = None,
                 overrides: dict[str, dict] | None = None) -> dict:
    """Day block for a yom tov / erev yom tov day. Key zmanim lines are
    rule-derived; YT minyan times are the most override-edited lines in the
    corpus (see PHASE3-FINDINGS), so they are emitted as editable defaults."""
    engine = engine or ZmanimEngine()
    labels = luach.day_labels(d)
    h = to_hebrew(d)
    is_yt = _is_yom_tov(d)
    next_yt = _is_yom_tov(d + timedelta(days=1))
    next_shabbos = (d + timedelta(days=1)).weekday() == 5
    entries: list[dict] = []

    def add(label, dt, section=None, *, kind="zman", qualifier=None, rule_id=None):
        entries.append(_zman_line(label, _fmt(dt), section, kind=kind,
                                  qualifier=qualifier, date_iso=d.isoformat(),
                                  rule_id=rule_id,
                                  source="rule" if kind == "minyan" else "zmanim"))

    if is_yt:
        add("Shacharis", datetime(d.year, d.month, d.day, 10, 0), kind="minyan",
            rule_id="yt_shacharis")
        add("Mincha", engine.shkia(d, "floor") - timedelta(minutes=10),
            kind="minyan", rule_id="yt_mincha")
        if next_yt:
            add("Candle lighting", engine.tzeis_shabbos(d, "ceil"),
                qualifier="not before", rule_id="yt_candles_2nd")
            add("Maariv", engine.tzeis_shabbos(d, "ceil"), kind="minyan",
                rule_id="yt_maariv_2nd")
        elif next_shabbos:
            add("Candle lighting", engine.candle_lighting(d),
                rule_id="yt_candles_shabbos")
            add("Kabbolas Shabbos & Maariv", engine.tzeis(d, "ceil") - timedelta(minutes=10),
                kind="minyan", rule_id="yt_ks")
        else:
            add("Yom Tov ends; Maariv", engine.tzeis_shabbos(d, "ceil"),
                kind="minyan", rule_id="yt_ends")
    else:
        # erev yom tov (or an interleaved chol day on a yom tov sheet)
        if next_yt:
            add("Candle lighting", engine.candle_lighting(d), rule_id="erev_yt_candles")
            add("Mincha", engine.candle_lighting(d) + timedelta(minutes=8),
                kind="minyan", rule_id="erev_yt_mincha")
            add("Shkia", engine.shkia(d, "floor"), rule_id="erev_yt_shkia")
            add("Maariv (Yom Tov)", engine.tzeis(d, "ceil"), kind="minyan",
                rule_id="erev_yt_maariv")

    return apply_day_block(d, h, labels, entries, overrides)


def apply_day_block(d, h, labels, entries, overrides):
    return {
        "type": "day",
        "title": ", ".join(labels) or None,
        "weekday": _WD_ABBR[d.weekday()],
        "hebrew_date": f"{h.day} {h.month_name}",
        "date": d.isoformat(),
        "labels": labels,
        "omer_day": luach.omer_day(d),
        "entries": apply_overrides(
            entries, scope_overrides(overrides, f"day:{d.isoformat()}")),
        "notes": [],
    }


def generate(start: date, end: date, *, engine: ZmanimEngine | None = None,
             profiles=DEFAULT_PROFILES, notes=DEFAULT_NOTES,
             overrides: dict[str, dict] | None = None) -> dict:
    """Generate sheet content for [start, end] as plain data: one week block
    per Sunday..Shabbos week intersecting the range, plus day blocks for yom
    tov and erev yom tov days in range. `overrides` maps rule_id -> edit and
    always wins over rules (see rules.Timesheet)."""
    engine = engine or ZmanimEngine()
    blocks: list[dict] = []
    # first Sunday on/before start
    sunday = start - timedelta(days=(start.weekday() + 1) % 7)
    while sunday <= end:
        blocks.append(assemble_week(sunday, engine=engine, profiles=profiles,
                                    notes=notes, overrides=overrides))
        for i in range(7):
            d = sunday + timedelta(days=i)
            if start <= d <= end and (_is_yom_tov(d) or
                                      (_is_yom_tov(d + timedelta(days=1)) and not _is_yom_tov(d))):
                blocks.append(assemble_day(d, engine=engine, overrides=overrides))
        sunday += timedelta(days=7)
    return {"format": "weekly", "start": start.isoformat(), "end": end.isoformat(),
            "blocks": blocks}
