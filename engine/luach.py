"""Luach (calendar) layer for TTCC sheets — diaspora, Chabad practice.

Provides, for any civil date / week:
  - parsha of the week (diaspora cycle, doubled sedras, Chazak)
  - special-Shabbos labels (Mevorchim, four parshiyos, Shira, HaGadol,
    Chazon, Nachamu, Shuva, Rosh Chodesh, Erev Pesach, Chabad dates)
  - yomim tovim / fasts (with commencement kind), Chanukah, Omer day,
    Pirkei Avos chapter(s) (Chabad: continuous cycle, doubled at year end)
  - molad announcement + Rosh Chodesh announcement (Shabbos Mevorchim)
  - DST transition detection and NSW public holidays

Everything is validated against the 27-sheet fixture corpus by
engine/validate_luach.py.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

from .hebcal import (HDate, from_hebrew, is_leap, molad_announcement,
                     month_names, month_number, rosh_chodesh_dates,
                     rosh_hashanah, to_hebrew, year_length)

SATURDAY = 5  # date.weekday()

SEDRAS = [
    "Bereishis", "Noach", "Lech Lecha", "Vayeira", "Chayei Sarah", "Toldos",
    "Vayeitzei", "Vayishlach", "Vayeishev", "Mikeitz", "Vayigash", "Vayechi",
    "Shemos", "Va'eira", "Bo", "Beshalach", "Yisro", "Mishpatim", "Terumah",
    "Tetzaveh", "Ki Sisa", "Vayakhel", "Pekudei", "Vayikra", "Tzav", "Shemini",
    "Tazria", "Metzora", "Acharei", "Kedoshim", "Emor", "Behar", "Bechukosai",
    "Bemidbar", "Naso", "Beha'aloscha", "Shlach", "Korach", "Chukas", "Balak",
    "Pinchas", "Matos", "Masei", "Devarim", "Va'eschanan", "Eikev", "Re'eh",
    "Shoftim", "Ki Seitzei", "Ki Savo", "Nitzavim", "Vayelech", "Ha'azinu",
    "V'Zos HaBracha",
]
# 1-based sedra numbers of the seven doublable pairs (first of each pair)
PAIR_VP, PAIR_TM, PAIR_AK, PAIR_BB, PAIR_CB, PAIR_MM, PAIR_NV = 22, 27, 29, 32, 39, 42, 51
# Sedras that close a chumash -> "Chazak"
CHAZAK_SEDRAS = {12, 23, 33, 43}


def _saturday_on_or_after(d: date) -> date:
    return d + timedelta(days=(SATURDAY - d.weekday()) % 7)


def _saturday_on_or_before(d: date) -> date:
    return d - timedelta(days=(d.weekday() - SATURDAY) % 7)


@lru_cache(maxsize=None)
def _festival_shabbos_dates(hyear: int) -> set[date]:
    """Shabbosos displaced from the sedra cycle: Pesach (15-22 Nisan) and
    Shavuos (6-7 Sivan). (Tishrei is outside the annual cycle window.)"""
    out = set()
    pesach = from_hebrew(hyear, "Nisan", 15)
    for i in range(8):
        d = pesach + timedelta(days=i)
        if d.weekday() == SATURDAY:
            out.add(d)
    shavuos = from_hebrew(hyear, "Sivan", 6)
    for i in range(2):
        d = shavuos + timedelta(days=i)
        if d.weekday() == SATURDAY:
            out.add(d)
    return out


@lru_cache(maxsize=None)
def parsha_schedule(hyear: int) -> dict[date, tuple[int, ...]]:
    """Sedra cycle of Hebrew year `hyear` (diaspora): Bereishis (Shabbos after
    Simchas Torah) through Nitzavim(-Vayelech) (Shabbos before next RH).
    Returns {shabbos_date: (sedra_number, ...)} - one or two numbers.

    Doubling is derived, then asserted against the classical anchors
    (Tzav/Metzora/Acharei before Pesach, Devarim on Shabbos Chazon); the
    validate script sweeps a wide year range to prove the derivation."""
    bereishis = _saturday_on_or_after(from_hebrew(hyear, "Tishrei", 24))
    next_rh = rosh_hashanah(hyear + 1)
    festival = _festival_shabbos_dates(hyear)
    slots = []
    d = bereishis
    while d < next_rh:
        if d not in festival:
            slots.append(d)
        d += timedelta(days=7)

    leap = is_leap(hyear)
    pesach = from_hebrew(hyear, "Nisan", 15)
    n1 = sum(1 for s in slots if s < pesach)

    # -- derive which pairs are doubled --
    # Nitzavim-Vayelech: doubled unless two open Shabbosos fall in Tishrei of
    # the coming year (RH Mon/Tue), which take Vayelech (Shuva) + Ha'azinu.
    nv = next_rh.weekday() not in (0, 1)  # Mon=0, Tue=1
    # Chukas-Balak (diaspora): doubled iff 2nd day Shavuos displaces a Shabbos.
    cb = from_hebrew(hyear, "Sivan", 7).weekday() == SATURDAY
    if leap:
        vp = tm = ak = bb = False
        if n1 not in (28, 29):  # Metzora or Acharei must close the pre-Pesach run
            raise AssertionError(f"{hyear}: leap pre-Pesach count {n1}")
    else:
        tm = ak = bb = True
        if 25 - n1 not in (0, 1):  # Tzav must close the pre-Pesach run
            raise AssertionError(f"{hyear}: common pre-Pesach count {n1}")
        vp = (25 - n1 == 1)
    # Total fit: sedras 1..51 into len(slots) Shabbosos; each doubled pair
    # saves one slot. (NV merges #52 into #51's slot, so it doesn't count.)
    need = 51 - len(slots)
    mm = need - (vp + tm + ak + bb + cb)
    if mm not in (0, 1):
        raise AssertionError(f"{hyear}: cannot fit cycle (mm={mm})")
    doubled_firsts = {p for p, on in [(PAIR_VP, vp), (PAIR_TM, tm), (PAIR_AK, ak),
                                      (PAIR_BB, bb), (PAIR_CB, cb), (PAIR_MM, bool(mm)),
                                      (PAIR_NV, nv)] if on}

    sched: dict[date, tuple[int, ...]] = {}
    n = 1
    for s in slots:
        if n in doubled_firsts:
            sched[s] = (n, n + 1)
            n += 2
        else:
            sched[s] = (n,)
            n += 1
    # -- classical anchors --
    last = sched[slots[-1]]
    if last[0] != PAIR_NV:
        raise AssertionError(f"{hyear}: cycle ends on {last}, not Nitzavim")
    devarim = next(s for s, ns in sched.items() if 44 in ns)
    av9 = from_hebrew(hyear, "Av", 9)
    if not (0 <= (av9 - devarim).days <= 6):
        raise AssertionError(f"{hyear}: Devarim {devarim} not Shabbos Chazon ({av9})")
    return sched


def sedra_name(numbers: tuple[int, ...]) -> str:
    return "–".join(SEDRAS[n - 1] for n in numbers)  # en dash, house style


@lru_cache(maxsize=None)
def week_parsha(d: date) -> str | None:
    """Parsha named in the week header for the week of Shabbos `d`. On a
    festival Shabbos the sheets title the week by the deferred sedra (the one
    read on the next open Shabbos), e.g. 'The week of Parshas Shemini & Pesach'."""
    reading = shabbos_reading(d)
    probe = d
    while reading is None:
        probe += timedelta(days=7)
        reading = shabbos_reading(probe)
    return reading


@lru_cache(maxsize=None)
def shabbos_reading(d: date) -> str | None:
    """Sedra read on Shabbos `d` (None on festival Shabbosos)."""
    assert d.weekday() == SATURDAY
    hy = to_hebrew(d).year
    for year in (hy, hy - 1):
        sched = parsha_schedule(year)
        if d in sched:
            return sedra_name(sched[d])
    # Tishrei, before Bereishis: Vayelech and/or Ha'azinu
    h = to_hebrew(d)
    if h.month == 1:
        if h.day <= 8:  # Shabbos Shuva
            two_open = rosh_hashanah(h.year).weekday() in (0, 1)  # RH Mon/Tue
            return "Vayelech" if two_open else "Ha'azinu"
        if 11 <= h.day <= 14:  # between YK and Succos (day 10 = YK itself)
            return "Ha'azinu"
    return None  # festival Shabbos (Pesach/Shavuos/Tishrei yomim tovim)


def is_chazak(d: date) -> bool:
    reading = shabbos_reading(d)
    if not reading:
        return False
    last = reading.split("–")[-1]
    return SEDRAS.index(last) + 1 in CHAZAK_SEDRAS


# --- special-Shabbos labels ---

def _adar(hyear: int) -> str:
    return "Adar II" if is_leap(hyear) else "Adar"


def mevorchim_month(d: date) -> str | None:
    """If Shabbos `d` is Shabbos Mevorchim, the month it blesses (not Tishrei)."""
    assert d.weekday() == SATURDAY
    h = to_hebrew(d)
    # Mevorchim: the last Shabbos of the month before Rosh Chodesh (RC falls
    # within the coming week), i.e. day 23-29 - except Elul (Tishrei is not
    # blessed). Day 30 is itself Rosh Chodesh, not Mevorchim.
    if not 23 <= h.day <= 29:
        return None
    names = month_names(h.year)
    if names[h.month - 1] == "Elul":
        return None
    return names[h.month]  # next month's name


def rosh_chodesh_announcement(d: date) -> dict | None:
    """Molad + RC-days info announced on Shabbos Mevorchim `d`."""
    month = mevorchim_month(d)
    if month is None:
        return None
    h = to_hebrew(d)
    m_idx = month_number(h.year, month)
    days = rosh_chodesh_dates(h.year, m_idx)
    return {"month": month, "molad": molad_announcement(h.year, m_idx),
            "rosh_chodesh_days": days}


def shabbos_labels(d: date) -> list[str]:
    """Labels for the 'Shabbos kodesh:' line (order: as printed on sheets)."""
    assert d.weekday() == SATURDAY
    h = to_hebrew(d)
    hy = h.year
    labels: list[str] = []
    if mevorchim_month(d):
        labels.append("Mevorchim")
    if is_chazak(d):
        labels.append("Chazak")
    if h.day in (1, 30):
        labels.append("Rosh Chodesh")
    adar = _adar(hy)
    # Four parshiyos
    if d == _saturday_on_or_before(from_hebrew(hy, adar, 1)):
        labels.append("Shekalim")
    purim = from_hebrew(hy, adar, 14)
    if d == _saturday_on_or_before(purim - timedelta(days=1)):
        labels.append("Zachor")
    rc_nisan = from_hebrew(hy, "Nisan", 1)
    hachodesh = _saturday_on_or_before(rc_nisan)
    if d == hachodesh:
        labels.append("HaChodesh")
    if d == _saturday_on_or_before(hachodesh - timedelta(days=7)):
        labels.append("Parah")
    if to_hebrew(d) == HDate(hy, month_number(hy, adar), 15):
        labels.append("Shushan Purim")
    if is_leap(hy) and to_hebrew(d) == HDate(hy, month_number(hy, "Adar I"), 15):
        labels.append("Shushan Purim Katan")
    # Named Shabbosos
    reading = shabbos_reading(d)
    if reading == "Beshalach":
        labels.append("Shira")
    pesach = from_hebrew(hy, "Nisan", 15)
    if d == _saturday_on_or_before(pesach - timedelta(days=1)):
        labels.append("HaGadol")
    if d == pesach - timedelta(days=1):
        labels.append("Erev Pesach")
    av9 = from_hebrew(hy, "Av", 9)
    if 0 <= (av9 - d).days <= 6:
        labels.append("Chazon")
    if 0 < (d - av9).days <= 7:
        labels.append("Nachamu")
    yk = from_hebrew(hy, "Tishrei", 10)
    if rosh_hashanah(hy) < d < yk:
        labels.append("Shuva")
    # Chabad dates falling on this Shabbos
    if to_hebrew(d) == HDate(hy, month_number(hy, "Tammuz"), 3):
        labels.append("Gimmel Tammuz")
    return labels


# --- holidays / fasts / omer ---

def _shift_fast(d: date, name: str) -> tuple[date, str]:
    """Push a Shabbos fast to Sunday (or Taanis Esther back to Thursday)."""
    if d.weekday() != SATURDAY:
        return d, name
    if name == "Taanis Esther":
        return d - timedelta(days=2), name
    return d + timedelta(days=1), f"{name} (Nidche)"


@lru_cache(maxsize=None)
def fasts(hyear: int) -> list[dict]:
    """All fasts of the Hebrew year. kind: 'dawn' (alos->tzeis 6 deg),
    'night' (previous shkia -> tzeis 8.4 deg), 'yk' (candle lighting ->
    tzeis 8.4 deg)."""
    out = []
    d, name = _shift_fast(from_hebrew(hyear, "Tishrei", 3), "Tzom Gedaliah")
    out.append({"date": d, "name": name, "kind": "dawn"})
    out.append({"date": from_hebrew(hyear, "Tishrei", 10), "name": "Yom Kippur",
                "kind": "yk"})
    out.append({"date": from_hebrew(hyear, "Teves", 10), "name": "Fast of 10 Teves",
                "kind": "dawn"})
    d, name = _shift_fast(from_hebrew(hyear, _adar(hyear), 13), "Taanis Esther")
    out.append({"date": d, "name": name, "kind": "dawn"})
    bechorim = from_hebrew(hyear, "Nisan", 14)
    if bechorim.weekday() == SATURDAY:  # Erev Pesach on Shabbos -> Thursday
        bechorim -= timedelta(days=2)
    out.append({"date": bechorim, "name": "Taanis Bechorim", "kind": "dawn"})
    d, name = _shift_fast(from_hebrew(hyear, "Tammuz", 17), "Fast of 17 Tammuz")
    out.append({"date": d, "name": name, "kind": "dawn"})
    d, name = _shift_fast(from_hebrew(hyear, "Av", 9), "Fast of 9 Av")
    out.append({"date": d, "name": name, "kind": "night"})
    return out


@lru_cache(maxsize=None)
def holidays(hyear: int) -> dict[date, list[str]]:
    """Diaspora holiday labels by civil date for Hebrew year `hyear`."""
    ev: dict[date, list[str]] = {}

    def add(d: date, label: str):
        ev.setdefault(d, []).append(label)

    def h(m: str, day: int) -> date:
        return from_hebrew(hyear, m, day)

    add(rosh_hashanah(hyear), "Rosh Hashana Day 1")
    add(h("Tishrei", 2), "Rosh Hashana Day 2")
    add(h("Tishrei", 9), "Erev Yom Kippur")
    add(h("Tishrei", 10), "Yom Kippur")
    add(h("Tishrei", 14), "Erev Succos")
    add(h("Tishrei", 15), "Succos day 1")
    add(h("Tishrei", 16), "Succos day 2")
    for day in range(17, 21):
        add(h("Tishrei", day), "Chol HaMoed Succos")
    add(h("Tishrei", 21), "Hoshana Rabbah")
    add(h("Tishrei", 22), "Shemini Atzeres")
    add(h("Tishrei", 23), "Simchas Torah")
    chanukah = h("Kislev", 25)
    for i in range(8):
        add(chanukah + timedelta(days=i), f"Chanukah day {i + 1}")
    add(h("Shevat", 15), "Tu BiShvat")
    if is_leap(hyear):
        add(h("Adar I", 14), "Purim Katan")
        add(h("Adar I", 15), "Shushan Purim Katan")
    adar = _adar(hyear)
    add(h(adar, 14), "Purim")
    add(h(adar, 15), "Shushan Purim")
    add(h("Nisan", 14), "Erev Pesach")
    add(h("Nisan", 15), "Pesach day 1")
    add(h("Nisan", 16), "Pesach day 2")
    for day in range(17, 21):
        add(h("Nisan", day), "Chol HaMoed Pesach")
    add(h("Nisan", 21), "Shevi'i Shel Pesach")
    add(h("Nisan", 22), "Acharon Shel Pesach")
    add(h("Nisan", 23), "Isru Chag")
    add(h("Iyar", 14), "Pesach Sheni")
    add(h("Iyar", 18), "Lag BaOmer")
    add(h("Sivan", 5), "Erev Shavuos")
    add(h("Sivan", 6), "Shavuos day 1")
    add(h("Sivan", 7), "Shavuos day 2")
    add(h("Av", 15), "Tu B'Av")
    add(rosh_hashanah(hyear + 1) - timedelta(days=1), "Erev Rosh Hashana")
    for f in fasts(hyear):
        if f["name"] != "Yom Kippur":
            add(f["date"], f["name"])
    # Chabad dates
    add(h("Kislev", 19), "Yud-Tes Kislev")
    add(h("Kislev", 20), "Chof Kislev")
    add(h("Shevat", 10), "Yud Shevat")
    add(h("Shevat", 22), "Chof-Beis Shevat")
    add(h("Nisan", 11), "Yud-Alef Nisan")
    add(h("Tammuz", 3), "Gimmel Tammuz")
    add(h("Tammuz", 12), "Yud-Beis Tammuz")
    add(h("Tammuz", 13), "Yud-Gimmel Tammuz")
    add(h("Elul", 18), "Chai Elul")
    return ev


_YT_OPENERS = {"Rosh Hashana Day 1", "Yom Kippur", "Succos day 1",
               "Shemini Atzeres", "Pesach day 1", "Shevi'i Shel Pesach",
               "Shavuos day 1"}


def day_labels(d: date) -> list[str]:
    hy = to_hebrew(d).year
    out = []
    for year in (hy, hy - 1, hy + 1):
        out.extend(l for l in holidays(year).get(d, []) if l not in out)
    tomorrow = set(holidays(hy).get(d + timedelta(days=1), []))
    if tomorrow & _YT_OPENERS and not any("day 1" in l or "Shel Pesach" in l
                                          or l in _YT_OPENERS for l in out):
        out.append("Erev Yom Tov")
    return out


def omer_day(d: date) -> int | None:
    """Omer count of civil day `d` (16 Nisan = 1 ... 5 Sivan = 49)."""
    hy = to_hebrew(d).year
    start = from_hebrew(hy, "Nisan", 16)
    n = (d - start).days + 1
    return n if 1 <= n <= 49 else None


# --- Pirkei Avos (Chabad, diaspora): continuous cycle, doubled at year end ---

@lru_cache(maxsize=None)
def _pirkei_avos_schedule(hyear: int) -> dict[date, tuple[int, ...]]:
    first = _saturday_on_or_after(from_hebrew(hyear, "Nisan", 23))
    last = _saturday_on_or_before(rosh_hashanah(hyear + 1) - timedelta(days=1))
    festival = _festival_shabbos_dates(hyear)
    slots = []
    d = first
    while d <= last:
        if d not in festival:
            slots.append(d)
        d += timedelta(days=7)
    # Assign 1..6 cycling; double on the final Shabbosos so the year ends on 6.
    last_single = (len(slots) - 1) % 6 + 1
    n_double = (6 - last_single) % 6
    if n_double > len(slots):
        raise AssertionError(f"{hyear}: pirkei avos cannot fit")
    sched: dict[date, tuple[int, ...]] = {}
    ch = 1
    for i, s in enumerate(slots):
        if i >= len(slots) - n_double:
            sched[s] = (ch, ch + 1)
            ch += 2
        else:
            sched[s] = (ch,)
            ch += 1
        if ch > 6:
            ch = 1
    return sched


def pirkei_avos(d: date) -> tuple[int, ...] | None:
    """Chapter(s) said on Shabbos `d` (None outside the Pesach->RH season)."""
    assert d.weekday() == SATURDAY
    hy = to_hebrew(d).year
    for year in (hy, hy - 1):
        sched = _pirkei_avos_schedule(year)
        if d in sched:
            return sched[d]
    return None


# --- week header ---

def hebrew_date_range(start: date, end: date) -> str:
    """'27 Iyar – 4 Sivan 5781' / '25 Adar I – 2 Adar II 5784' style."""
    a, b = to_hebrew(start), to_hebrew(end)
    if a.month == b.month:
        return f"{a.day}–{b.day} {b.month_name} {b.year}"
    left = f"{a.day} {a.month_name}"
    if a.year != b.year:
        left += f" {a.year}"
    return f"{left} – {b.day} {b.month_name} {b.year}"


# --- DST & NSW public holidays ---

def dst_transition(start: date, end: date, tz=None) -> date | None:
    """First civil date in [start, end] whose UTC offset differs from the
    previous day's (Australia/Sydney by default)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    tz = tz or ZoneInfo("Australia/Sydney")
    d = start
    while d <= end:
        off0 = datetime(d.year, d.month, d.day, 12, tzinfo=tz).utcoffset()
        prev = d - timedelta(days=1)
        off1 = datetime(prev.year, prev.month, prev.day, 12, tzinfo=tz).utcoffset()
        if off0 != off1:
            return d
        d += timedelta(days=1)
    return None


