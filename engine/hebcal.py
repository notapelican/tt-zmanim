"""Hebrew calendar core: year arithmetic, Hebrew<->civil conversion, molad.

Implements the classical fixed (Hillel II) calendar via the compact
elapsed-days formulation (Dershowitz & Reingold, "Calendrical Calculations"),
verified against the 27-fixture golden corpus (see engine/validate_luach.py).

Month numbering used throughout: civil order from Tishrei.
  1 Tishrei, 2 Marcheshvan, 3 Kislev, 4 Teves, 5 Shevat,
  6 Adar (or Adar I), [6.5 -> 7 Adar II in leap years],
  then Nisan..Elul. To keep integers, months run 1..12 (common) or
  1..13 (leap), with Adar II = 7 in leap years and Nisan = 7 (common) / 8 (leap).
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

# Rata Die ordinal of the day before 1 Tishrei year 1; Python's
# date.toordinal() is Rata Die, so conversion is direct.
_HEBREW_EPOCH = -1373427

PARTS_PER_DAY = 25920          # 24h * 1080 chalakim
MOLAD_INTERVAL = 765433        # 29d 12h 793p in chalakim
# Molad Tishrei year 1 ("BaHaRaD"): Sunday evening + 5h 204p (day 2, from 6pm)
_FIRST_MOLAD_PARTS = 5 * 1080 + 204


def is_leap(year: int) -> bool:
    return (7 * year + 1) % 19 < 7


def months_in_year(year: int) -> int:
    return 13 if is_leap(year) else 12


def _months_elapsed(year: int) -> int:
    """Lunar months before 1 Tishrei of `year`."""
    return (235 * year - 234) // 19


@lru_cache(maxsize=None)
def _elapsed_days(year: int) -> int:
    """Days from the epoch to 1 Tishrei of `year`, before year-length fixes.
    The +6h fold (12084 = 5h204p + 6h) bakes in the molad-zaken postponement;
    the (3*(d+1))%7 test applies the lo-ADU-rosh postponement."""
    months = _months_elapsed(year)
    parts = 12084 + 13753 * months
    days = 29 * months + parts // PARTS_PER_DAY
    return days + 1 if (3 * (days + 1)) % 7 < 3 else days


@lru_cache(maxsize=None)
def rosh_hashanah_ordinal(year: int) -> int:
    """Rata Die ordinal of 1 Tishrei of `year` (incl. GaTRaD/BeTUTeKPaT fixes)."""
    d = _elapsed_days(year)
    if _elapsed_days(year + 1) - d == 356:
        d += 2
    elif d - _elapsed_days(year - 1) == 382:
        d += 1
    return _HEBREW_EPOCH + d


def rosh_hashanah(year: int) -> date:
    return date.fromordinal(rosh_hashanah_ordinal(year))


def year_length(year: int) -> int:
    return rosh_hashanah_ordinal(year + 1) - rosh_hashanah_ordinal(year)


def month_lengths(year: int) -> list[int]:
    """Length of each month, civil order from Tishrei (index 0 = Tishrei)."""
    yl = year_length(year)
    cheshvan = 30 if yl in (355, 385) else 29
    kislev = 29 if yl in (353, 383) else 30
    if is_leap(year):
        #        Tis Che Kis Tev She AdI AdII Nis Iyr Siv Tam Av  Elu
        return [30, cheshvan, kislev, 29, 30, 30, 29, 30, 29, 30, 29, 30, 29]
    return [30, cheshvan, kislev, 29, 30, 29, 30, 29, 30, 29, 30, 29]


def month_names(year: int) -> list[str]:
    if is_leap(year):
        return ["Tishrei", "Marcheshvan", "Kislev", "Teves", "Shevat",
                "Adar I", "Adar II", "Nisan", "Iyar", "Sivan", "Tammuz", "Av", "Elul"]
    return ["Tishrei", "Marcheshvan", "Kislev", "Teves", "Shevat",
            "Adar", "Nisan", "Iyar", "Sivan", "Tammuz", "Av", "Elul"]


class HDate:
    """A Hebrew date. `month` is the civil-order index (1 = Tishrei)."""

    __slots__ = ("year", "month", "day")

    def __init__(self, year: int, month: int, day: int):
        self.year, self.month, self.day = year, month, day

    @property
    def month_name(self) -> str:
        return month_names(self.year)[self.month - 1]

    def to_date(self) -> date:
        ord_ = rosh_hashanah_ordinal(self.year)
        ord_ += sum(month_lengths(self.year)[: self.month - 1]) + self.day - 1
        return date.fromordinal(ord_)

    def __repr__(self):
        return f"{self.day} {self.month_name} {self.year}"

    def __eq__(self, other):
        return (self.year, self.month, self.day) == (other.year, other.month, other.day)


def month_number(year: int, name: str) -> int:
    """Civil-order month index for a name (e.g. 'Nisan' -> 7 or 8)."""
    return month_names(year).index(name) + 1


def from_hebrew(year: int, month_name_: str, day: int) -> date:
    return HDate(year, month_number(year, month_name_), day).to_date()


def to_hebrew(d: date) -> HDate:
    # Hebrew year that starts on/before d: civil year + 3760 or 3761.
    year = d.year + 3760
    while rosh_hashanah_ordinal(year + 1) <= d.toordinal():
        year += 1
    while rosh_hashanah_ordinal(year) > d.toordinal():
        year -= 1
    rem = d.toordinal() - rosh_hashanah_ordinal(year)
    for i, ml in enumerate(month_lengths(year)):
        if rem < ml:
            return HDate(year, i + 1, rem + 1)
        rem -= ml
    raise AssertionError("date beyond year end")


# --- Molad ---

def molad(year: int, month: int) -> tuple[int, int]:
    """Molad of the given month (civil-order index, 1 = Tishrei of `year`).
    Returns (rata_die_ordinal_of_halachic_day, parts_after_6pm)."""
    total = _FIRST_MOLAD_PARTS + (_months_elapsed(year) + month - 1) * MOLAD_INTERVAL
    days, parts = divmod(total, PARTS_PER_DAY)
    # Day 0 of the molad count = the halachic day of BaHaRaD (a Monday),
    # which is _HEBREW_EPOCH - 1 in Rata Die (calibrated against the corpus's
    # printed molad announcements; see validate_luach.py).
    return _HEBREW_EPOCH - 1 + days, parts


def molad_announcement(year: int, month: int) -> dict:
    """Molad in the form announced (civil day + civil clock, 'Jerusalem
    Standard Time'): {weekday, hour(1-12), minute, ampm, chalakim}.
    weekday: 0=Sunday..5=Friday, 6=Shabbos (civil day of the molad moment)."""
    day_ord, parts = molad(year, month)
    if parts < 6 * 1080:  # before midnight: evening of previous civil day
        civil_ord = day_ord - 1
        hour24 = 18 + parts // 1080
    else:
        civil_ord = day_ord
        hour24 = parts // 1080 - 6
    rem = parts % 1080
    minute, chalakim = divmod(rem, 18)
    weekday = (civil_ord % 7 + 1) % 7  # RD 1 = Monday -> Sunday=0..Shabbos=6
    ampm = "am" if hour24 < 12 else "pm"
    hour12 = hour24 % 12 or 12
    return {"weekday": weekday, "hour": hour12, "minute": minute,
            "ampm": ampm, "chalakim": chalakim, "hour24": hour24}


def rosh_chodesh_dates(year: int, month: int) -> list[date]:
    """Civil date(s) of Rosh Chodesh of the given month (1-2 days).
    month is civil-order index of the NEW month (>=2; RC Tishrei is RH)."""
    first = HDate(year, month, 1).to_date()
    if month_lengths(year)[month - 2] == 30:
        return [first - timedelta(days=1), first]
    return [first]
