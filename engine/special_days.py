"""Special-day rules, phase 1 (weekly-sheet impact only).

Implements the first tranche of the mined rule catalog
(phase0/mining/SPECIAL-DAYS-CATALOG.md), pending shul review — every emitted
line carries an ``sd_*`` rule_id and every note is a plain note, so each one
is editable/removable per sheet through the normal overrides:

  1c  fast-day Mincha pulled earlier (shkia - 25, floored to 5 min)
  1d  nidche fasts inherit the split automatically (fast date = Sunday)
  1e  10 Teves falling on Erev Shabbos: explanatory notes
  2   9 Av set: Kinos Shacharis (8:00 & 9:30), Mincha Gedola + afternoon
      Mincha on the fast, erev-fast early Mincha, "Eicha & Kinos" decoration
      on the Maariv line, break-fast refreshments note
  8a  Elul customs notes (L'David from Rosh Chodesh, shofar + 3 Tehillim
      from 1 Elul, phrased by weekday)
  12b V'sein Tal U'Matar start note (4/5 December)
  12e Nittel note (24 December night)
  12i mid-week Rosh Chodesh span note

Times are zmanim-anchored per the catalog evidence; wording follows the
printed sheets. Layout/data only — never re-rounds an existing time.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from engine import luach
from engine.hebcal import from_hebrew, month_number, to_hebrew
from engine.rules import WEEKDAY
from engine.zmanim import ZmanimEngine

_WD = ["Mon.", "Tues.", "Wed.", "Thurs.", "Fri.", "Shabbos", "Sun."]


def _fmt(dt: datetime) -> str:
    """Entry storage format (24h HH:MM, same as assemble._fmt)."""
    return f"{dt.hour:02d}:{dt.minute:02d}"


def _floor5(dt: datetime) -> datetime:
    return dt.replace(minute=dt.minute - dt.minute % 5, second=0, microsecond=0)


def _round5(dt: datetime) -> datetime:
    """Round to the nearest 5 minutes (the sheets' minyan-time convention)."""
    dt = dt.replace(second=0, microsecond=0)
    rem = dt.minute % 5
    return dt + timedelta(minutes=(5 - rem) if rem >= 3 else -rem)


def _line(label, time_s, *, day_spec=None, date_iso=None, rule_id=None,
          section=WEEKDAY, kind="minyan"):
    return {"rule_id": rule_id, "section": section, "label": label,
            "kind": kind, "day_spec": day_spec, "date": date_iso,
            "time": time_s, "qualifier": None, "source": "special_day"}


def _fasts_in(sunday: date, shabbos: date) -> list[dict]:
    hy = to_hebrew(shabbos).year
    out = []
    for year in (hy, hy - 1, hy + 1):
        for f in luach.fasts(year):
            if sunday <= f["date"] <= shabbos:
                out.append(f)
    return out


def _insert_after(entries: list, idx: int, new: list[dict]) -> None:
    for off, e in enumerate(new, 1):
        entries.insert(idx + off, e)


def _find(entries: list, rule_id: str) -> int | None:
    for i, e in enumerate(entries):
        if e.get("rule_id") == rule_id:
            return i
    return None


def _exclude_days(entries: list, idx: int, excl: set[date],
                  week_days: list[date]) -> None:
    """Remove the given days from an entry's day_spec, recomputed from the
    standard uniform span it started as (Sun.-Thurs. / Mon.-Fri.). All
    exclusions for one entry must arrive in a single call."""
    from engine.assemble import format_day_spec, _is_yom_tov
    e = entries[idx]
    spec = e.get("day_spec") or ""
    if spec.startswith("Sun"):
        days = [x for x in week_days[:5] if not _is_yom_tov(x)]
    else:
        days = [x for x in week_days[1:6] if not _is_yom_tov(x)]
    e["day_spec"] = format_day_spec([x for x in days if x not in excl])


# --- rule groups ------------------------------------------------------------

def _minor_fast_mincha(entries, notes, sunday, shabbos, engine, week_days):
    """Rules 1c/1d/1e: fast-day Mincha (and the 10-Teves-on-Friday notes)."""
    for f in _fasts_in(sunday, shabbos):
        if f["kind"] != "dawn" or f["name"] == "Taanis Bechorim":
            continue
        d = f["date"]
        if d.weekday() == 4:  # Erev Shabbos fast (only 10 Teves can) - rule 1e
            notes.append(
                "No early minyanim for Erev Shabbos. (Due to the Fast not "
                "finishing until Tzeis Hachochavim, and other considerations, "
                "there is little benefit to bring in Shabbos early this week.)")
            notes.append(
                "Note that Mincha for Erev Shabbos today is earlier than usual "
                "and includes Kerias Hatorah, but no Tachanun or Avinu Malkenu.")
            continue
        if d.weekday() == 5:  # never happens post-nidche, defensive
            continue
        idx = _find(entries, "weekday_mincha")
        if idx is None:
            continue
        _exclude_days(entries, idx, {d}, week_days)
        t = _round5(engine.shkia(d, "nearest") - timedelta(minutes=25))
        _insert_after(entries, idx, [
            _line("Mincha", _fmt(t), day_spec=_WD[d.weekday()],
                  date_iso=d.isoformat(), rule_id="sd_fast_mincha"),
        ])


def _av9(entries, notes, sunday, shabbos, engine, week_days):
    """Rules 2e-2m (fast-day subset): Kinos Shacharis, Mincha Gedola +
    afternoon Mincha, erev-fast Mincha, Eicha decoration, refreshments."""
    fast = next((f for f in _fasts_in(sunday, shabbos) if f["kind"] == "night"), None)
    if fast is None:
        return
    d = fast["date"]
    erev = d - timedelta(days=1)
    wd = _WD[d.weekday()]

    # Shacharis 8:00 & 9:30 followed by Kinos (fixed; evidence 5782/5786).
    for rid in ("shacharis_wk_1", "shacharis_wk_2"):
        idx = _find(entries, rid)
        if idx is not None:
            _exclude_days(entries, idx, {d}, week_days)
    idx = _find(entries, "shacharis_wk_2")
    if idx is None:
        idx = _find(entries, "shacharis_sun_2")
    if idx is not None:
        _insert_after(entries, idx, [
            _line("Shacharis", "08:00", day_spec=wd, date_iso=d.isoformat(),
                  rule_id="sd_av9_shacharis_1"),
            _line("Shacharis", "09:30 followed by Kinos", day_spec=wd,
                  date_iso=d.isoformat(), rule_id="sd_av9_shacharis_2"),
        ])

    # Mincha: erev-fast early Mincha (weekday erev only, ahead of the seudah
    # hamafsekes), then on the fast a Mincha Gedola minyan + late-afternoon
    # Mincha (shkia - 30, evidence 5786 4:40pm).
    idx = _find(entries, "weekday_mincha")
    if idx is not None:
        new = []
        excl = {d}
        if erev.weekday() != 5 and sunday <= erev:
            excl.add(erev)
            t_erev = _floor5(engine.shkia(erev, "nearest") - timedelta(minutes=80))
            new.append(_line("Mincha", _fmt(t_erev), day_spec=_WD[erev.weekday()],
                             date_iso=erev.isoformat(), rule_id="sd_erev_av9_mincha"))
        _exclude_days(entries, idx, excl, week_days)
        noon = engine.chatzos(d, "nearest") - timedelta(hours=12)
        t_gedola = _floor5(noon + timedelta(minutes=30))
        t_late = _round5(engine.shkia(d, "nearest") - timedelta(minutes=30))
        new.append(_line("Mincha", _fmt(t_gedola), day_spec=wd,
                         date_iso=d.isoformat(), rule_id="sd_av9_mincha_1"))
        new.append(_line("Mincha", _fmt(t_late), day_spec=wd,
                         date_iso=d.isoformat(), rule_id="sd_av9_mincha_2"))
        _insert_after(entries, idx, new)

    # Eicha & Kinos after Maariv on the night the fast begins.
    midx = _find(entries, "weekday_maariv")
    if erev.weekday() == 5:  # nidche: fast begins Motzaei Shabbos
        notes.append("Megillas Eicha & Kinos after Maariv on Motzaei Shabbos.")
    elif midx is not None:
        e = entries[midx]
        e["time"] = f"{e['time']} (Eicha & Kinos on {_WD[erev.weekday()]} after Maariv)"

    # Break-fast refreshments (standing custom, often sponsored).
    notes.append(f"Refreshments after Maariv on {wd} following the end of the Fast")


def _elul(notes, sunday, shabbos):
    """Rule 8a: Elul customs, phrased by the weekdays they start on."""
    hy = to_hebrew(shabbos).year
    elul1 = from_hebrew(hy, "Elul", 1)
    if not (sunday <= elul1 <= shabbos):
        return
    ldavid = from_hebrew(hy, "Av", 30)  # first day Rosh Chodesh Elul
    day2 = elul1 + timedelta(days=1)
    notes.append(f"From {_WD[ldavid.weekday()]} add “L’David Adn.. Ori” in "
                 "Shacharis and Mincha.")
    notes.append(
        f"From {_WD[elul1.weekday()]} sound the shofar at the end of Shacharis "
        "(excl. Shabbos) and say three extra Tehillim. "
        f"(On {_WD[elul1.weekday()]} say Tehillim 1–3; on {_WD[day2.weekday()]} "
        "say Tehillim 4–6 and so on.)")


def _rosh_chodesh_span(notes, sunday, shabbos):
    """Rule 12i: 'Rosh Chodesh: from X night to Y afternoon.'.

    The wording always describes the FULL Rosh Chodesh span (which can begin
    the previous week, e.g. a 30th falling on Shabbos), and the note prints on
    the week containing the last RC day, so it appears exactly once. Rosh
    Hashana (1 Tishrei) is a yom tov with its own sheet, not an RC note."""
    day1 = None  # the 1st of the new month inside this week (or just after Shabbos)
    for i in range(7):
        d = sunday + timedelta(days=i)
        h = to_hebrew(d)
        if h.day == 1 and h.month != month_number(h.year, "Tishrei"):
            day1 = d
            break
    if day1 is None:
        return
    # Full span: [30th of the old month if it exists] .. day1.
    prev = day1 - timedelta(days=1)
    first = prev if to_hebrew(prev).day == 30 else day1
    eve = first - timedelta(days=1)
    start = ("Shabbos" if first.weekday() == 5
             else f"{_WD[eve.weekday()]} night")
    end = ("the end of Shabbos" if day1.weekday() == 5
           else f"{_WD[day1.weekday()]} afternoon")
    notes.append(f"Rosh Chodesh: from {start} to {end}.")


def _december_notes(notes, sunday, shabbos, engine):
    """Rules 12b (V'sein Tal U'Matar) + 12e (Nittel)."""
    for year in {sunday.year, shabbos.year}:
        # Tal U'Matar: Maariv of 4 December (5 December before a civil leap year).
        start = date(year, 12, 5) if (year + 1) % 4 == 0 and (
            (year + 1) % 100 != 0 or (year + 1) % 400 == 0) else date(year, 12, 4)
        if sunday <= start <= shabbos:
            notes.append(
                f"Start saying V'sein Tal U'Matar in Shemoneh Esrei from Maariv "
                f"on {_WD[start.weekday()]} night ({start.day} {start:%b}).")
        nittel = date(year, 12, 24)
        if sunday <= nittel <= shabbos:
            c = engine.chatzos(nittel, "nearest")
            ampm = f"{c.hour % 12 or 12}:{c.minute:02d}{'am' if c.hour < 12 else 'pm'}"
            notes.append(
                f"Nittel ({_WD[nittel.weekday()]} night): the custom is not to "
                f"study Torah from shkia until chatzos ({ampm}).")


def apply_special_days(entries: list[dict], sunday: date, shabbos: date,
                       engine: ZmanimEngine) -> list[str]:
    """Mutate the week's entries in place (fast-day splits, decorations) and
    return extra notes. Called by assemble_week after the fast boxes, before
    section-title mapping — davening entries still carry the WEEKDAY key."""
    week_days = [sunday + timedelta(days=i) for i in range(6)]  # Sun..Fri
    notes: list[str] = []
    _minor_fast_mincha(entries, notes, sunday, shabbos, engine, week_days)
    _av9(entries, notes, sunday, shabbos, engine, week_days)
    _elul(notes, sunday, shabbos)
    _rosh_chodesh_span(notes, sunday, shabbos)
    _december_notes(notes, sunday, shabbos, engine)
    return notes
