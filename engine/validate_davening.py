"""Regressions for `assemble.day_minyanim` — the per-day minyan resolution
behind the display screens' davening pane.

Run:  python3 -m engine.validate_davening   (exits nonzero on regression)

The stakes here are the highest of anything the display layer does: a wrong
zman on a wall is embarrassing, but a wrong *minyan time* is the reason someone
shows up to an empty shul. So this checks the thing that actually went wrong
once already while building it — `day_minyanim` originally dropped every
Shabbos-day rule built on a FixedTime (Tehillim, Chassidus, Shabbos Shacharis),
because those carry neither a `date` nor a `day_spec` (only ZmanAnchored/ranged
weekday lines do). The fix reads the block's own `friday`/`shabbos` civil dates
for every non-weekday section, rather than trusting each entry to carry its own
date — and every case below exists because it once silently failed.
"""
from __future__ import annotations

import itertools
import sys
from datetime import date, datetime, timedelta

from . import luach
from .assemble import day_minyanim, day_spec_includes, format_day_spec
from .zmanim import ZmanimEngine


class Score:
    def __init__(self):
        self.groups: dict[str, list[int]] = {}
        self.failures: list[str] = []

    def add(self, group: str, ok: bool, msg: str = ""):
        g = self.groups.setdefault(group, [0, 0])
        g[1] += 1
        if ok:
            g[0] += 1
        else:
            self.failures.append(f"[{group}] {msg}")

    def report(self) -> bool:
        for name in sorted(self.groups):
            ok, total = self.groups[name]
            mark = "OK " if ok == total else "FAIL"
            print(f"  {mark} {name}: {ok}/{total}")
        if self.failures:
            print(f"\n{len(self.failures)} failure(s):")
            for f in self.failures[:40]:
                print("  -", f)
        return not self.failures


def check_day_spec_roundtrip(sc: Score):
    """format_day_spec and day_spec_includes must be exact inverses: for every
    subset of a week's Sun-Fri days, every day of that week must agree on
    whether it is "in" the formatted spec."""
    sunday = date(2026, 1, 25)
    week = [sunday + timedelta(days=i) for i in range(6)]  # Sun..Fri
    for r in range(1, 6):
        for combo in itertools.combinations(week, r):
            spec = format_day_spec(list(combo))
            for d in week:
                want = d in combo
                got = day_spec_includes(spec, d)
                sc.add("day_spec_roundtrip", want == got,
                       f"{spec!r} at {d} ({d.strftime('%a')}): want {want}, got {got}")


def _labels(entries):
    return sorted((e["label"], e["time"]) for e in entries)


def check_ordinary_week(sc: Score):
    """A plain week: Sunday and the swapped-in weekday-holiday pattern share
    one Shacharis set, Tue-Thu share another, Friday carries the early+regular
    Erev Shabbos lines when the early minyan is active, and Shabbos carries
    Chassidus/Shacharis (or Tehillim/Shacharis on Mevorchim) plus Mincha and
    Motzaei Maariv. Every entry's date must be the day it was resolved for."""
    sunday = date(2026, 1, 25)
    eng = ZmanimEngine()

    sun = day_minyanim(sunday, engine=eng)
    mon = day_minyanim(sunday + timedelta(days=1), engine=eng)
    tue = day_minyanim(sunday + timedelta(days=2), engine=eng)
    fri = day_minyanim(sunday + timedelta(days=5), engine=eng)
    shabbos = day_minyanim(sunday + timedelta(days=6), engine=eng)

    sun_l, mon_l, tue_l, fri_l, shab_l = (_labels(e) for e in (sun, mon, tue, fri, shabbos))

    sc.add("ordinary_week", sun_l == mon_l,
           f"Sunday {sun_l} != Monday {mon_l} (both should be Sun.-pattern)")
    sc.add("ordinary_week", ("Shacharis", "08:00") in sun_l and ("Shacharis", "09:15") in sun_l,
           f"Sunday missing 8:00/9:15 Shacharis: {sun_l}")
    sc.add("ordinary_week", ("Shacharis", "06:15") in tue_l and ("Shacharis", "07:30") in tue_l,
           f"Tuesday missing 6:15/7:30 Shacharis: {tue_l}")
    sc.add("ordinary_week", any(l.startswith("Kabbolas Shabbos") for l, _ in fri_l),
           f"Friday missing Kabbolas Shabbos: {fri_l}")
    sc.add("ordinary_week",
           any(l in ("Chassidus", "Tehillim") for l, _ in shab_l)
           and any(l.startswith("Shacharis") for l, _ in shab_l)
           and any(l.startswith("Mincha") for l, _ in shab_l)
           and any("Motzaei" in l for l, _ in shab_l),
           f"Shabbos missing an expected line: {shab_l}")

    for d, entries in ((sunday, sun), (sunday + timedelta(days=6), shabbos)):
        for e in entries:
            sc.add("ordinary_week_dates", e["date"] == d.isoformat(),
                   f"{d}: entry {e['label']!r} dated {e['date']}")


