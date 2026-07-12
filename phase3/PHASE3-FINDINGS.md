# Phase 3 findings: recovered schedule rules (minyan-time policies)

**Corpus:** every `minyan` entry in the weekly blocks of all 27 fixtures
(`phase0/fixtures/`), fitted by `phase0/scripts/fit_rules.py` the same way the
Phase 0/1 zmanim definitions were fitted. The recovered rules are encoded as
`DEFAULT_PROFILES` in `engine/rules.py` and regression-tested end-to-end by
`engine/validate_rules.py` (asserting baseline **777/861 = 90.2%** exact,
including seasonal-profile switching at 59/62).

## Recovered rules (exact-hit rates from validate_rules.py)

| Line | Recovered rule | Exact |
|---|---|---|
| Weekday Shacharis | fixed menu: Sun 8:00 & 9:15 (9:15 was **9:00 until 5783**); Mon–Fri 6:15 & 7:30; holiday-period third minyan 9:15 (9:45 in Jan 5786) | 231/234 |
| Weekday Mincha | **earliest shkia of the covered days − 10 min** (floor) | 52/72¹ |
| Weekday Maariv | **latest weekday tzeis (6°) of the covered days** (ceil) | 53/62² |
| Erev Shabbos Mincha | **candle lighting + 8 min** | 50/57³ |
| Kabbolas Shabbos (followed by Maariv) | **Friday tzeis (6°, ceil) − 10 min** — i.e. timed so the Maariv that follows lands at tzeis | 48/58³ |
| Early ES Mincha | **plag hamincha − 20 min** ("must be finished before Plag") | 25/26 |
| Early ES candle window | "not before" **plag**; "not after approx" **plag + 10** | 52/53 |
| Early ES Kabbolas Shabbos | **at plag** | 26/28 |
| Early ES kiddush/Shema lines | kiddush "before **tzeis − 30** or after **tzeis**"; Kerias Shema / kezayis "from/after **tzeis**" | 84/84 |
| Shabbos morning | Mevorchim → Tehillim **8:15** + Shacharis **10:10**; otherwise Chassidus **9:15** + Shacharis **10:00** | 109/116 |
| Shabbos Mincha | **shkia − 18 min snapped to the nearest 5-minute mark** | 43/56⁴ |
| Halacha shiur (Shabbos) | **Shabbos Mincha − 30 min** (= shkia − 48 on the same 5-min grid) | 24/32⁴ |
| Motzaei Shabbos Maariv | tzeis 8.4° (the Phase-1 zman, ceil) | 57/58 |

¹ ² ³ ⁴ — every miss triaged below.

## Seasonal profiles (activation conditions)

1. **`base`** — always active: the fixed Shacharis sets, weekday Mincha/Maariv,
   regular Erev Shabbos lines, Shabbos-day lines.
2. **`early_erev_shabbos`** — the early Erev Shabbos Mincha / candles-from-plag /
   Kabbolas Shabbos minyan. Condition recovered from the corpus: **Friday plag
   ≥ 5:50pm** (17:50 separates every season-boundary week: last-on 2026-03-20
   plag 17:54, first-off 2026-03-27 plag 17:46; earliest-on 2021-10-15 plag
   17:51). All qualifying weeks are DST weeks. **59/62 agreement**; all 3
   mismatches are sheets *without* the section on qualifying weeks:
   - 5783 wk 04 (2022-10-21, plag 17:55) and 5786 wk 04 (2025-10-17, plag
     17:52): the first qualifying week after Tishrei — the 5786 sheet prints
     "The Erev Shabbos early minyan … will resume next week", i.e. a deliberate
     one-week deferral, modeled as a per-sheet suppression (not a rule).
   - 5785 wk 15 (2025-01-10): mid-January school-holiday sheet that dropped the
     section (its regular Mincha 7:45pm even precedes candle lighting) — an
     override-heavy holiday sheet.
3. **`halacha_shiur_season`** — the Shabbos-afternoon halacha shiur. Condition:
   **DST in effect** — a longer window than the plag condition (late-March
   sheets keep the shiur after the early minyan has stopped; winter sheets
   never print it). First-DST-week sheets sometimes defer it together with the
   early minyan (same resume-lag suppression).
