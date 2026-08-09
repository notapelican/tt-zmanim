"""Regressions for the display-screen layer: Hebrew-letter rendering, the
Chabad-days table, and the per-day view.

Run:  python3 engine/validate_dayview.py   (exits nonzero on regression)

Two things are checked that matter more than the rest:

1. **The day view cannot disagree with a printed sheet.** Every zman it publishes
   is re-derived from the same `ZmanimEngine` method the sheets use and compared
   string-for-string, so a formatting or rounding drift in the display layer is a
   test failure rather than a discrepancy on a wall.
2. **Chabad dates round-trip.** Each entry resolves to a civil date whose Hebrew
   date is the one the table claims — including Adar II in a leap year, which is
   the case a hand-written table gets wrong.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta

from . import chabad, hebcal
from .dayview import day_view, day_views
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
            if len(self.failures) > 40:
                print(f"  ... and {len(self.failures) - 40} more")
        return not self.failures


# --- Hebrew numerals ---------------------------------------------------------

# Hand-checked. The interesting ones: 15 and 16 must never be יה/יו (they spell
# divine names), and 500+ repeats ת because 400 is the largest single letter.
NUMERALS = {
    1: "א׳", 5: "ה׳", 9: "ט׳", 10: "י׳", 11: "י״א",
    14: "י״ד", 15: "ט״ו", 16: "ט״ז", 17: "י״ז", 18: "י״ח",
    19: "י״ט", 20: "כ׳", 24: "כ״ד", 25: "כ״ה", 28: "כ״ח", 29: "כ״ט",
    30: "ל׳", 100: "ק׳", 400: "ת׳", 500: "ת״ק", 700: "ת״ש",
    786: "תשפ״ו", 787: "תשפ״ז", 900: "תת״ק",
}


def check_numerals(sc: Score):
    for n, want in NUMERALS.items():
        got = hebcal.hebrew_numeral(n)
        sc.add("hebrew_numerals", got == want, f"{n}: {got!r} != {want!r}")

    for bad in (0, -1, 1000):
        try:
            hebcal.hebrew_numeral(bad)
            sc.add("hebrew_numerals", False, f"{bad} should have raised")
        except ValueError:
            sc.add("hebrew_numerals", True)

    # 15 and 16 must not contain the yud-heh / yud-vav spellings, at any scale.
    for n in (15, 16, 115, 315, 516):
        body = hebcal.hebrew_numeral(n, punctuate=False)
        sc.add("hebrew_numerals", "יה" not in body and "יו" not in body,
               f"{n} renders as {body!r}")


DATE_LETTERS = {
    # (hebrew year, month, day): expected rendering
    (5786, "Shevat", 10): "י׳ שבט תשפ״ו",
    (5786, "Teves", 24): "כ״ד טבת תשפ״ו",
    (5786, "Kislev", 19): "י״ט כסלו תשפ״ו",
    (5786, "Nisan", 11): "י״א ניסן תשפ״ו",
    (5786, "Av", 20): "כ׳ מנחם־אב תשפ״ו",
    (5786, "Marcheshvan", 20): "כ׳ מרחשון תשפ״ו",
    (5786, "Elul", 18): "י״ח אלול תשפ״ו",
    (5787, "Adar I", 25): "כ״ה אדר א׳ תשפ״ז",
    (5787, "Adar II", 25): "כ״ה אדר ב׳ תשפ״ז",
}


def check_date_letters(sc: Score):
    for (hy, month, day), want in DATE_LETTERS.items():
        d = hebcal.from_hebrew(hy, month, day)
        got = hebcal.hebrew_date_letters(d)
        sc.add("hebrew_dates", got == want, f"{hy} {month} {day}: {got!r} != {want!r}")

    # Thousands prefix, used where the full year is spelled out.
    got = hebcal.hebrew_year_letters(5786, with_thousands=True)
    sc.add("hebrew_dates", got == "ה׳תשפ״ו", f"5786 with thousands: {got!r}")


# --- Chabad days -------------------------------------------------------------

def check_chabad(sc: Score):
    # Cover a leap year and a non-leap year, and a run of both.
    for hy in range(5784, 5796):
        leap = hebcal.is_leap(hy)
        days = chabad.chabad_days(hy)
        entries = [e for v in days.values() for e in v]

        sc.add("chabad_count", len(entries) == len(chabad.DAYS),
               f"{hy}: {len(entries)} entries for {len(chabad.DAYS)} table rows")

        for d, es in days.items():
            for e in es:
                h = hebcal.to_hebrew(d)
                sc.add("chabad_roundtrip",
                       h.day == e["hebrew_day"] and h.month_name == e["hebrew_month"],
                       f"{hy} {e['name']}: {d} is {h.day} {h.month_name}, "
                       f"table says {e['hebrew_day']} {e['hebrew_month']}")
                sc.add("chabad_fields",
                       bool(e["name"] and e["hebrew"] and e["description"] and e["kind"]),
                       f"{hy} {e['name']}: empty field")
                # for_date must agree with the table it came from.
                sc.add("chabad_for_date",
                       any(x["name"] == e["name"] for x in chabad.for_date(d)),
                       f"{hy} {e['name']}: for_date({d}) missed it")

        # Adar entries must land in Adar II in a leap year, plain Adar otherwise.
        for e in entries:
            if e["hebrew_month"].startswith("Adar"):
                want = "Adar II" if leap else "Adar"
                sc.add("chabad_adar", e["hebrew_month"] == want,
                       f"{hy} (leap={leap}) {e['name']}: in {e['hebrew_month']}, want {want}")

    # Chai Elul is written by its idiom, not its numeral.
    chai = [e for e in (chabad.for_date(hebcal.from_hebrew(5786, "Elul", 18)))
            if e["name"] == "Chai Elul"]
    sc.add("chabad_hebrew", bool(chai) and chai[0]["hebrew"] == "ח״י אלול",
           f"Chai Elul renders as {chai[0]['hebrew']!r}" if chai else "Chai Elul missing")

    # Unconfirmed entries must be filterable, since a display may refuse to show
    # a date that has no citation.
    all_days = chabad.chabad_days(5786)
    confirmed_only = chabad.chabad_days(5786, include_unconfirmed=False)
    n_all = sum(len(v) for v in all_days.values())
    n_conf = sum(len(v) for v in confirmed_only.values())
    n_unconf = sum(1 for e in chabad.DAYS if not e.confirmed)
    sc.add("chabad_unconfirmed", n_all - n_conf == n_unconf,
           f"{n_all} - {n_conf} != {n_unconf} unconfirmed rows")

    # Every confirmed row must cite something.
    for e in chabad.DAYS:
        if e.confirmed:
            sc.add("chabad_sources", bool(e.source),
                   f"{e.name}: confirmed with no source")


# --- Day view ----------------------------------------------------------------

def check_dayview(sc: Score):
    eng = ZmanimEngine()
    # A spread that includes Shabbos, a fast, yom tov, the Omer, a DST changeover
    # and a leap-year Adar.
    starts = (date(2026, 1, 25), date(2026, 4, 1), date(2026, 8, 9),
              date(2026, 10, 4), date(2027, 3, 28))
    for start in starts:
        for i in range(7):
            d = start + timedelta(days=i)
            v = day_view(d, engine=eng)

            sc.add("dayview_date", v["date"] == d.isoformat(), f"{d}: {v['date']}")

            # Every published zman must equal the engine's own value, formatted
            # the same way. This is the guard against a display-layer drift.
            for key, method in (("alos", "alos"), ("netz", "netz"),
                                ("sof_zman_shema", "sof_zman_shema"),
                                ("shkia", "shkia"), ("tzeis", "tzeis"),
                                ("chatzos_halayla", "chatzos")):
                dt = getattr(eng, method)(d)
                want = f"{dt.hour:02d}:{dt.minute:02d}"
                sc.add("dayview_zmanim", v["zmanim"].get(key) == want,
                       f"{d} {key}: {v['zmanim'].get(key)} != {want}")

            # Which side of midnight chatzos halayla falls on is seasonal, not
            # fixed: under DST solar noon is ~12:45–13:15 so chatzos lands after
            # midnight, but on standard time it can be ~23:45 — the same civil
            # day. (Sydney's DST ends 5 Apr 2026, and that week is in the sample
            # precisely because it catches this.) So the flag must track the real
            # datetime rather than a rule of thumb. A consumer that assumed
            # "chatzos is always tomorrow" would be wrong for months at a time.
            flagged = "chatzos_halayla" in v["zmanim_next_day"]
            actually_next = eng.chatzos(d).date() != d
            sc.add("dayview_next_day", flagged == actually_next,
                   f"{d}: flagged next-day={flagged}, engine says {eng.chatzos(d)}")

            # The Hebrew block must agree with hebcal.
            h = hebcal.to_hebrew(d)
            sc.add("dayview_hebrew",
                   v["hebrew"]["day"] == h.day and v["hebrew"]["month"] == h.month_name
                   and v["hebrew"]["letters"] == hebcal.hebrew_date_letters(d),
                   f"{d}: {v['hebrew']}")

            # A parsha is always named: the sheets title every week by one, using
            # the deferred sedra on a festival week.
            sc.add("dayview_parsha", bool(v["parsha"]), f"{d}: no parsha")

            # Shabbos-only keys appear only on Shabbos.
            is_shabbos = d.weekday() == 5
            sc.add("dayview_shabbos", ("shabbos_labels" in v) == is_shabbos,
                   f"{d}: shabbos_labels present={('shabbos_labels' in v)}, "
                   f"is_shabbos={is_shabbos}")

    # Range covers every day inclusive, in order.
    doc = day_views(date(2026, 8, 9), date(2026, 8, 15))
    sc.add("dayview_range", len(doc["days"]) == 7, f"{len(doc['days'])} days for a week")
    sc.add("dayview_range",
           [x["date"] for x in doc["days"]]
           == [(date(2026, 8, 9) + timedelta(days=i)).isoformat() for i in range(7)],
           "range days out of order or wrong")

    # Yud Shevat 5786 must surface as a Chabad day on the right civil date.
    v = day_view(date(2026, 1, 28), engine=eng)
    sc.add("dayview_chabad",
           any(e["name"] == "Yud Shevat" for e in v["chabad"]),
           f"10 Shevat 5786: chabad={v['chabad']}")


def main() -> int:
    sc = Score()
    print("Display-layer regressions (hebrew letters / chabad days / day view)")
    check_numerals(sc)
    check_date_letters(sc)
    check_chabad(sc)
    check_dayview(sc)
    ok = sc.report()
    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