def _easter(year: int) -> date:
    """Gregorian Easter Sunday (anonymous computus)."""
    a, b, c = year % 19, year // 100, year % 100
    d_, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d_ - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def nsw_public_holidays(year: int) -> dict[date, str]:
    """NSW public holidays (gazetted rules)."""
    hol: dict[date, str] = {}

    def observed(d: date, name: str):
        hol[d] = name
        if d.weekday() == SATURDAY:
            hol[d + timedelta(days=2)] = f"{name} (observed)"
        elif d.weekday() == 6:
            hol[d + timedelta(days=1)] = f"{name} (observed)"

    observed(date(year, 1, 1), "New Year's Day")
    observed(date(year, 1, 26), "Australia Day")
    easter = _easter(year)
    hol[easter - timedelta(days=2)] = "Good Friday"
    hol[easter - timedelta(days=1)] = "Easter Saturday"
    hol[easter] = "Easter Sunday"
    hol[easter + timedelta(days=1)] = "Easter Monday"
    hol[date(year, 4, 25)] = "Anzac Day"
    june1 = date(year, 6, 1)
    hol[june1 + timedelta(days=(7 - june1.weekday()) % 7 + 7)] = "King's Birthday"
    oct1 = date(year, 10, 1)
    hol[oct1 + timedelta(days=(7 - oct1.weekday()) % 7)] = "Labour Day"
    observed(date(year, 12, 25), "Christmas Day")
    observed(date(year, 12, 26), "Boxing Day")
    return hol