4. **`summer_holidays`** (default window **14 Dec – 27 Jan**, operator-adjusted
   yearly): adds fixed **Mincha 2:00pm** and **Maariv 9:00pm**. See "sporadic
   extras" below — this is the one profile whose activation the corpus does
   *not* pin to a clean condition.

Public holidays: on a Mon–Fri NSW public holiday the sheets move Shacharis to
the **Sunday schedule** (confirmed on Australia Day 2026, Easter/Anzac 2026,
King's Birthday 2026 sheets). The assembler implements this via
`luach.nsw_public_holidays` (day_spec adjustment + a note).

## Residual triage (every class of miss, with counts)

**±1–2 minute "nice number" nudges (≈33 lines across all zman-anchored
families).** The gabbai frequently rounds a computed time to a 5-minute mark:
every ±1/±2 Kabbolas-Shabbos miss (10/10), every ±1 Erev-Shabbos-Mincha miss
(5/7), and most weekday Mincha/Maariv ±1 misses land exactly on :x0/:x5. These
are cosmetic per-sheet edits of the true rule value — precisely the
manual-override case the data model keeps editable (`source: "override"`).

**±5-minute Shabbos-Mincha grid nudges (13 + 8 halacha-shiur lines).** Shabbos
Mincha itself sits on a 5-minute grid, so its overrides show as ±5; the
halacha shiur moves in lock-step (always Mincha − 30, including when Mincha is
nudged — corroborating the −30 link).

**Fast-day / special-day weekday lines (≈10 lines).** Erev-fast and fast-day
Mincha/Maariv (Taanis Esther 4:30pm, erev 9 Av 4:30pm, 9 Av day 3:45pm, Purim
Maariv 8:30pm with Megillah, Erev Pesach adjustments) are event-specific
overrides, not derivable from the weekly rules; they belong to the yom-tov/fast
day-block layer where sheets are edited per event.

**Sporadic summer extras (6 lines).** The fixed 2:00pm Mincha also appears on
March-2025, late-Nov-2025 and June-2026 sheets — outside any consistent date
window (and the 9:00pm Maariv's window differs from the 2:00pm Mincha's even
within one sheet-run). Recommendation (implemented): keep `summer_holidays` as
a profile with an operator-set date range defaulting to the school-holiday
window; treat out-of-window appearances as per-sheet additions. No calendar
condition explains them.

**Chanukah Fridays (4 lines).** When Erev Shabbos is Chanukah, the early
section is restructured (Chanukah lighting at plag, Shabbos candles at the
regular time, Kabbolas Shabbos 7:30pm fixed) and the weekday line becomes
"Mincha and Chanukah candles in shule". A Chanukah variant of the Erev-Shabbos
sections is Phase-4 dashboard work; per-sheet override until then.

**One-off specials (7 lines).** Bereishis 5782 double Shacharis (9:30 inside /
10:30 outside — COVID era), Pesach-week Shacharis 7:00am "note early start",
Selichos-week Tehillim 8:30 + Shacharis 10:10 on a non-Mevorchim Shabbos,
Shabbos-Shacharis printed 10:15 instead of 10:10 (twice), early-ES Mincha 3:00pm
"note early start time", 5785-wk15 holiday-sheet Erev Shabbos Mincha 7:45pm.

**Data corrections found:** 9 Av's fast *end* matches the 6° weekday tzeis
(5786: printed 5:37pm = tzeis 6°), not the 8.4° family — only Yom Kippur ends
at 8.4°. (Phase 0's note that evening-starting fasts end at 8.4° was right for
YK only.)

## What the renderer/dashboard inherits

- `engine/rules.py` — data model: `ScheduleRule` (zman-anchored with explicit
  rounding/grid + halachic `Bound`, fixed-clock, or manual), `ScheduleProfile`
  (+ `Condition`: date range / DST / zman comparison / boolean combinators),
  `NoteTemplate`, `Timesheet`, `apply_overrides` (overrides always win;
  edited lines keep their bound so the editor can warn — never block — when an
  edit crosses it).
- `engine/assemble.py` — `generate(start, end)` → plain-data week/day blocks
  (structure specified field-by-field in `RENDERER-CONTRACT.md`).
- `engine/validate_rules.py` — asserting golden regression (baseline 777).