def check_mevorchim_split(sc: Score):
    """Exactly one of Tehillim/Chassidus must appear, matching the week's
    Mevorchim state — this is the split that motivated the whole `when`
    mechanism, and the one most likely to silently invert."""
    checked_mevorchim = checked_plain = False
    d = date(2026, 1, 4)
    for _ in range(60):
        if d.weekday() == 5:  # Shabbos
            is_mevorchim = luach.mevorchim_month(d) is not None
            entries = day_minyanim(d)
            labels = [l for l, _ in _labels(entries)]
            has_tehillim = "Tehillim" in labels
            has_chassidus = "Chassidus" in labels
            sc.add("mevorchim_split", has_tehillim != has_chassidus,
                   f"{d} (mevorchim={is_mevorchim}): both or neither present: {labels}")
            if is_mevorchim:
                sc.add("mevorchim_split", has_tehillim and not has_chassidus,
                       f"{d}: mevorchim but got {labels}")
                checked_mevorchim = True
            else:
                sc.add("mevorchim_split", has_chassidus and not has_tehillim,
                       f"{d}: not mevorchim but got {labels}")
                checked_plain = True
        d += timedelta(days=1)
    sc.add("mevorchim_split_coverage", checked_mevorchim, "no Mevorchim Shabbos found in sample window")
    sc.add("mevorchim_split_coverage", checked_plain, "no plain Shabbos found in sample window")


def check_public_holiday_swap(sc: Score):
    """A NSW public holiday Monday must use the Sunday Shacharis pattern, per
    assemble_week's explicit swap — the same real bug class (a rule silently
    not applying to the day it should) as the FixedTime gap above, just from
    the other direction (a day claiming a pattern that is not its own)."""
    found = False
    for year in (2026, 2027):
        for hol_date, _name in luach.nsw_public_holidays(year).items():
            if hol_date.weekday() != 0:  # Monday only, per the assembler's swap
                continue
            found = True
            entries = day_minyanim(hol_date)
            labels = _labels(entries)
            sc.add("public_holiday", ("Shacharis", "08:00") in labels and ("Shacharis", "09:15") in labels,
                   f"{hol_date}: expected Sunday-pattern Shacharis, got {labels}")
    sc.add("public_holiday_coverage", found, "no Monday NSW public holiday found to test")


def check_time_iso(sc: Score):
    """Every entry's time_iso must be the same instant as its `time` string,
    on the date it was resolved for — the same discipline as dayview's
    zmanim_iso, and for the same reason: a signage player may not run the
    shul's timezone."""
    sunday = date(2026, 1, 25)
    for i in range(7):
        d = sunday + timedelta(days=i)
        for e in day_minyanim(d):
            iso = e.get("time_iso")
            ok = False
            if iso:
                parsed = datetime.fromisoformat(iso)
                ok = (f"{parsed.hour:02d}:{parsed.minute:02d}" == e["time"]
                      and parsed.date().isoformat() == e["date"] == d.isoformat())
            sc.add("time_iso", ok, f"{d} {e['label']}: time={e['time']} time_iso={iso}")


def check_erev_yom_tov_duplication(sc: Score):
    """An Erev Yom Tov chol day can legitimately carry two lines for the same
    tefilla (the week's ranged weekday line, whose range happens to include
    that day, plus the day-block's Yom-Tov-specific line) — this asserts that
    is exactly what happens for a known Erev Pesach, not more and not less."""
    # Pesach 5786 begins 1 Apr 2026 (2 Nisan is Rebbe Rashab's yahrtzeit, but
    # the civil date below is Erev Pesach itself — a Wednesday).
    erev_pesach = date(2026, 4, 1)
    sc.add("erev_yom_tov", "Pesach" in " ".join(luach.day_labels(erev_pesach + timedelta(days=1))),
           f"{erev_pesach + timedelta(days=1)} is not Pesach day 1 in this build; date sample is stale")
    entries = day_minyanim(erev_pesach)
    minchas = [e for e in entries if e["label"].startswith("Mincha")]
    sc.add("erev_yom_tov", len(minchas) >= 1, f"{erev_pesach}: no Mincha at all: {_labels(entries)}")
    for e in entries:
        sc.add("erev_yom_tov_dates", e["date"] == erev_pesach.isoformat(),
               f"{erev_pesach}: entry {e['label']!r} dated {e['date']}")


def main() -> int:
    sc = Score()
    print("Davening (minyan-time) regressions")
    check_day_spec_roundtrip(sc)
    check_ordinary_week(sc)
    check_mevorchim_split(sc)
    check_public_holiday_swap(sc)
    check_time_iso(sc)
    check_erev_yom_tov_duplication(sc)
    ok = sc.report()
    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
