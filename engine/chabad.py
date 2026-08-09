"""Chabad calendar days: the Rebbeim's yahrtzeits and birthdays, the
liberations, and the dates TTCC marks.

Separate from ``luach.holidays()`` on purpose. ``holidays()`` feeds the printed
sheets, and the sheets mark only five of these days (Gimmel Tammuz, Yud Shevat,
Yud-Alef Nisan, Yud-Tes/Chof Kislev, Yud-Gimmel Tammuz — verified across all 27
fixtures). Folding twenty more labels into ``holidays()`` would silently change
what prints on a sheet, which nobody asked for. The screens want the fuller
luach, so they read this table instead.

This is the *canonical* table: dates, and a source for each. The display plugin
layers its own editable descriptions and the shul's own custom dates on top, and
hides rather than deletes anything from here — see the ttcc-display warplan §3.1.

Scope and conventions were settled with TTCC on 2026-08-04:
  - transliteration is title case with the sheets' own month spellings
    (``Yud-Alef Nisan``, ``Yud Shevat``, ``Chof-Daled Teves``);
  - the day label says ``Cheshvan`` where the engine's month name is
    ``Marcheshvan``;
  - Adar dates fall in **Adar II** in a leap year;
  - one visual treatment for every day, so ``kind`` is metadata for callers that
    want it, not a styling instruction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .hebcal import from_hebrew, hebrew_numeral, is_leap, to_hebrew

# Source shorthands, expanded in `SOURCES`.
_CAL = "chabad.org-calendar"
_CHANA = "chabad.org-chana"
_SHTERNA = "chabad.org-shterna-sarah"

SOURCES = {
    _CAL: "chabad.org Jewish calendar day pages (https://www.chabad.org/calendar/)",
    _CHANA: "https://www.chabad.org/therebbe/article_cdo/aid/2540507/jewish/"
            "Yahrtzeit-of-Rebbetzin-Chana-Schneerson-Vov-Tishrei-5741-1980.htm",
    _SHTERNA: "https://www.chabad.org/calendar/view/day_cdo/aid/252537/jewish/"
              "Rebbetzin-Shterna-Sarah-Schneersohn.htm",
}

# Kinds. Metadata only — TTCC chose a single visual treatment for every day.
YAHRTZEIT = "yahrtzeit"
BIRTHDAY = "birthday"
LIBERATION = "liberation"
HISTORIC = "historic"


@dataclass(frozen=True)
class ChabadDay:
    """One entry in the table.

    `month` is the engine's month name in a *non-leap* year. `leap_month` gives
    the month in a leap year where it differs (Adar dates -> Adar II).
    `hebrew_override` exists for days written by their idiom rather than their
    numeral: Chai Elul is ח״י אלול, not י״ח אלול.
    `confirmed` is False for a date still awaiting a citation — callers that must
    not display an unverified date can filter on it.
    """

    month: str
    day: int
    name: str
    description: str
    kind: str
    source: str
    label_month: str | None = None     # month as written in the day's name
    leap_month: str | None = None
    hebrew_override: str | None = None
    confirmed: bool = True


DAYS: tuple[ChabadDay, ...] = (
    ChabadDay("Tishrei", 6, "Vov Tishrei",
              "Yahrtzeit of Rebbetzin Chana Schneerson, the Rebbe's mother",
              YAHRTZEIT, _CHANA),
    ChabadDay("Tishrei", 13, "Yud-Gimmel Tishrei",
              "Yahrtzeit of the Rebbe Maharash", YAHRTZEIT, _CAL),
    ChabadDay("Marcheshvan", 20, "Chof Cheshvan",
              "Birthday of the Rebbe Rashab", BIRTHDAY, _CAL,
              label_month="Cheshvan"),
    ChabadDay("Kislev", 9, "Tes Kislev",
              "Birthday and yahrtzeit of the Mitteler Rebbe", YAHRTZEIT, _CAL),
    ChabadDay("Kislev", 10, "Yud Kislev",
              "Liberation of the Mitteler Rebbe", LIBERATION, _CAL),
    ChabadDay("Kislev", 14, "Yud-Daled Kislev",
              "The Rebbe's wedding", HISTORIC, _CAL),
    ChabadDay("Kislev", 19, "Yud-Tes Kislev",
              "Rosh Hashanah of Chassidus — liberation of the Alter Rebbe; "
              "yahrtzeit of the Maggid of Mezritch", LIBERATION, _CAL),
    ChabadDay("Kislev", 20, "Chof Kislev",
              "Second day of the liberation of the Alter Rebbe", LIBERATION, _CAL),
    ChabadDay("Teves", 5, "Hey Teves",
              "Didan Notzach — the seforim victory", HISTORIC, _CAL),
    ChabadDay("Teves", 24, "Chof-Daled Teves",
              "Yahrtzeit of the Alter Rebbe", YAHRTZEIT, _CAL),
    ChabadDay("Shevat", 10, "Yud Shevat",
              "Yahrtzeit of the Rebbe Rayatz; the Rebbe's acceptance of the "
              "leadership", YAHRTZEIT, _CAL),
    ChabadDay("Shevat", 13, "Yud-Gimmel Shevat",
              "Yahrtzeit of Rebbetzin Shterna Sarah", YAHRTZEIT, _SHTERNA),
    ChabadDay("Shevat", 22, "Chof-Beis Shevat",
              "Yahrtzeit of Rebbetzin Chaya Mushka", YAHRTZEIT, _CAL),
    # Adar dates fall in Adar II in a leap year (TTCC, 2026-08-04).
    ChabadDay("Adar", 25, "Chof-Hey Adar",
              "Birthday of Rebbetzin Chaya Mushka", BIRTHDAY, _CAL,
              leap_month="Adar II"),
    ChabadDay("Nisan", 2, "Beis Nisan",
              "Yahrtzeit of the Rebbe Rashab", YAHRTZEIT, _CAL),
    ChabadDay("Nisan", 11, "Yud-Alef Nisan",
              "The Rebbe's birthday", BIRTHDAY, _CAL),
    ChabadDay("Nisan", 13, "Yud-Gimmel Nisan",
              "Yahrtzeit of the Tzemach Tzedek", YAHRTZEIT, _CAL),
    ChabadDay("Iyar", 2, "Beis Iyar",
              "Birthday of the Rebbe Maharash", BIRTHDAY, _CAL),
    ChabadDay("Sivan", 28, "Chof-Ches Sivan",
              "The Rebbe and Rebbetzin's arrival in America", HISTORIC, _CAL),
    ChabadDay("Tammuz", 3, "Gimmel Tammuz",
              "Yahrtzeit of the Rebbe", YAHRTZEIT, _CAL),
    ChabadDay("Tammuz", 12, "Yud-Beis Tammuz",
              "Birthday of the Rebbe Rayatz, and his liberation",
              LIBERATION, _CAL),
    ChabadDay("Tammuz", 13, "Yud-Gimmel Tammuz",
              "Second day of the liberation of the Rebbe Rayatz",
              LIBERATION, _CAL),
    ChabadDay("Av", 20, "Chof Av",
              "Yahrtzeit of R' Levi Yitzchak Schneerson, the Rebbe's father",
              YAHRTZEIT, _CAL),
    # Flagged for confirmation (ttcc-display warplan §3.1) — included because
    # TTCC asked for the full luach, but not yet cited, so `confirmed` is False.
    ChabadDay("Elul", 15, "Yud-Hey Elul",
              "Founding of Tomchei Temimim", HISTORIC, "",
              confirmed=False),
    ChabadDay("Elul", 18, "Chai Elul",
              "Birthdays of the Baal Shem Tov and the Alter Rebbe",
              BIRTHDAY, _CAL,
              # Written by its idiom: ח״י, not י״ח.
              hebrew_override="ח״י אלול"),
)


def _month_for_year(entry: ChabadDay, hyear: int) -> str:
    if entry.leap_month and is_leap(hyear):
        return entry.leap_month
    return entry.month


def _hebrew_label(entry: ChabadDay, hyear: int) -> str:
    """The day in Hebrew letters, e.g. 'י״ט כסלו'. No year: these are annual."""
    if entry.hebrew_override:
        return entry.hebrew_override
    from .hebcal import hebrew_month_letters, month_number
    month = _month_for_year(entry, hyear)
    return (f"{hebrew_numeral(entry.day)} "
            f"{hebrew_month_letters(hyear, month_number(hyear, month))}")


def _as_dict(entry: ChabadDay, hyear: int) -> dict:
    return {
        "name": entry.name,
        "hebrew": _hebrew_label(entry, hyear),
        "description": entry.description,
        "kind": entry.kind,
        "hebrew_month": _month_for_year(entry, hyear),
        "hebrew_day": entry.day,
        "source": SOURCES.get(entry.source, entry.source),
        "confirmed": entry.confirmed,
    }


def chabad_days(hyear: int, *, include_unconfirmed: bool = True) -> dict[date, list[dict]]:
    """Every Chabad day in Hebrew year `hyear`, keyed by civil date.

    A civil date can carry more than one entry only if the table ever gains two
    on the same Hebrew date; the value is a list so that stays representable.
    """
    out: dict[date, list[dict]] = {}
    for entry in DAYS:
        if not entry.confirmed and not include_unconfirmed:
            continue
        d = from_hebrew(hyear, _month_for_year(entry, hyear), entry.day)
        out.setdefault(d, []).append(_as_dict(entry, hyear))
    return out


def for_date(d: date, *, include_unconfirmed: bool = True) -> list[dict]:
    """Chabad days falling on the Hebrew date that contains `d`.

    Callers displaying this must have already resolved which Hebrew date they
    mean — the screens roll over at tzeis, not midnight — and pass that date.
    """
    hyear = to_hebrew(d).year
    return chabad_days(hyear, include_unconfirmed=include_unconfirmed).get(d, [])
