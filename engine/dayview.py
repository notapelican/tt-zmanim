"""Per-day view: the neutral daily payload behind the display screens.

Deliberately *not* display-shaped. The screens compose their own panes; this
returns one dict per day with the day's zmanim, its luach labels, its Hebrew
date (in letters as well as words) and any Chabad days falling on it. Same
pass-through discipline as the rest of the engine surface: every time here comes
from ``ZmanimEngine`` at that method's own rounding policy, and nothing is
re-rounded or reformatted downstream.

Why this exists: the service was week-shaped. ``assemble.generate`` returns
week/day *sheet blocks* and ``highlights`` returns a week's headline times, but a
screen showing "today" needed neither. See the ttcc-display warplan §3.

Two deliberate omissions:

- **Candle lighting is not here.** ``highlights`` already computes it for the
  widget and the Shabbos screen, and one number should have one source. A screen
  wanting candle lighting asks ``/highlights``.
- **Mincha gedola is not here** because the engine has no such zman. It would be
  a new halachic definition plus a rounding choice, and this project does not
  add either without the Rov — see WARPLAN §4 and the Phase 0 gate.
"""
from __future__ import annotations

from datetime import date, timedelta

from . import chabad, hebcal, luach
from .zmanim import ZmanimEngine

# Zmanim included for every day, in the order a screen would read them, as
# (payload key, engine method). Each is called with the method's own default
# rounding, which is where the sheet's per-zman policy lives (see
# engine/zmanim.py) — do not pass a rounding from here.
#
# `chatzos` is renamed on the way out. In this engine it means halachic
# *midnight* (solar noon + 12h), so it is published as `chatzos_halayla`: a key
# called plain "chatzos" in a list of a day's times reads as midday, and a screen
# that shows 1:08am as midday is exactly the failure this project cannot have.
# Chatzos hayom (midday) is deliberately absent — the fixtures show it printed at
# both solar_noon and solar_noon−1min (phase0/mining/SPECIAL-DAYS-CATALOG.md), so
# its rounding is not settled, and this is not the place to pick one.
_ZMANIM = (
    ("alos", "alos"),
    ("misheyakir", "misheyakir"),
    ("netz", "netz"),
    ("sof_zman_shema", "sof_zman_shema"),
    ("sof_zman_tfila", "sof_zman_tfila"),
    ("plag_hamincha", "plag_hamincha"),
    ("shkia", "shkia"),
    ("tzeis", "tzeis"),
    ("tzeis_shabbos", "tzeis_shabbos"),
    ("chatzos_halayla", "chatzos"),
)

_WEEKDAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Shabbos")


def _fmt(dt) -> str:
    return f"{dt.hour:02d}:{dt.minute:02d}"


def _weekday_name(d: date) -> str:
    # date.weekday(): Monday=0 .. Sunday=6. The sheets run Sunday..Shabbos.
    return _WEEKDAYS[(d.weekday() + 1) % 7]


def _hebrew_block(d: date) -> dict:
    h = hebcal.to_hebrew(d)
    return {
        "year": h.year,
        "month": h.month_name,
        "day": h.day,
        "day_letters": hebcal.hebrew_numeral(h.day),
        "month_letters": hebcal.hebrew_month_letters(h.year, h.month),
        "year_letters": hebcal.hebrew_year_letters(h.year),
        "letters": hebcal.hebrew_date_letters(d),
        "is_leap_year": hebcal.is_leap(h.year),
    }


def _coming_shabbos(d: date) -> date:
    """The Shabbos on or after `d`. `luach.week_parsha` is keyed by Shabbos."""
    return d + timedelta(days=(5 - d.weekday()) % 7)


def _is_fast(d: date) -> bool:
    hy = hebcal.to_hebrew(d).year
    for year in (hy, hy - 1, hy + 1):
        for f in luach.fasts(year):
            if f["date"] == d:
                return True
    return False


def day_view(d: date, *, engine: ZmanimEngine | None = None) -> dict:
    """One day's zmanim, luach labels, Hebrew date and Chabad days.

    `d` is a civil date. Note that the Hebrew date returned is the one the
    engine assigns to that civil date — i.e. the Hebrew day that *ends* on it.
    A caller rolling over at tzeis (the screens do) must decide for itself which
    civil date it means before calling, and the tzeis it needs to make that
    decision is in this payload.
    """
    eng = engine or ZmanimEngine()

    zmanim: dict[str, str] = {}
    # The same times as absolute, offset-bearing instants.
    #
    # Not redundant: `zmanim` is the display string and stays authoritative for
    # what a screen prints, but a *comparison* ("are we past shkia yet?") made
    # from "20:03" plus a date has to assume a timezone, and a signage player is
    # quite likely to be running UTC. Publishing the instant removes the guess.
    zmanim_iso: dict[str, str] = {}
    # Zmanim whose clock time falls on the *following* civil date — chatzos
    # halayla always, and anything else the solver puts past midnight. Published
    # explicitly so a caller comparing "is it past this time yet" cannot get the
    # day wrong.
    next_day: list[str] = []
    for key, method in _ZMANIM:
        try:
            dt = getattr(eng, method)(d)
        except Exception:
            # A zman that cannot be computed for this date (polar edge cases in
            # the solar solver) is omitted rather than guessed at. Panes drop a
            # row they have no time for.
            continue
        zmanim[key] = _fmt(dt)
        zmanim_iso[key] = dt.isoformat()
        if dt.date() != d:
            next_day.append(key)

    labels = luach.day_labels(d)
    is_shabbos = d.weekday() == 5

    out = {
        "date": d.isoformat(),
        "weekday": _weekday_name(d),
        "hebrew": _hebrew_block(d),
        "zmanim": zmanim,
        "zmanim_iso": zmanim_iso,
        "zmanim_next_day": next_day,
        "labels": labels,
        "chabad": chabad.for_date(d),
        "omer": luach.omer_day(d),
        # The parsha of the week this day belongs to — i.e. the one that will be
        # read on the coming Shabbos, which is how the sheets title a week.
        "parsha": luach.week_parsha(_coming_shabbos(d)),
        "is_shabbos": is_shabbos,
        "is_fast": _is_fast(d),
        "is_rosh_chodesh": any("Rosh Chodesh" in l for l in labels),
    }

    if is_shabbos:
        out["shabbos_labels"] = luach.shabbos_labels(d)
        out["shabbos_reading"] = luach.shabbos_reading(d)
        avos = luach.pirkei_avos(d)
        out["pirkei_avos"] = list(avos) if avos else None

    return out


def day_views(start: date, end: date, *,
              engine: ZmanimEngine | None = None) -> dict:
    """`day_view` for every day in [start, end] inclusive."""
    eng = engine or ZmanimEngine()
    days = []
    d = start
    while d <= end:
        days.append(day_view(d, engine=eng))
        d += timedelta(days=1)
    return {"days": days}
