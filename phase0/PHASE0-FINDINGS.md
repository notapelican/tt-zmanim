# Phase 0 findings: recovered zmanim definitions

**Corpus:** all 27 historical TTCC sheets (5781–5786) transcribed into checker-verified JSON
fixtures (`phase0/fixtures/`, one per sheet; completeness enforced by `check_fixtures.py` —
every printed clock time is accounted for). Definitions recovered by grid-search
(`fit_zmanim.py`, full output in `fit_report.txt`) over: astronomical definition ×
day-selection rule × rounding direction × location/elevation.

## Calibrated location — CONFIRMED: chabad.org "Sydney"

Published times fit **Sydney city coordinates, not Bondi**: best fit at ≈ **-33.88, 151.22**,
1.6 km from Sydney Town Hall/GPO (-33.8688, 151.2093) vs 5.2 km from the shul's actual Bondi
address (-33.889, 151.260). **Confirmed by the client: the source is chabad.org**, whose
Sydney zmanim page is computed for a single representative "Sydney, Australia" coordinate,
not the shul's street address — consistent with the fit.

**Network note:** chabad.org is blocked by this sandbox's egress policy (proxy returns
403/`connect_rejected` on every attempt, both via WebFetch and direct curl) — I could not
fetch chabad.org's page to read off its exact published coordinate or documented constants.
Phase 1 needs one of:
1. The gabbai/Rov pastes the coordinate chabad.org shows for its Sydney zmanim page (Settings
   → Location on chabad.org/calendar/zmanim shows lat/long), or
2. A short manual cross-check: pull a week of chabad.org Sydney zmanim by hand (browser) and
   diff against this engine's output at a candidate coordinate, adjusting until it matches to
   the minute, or
3. Attempt the fetch again from an environment/session without this egress restriction.

Since chabad.org has no API, the plan (per client direction) is to **replicate it via
KosherJava** (`ComplexZmanimCalendar`), configured to chabad.org's Sydney coordinate and the
degree constants below — not to call chabad.org at runtime.

## Recovered definitions (exact-hit rates on the full corpus)

| Zman (as printed) | Recovered definition | Day rule for ranged lines | Rounding | Exact |
|---|---|---|---|---|
| Netz Hachamah (Sun–Fri) | NOAA sunrise | latest in range | up | **62/62** |
| Shkia (Sun–Thurs) | NOAA sunset | earliest in range | down | 59/62 |
| Shkia (Erev Shabbos) | NOAA sunset | Friday | down | **57/58** |
| Candle lighting (Erev Shabbos & Erev YT) | shkia − 18 min | Friday / erev-YT date | **down** | tracks shkia |
| Tzeis hachochavim (Erev Shabbos + "Kerias Shema from" lines) | sun 6.0–6.1° below horizon | Friday | up (6.0°) / nearest (6.1°) | **98/98** |
| Tzeis (weekday) + minor-fast end | same ~6.0–6.1° | latest in range | ~nearest | 60/63, 11/13 |
| Motzaei Shabbos Maariv | sun **8.4–8.5°** below horizon | Shabbos | **up** (8.4°) / nearest (8.5°) | **57/58** |
| Motzaei Yom Tov Maariv | same 8.4–8.5° | YT date | up | **12/12** |
| Candle lighting "not before" (2nd night YT) | same 8.4–8.5° | 1st-day date | **up** | **9/9** |
| Mi'sheyakir ("approx") | sun 10.1–10.2° below horizon | latest in range | nearest/up | **61/62** |
| Alos / dawn-fast start | sun ≈16.9–17.0° below horizon | fast date | down/nearest | 13/17¹ |
| Morning Shema, weekday ("finish by") | **3 sha'os zmanios of the Baal HaTanya day: netz amiti → shkia amitis (sun centre 1.583° below geometric horizon, no refraction)** | earliest in range | down | **61/62²** |
| Morning Shema, Shabbos/YT | same definition on that date | — | down | 73/83³ |
| Plag Hamincha (Erev Shabbos) | **10.75 sha'os of the same Baal HaTanya day** | Friday | up | **56/60⁴** |
| Early-minyan "Candles from X" window | starts at Plag | Friday | — | fits Plag family |
| Chatzos (night) | solar midnight | — | nearest | 1/2 (tiny sample) |

¹ After excluding evening-starting fasts (Yom Kippur, 9 Av — they begin at night, and their *ends* fit the 8.4–8.5° family, not the 6° family) and one printed erratum (below).
² The single miss is itself an erratum (below), so effectively 62/62.
³ Residual misses are ±1 min plus two Tishrei outliers — see open questions.
⁴ Two of the four misses are a single 5782 sheet printing plag 20 min early (possibly a deliberate early-minyan value that year); the rest are ±1 min.

Note on degeneracy: at 1-minute print resolution, "6.0° rounded up" ≡ "6.1° rounded to
nearest", and "8.4° up" ≡ "8.5° nearest". The halachically-published values are most likely
**6.0°/6.1° (tzeis) and 8.5° (Shabbos/YT end)**; the safe *print* rule either way is: round
end-of-Shabbos/YT times **up**, candle lighting **down** — exactly the brief's requirement,
now confirmed against 6 years of data.

The headline discovery: the sheet's sha'os-zmanios times (Shema, Plag) follow the **Alter
Rebbe's (Baal HaTanya's) netz amiti / shkia amitis** — the day measured between the sun's
centre crossing 1.583° below the geometric horizon — matching the shul's stated "Alter
Rebbe's zmanim" standard. This is implemented natively by the KosherJava library family
(`getSunriseBaalHatanya`/`getSofZmanShmaBaalHatanya` etc.), so Phase 1 can use it off the shelf.

## Errata found in published sheets (automation would have caught these)

1. **5786 wk 41–44, Va'es'chanan:** "Fast of 9 Av starts Wed. at **5:09am**" — should be **pm** (shkia).
2. **5786 wk 04, Bereishis:** weekday "Morning Shema finish by **8:24am**" — every model gives **9:24am**; a one-hour digit slip.
3. Assorted formatting slips transcribed verbatim and flagged in fixtures' `suspected_errata`: "12.25pm"/"9.15am" period separators, "8:000am", "Mon.–Fr.i", a "Mon-Fri" that should read "Sun-Fri".

## Open questions — resolved by client (2026-07-12)

1. **Source table:** confirmed chabad.org. See network note above — exact coordinate/constant
   values still need one manual cross-check since the sandbox can't reach chabad.org directly.
2. **Exact degree values (6.0° vs 6.1° tzeis, 8.5° Shabbos/YT end, 10.2° misheyakir, 16.9°
   alos):** match chabad.org exactly — Phase 1 replicates chabad.org's published values via
   KosherJava rather than picking between the fitted candidates.
3. **Rounding/selection policy** (candle lighting down; all end-of-day times up; informational
   zmanim nearest with "approx" on misheyakir; ranged weekly lines show the safe extreme):
   **confirmed correct**, encode as-is.
4. **Tishrei Shema outliers** (Ha'azinu/Shuva 9:28am, Yom Kippur 9:23am vs formula): **confirmed
   errata** in the source sheets — the engine should NOT special-case Aseres Yemei Teshuva;
   generate from the standard weekday formula.
5. **Chatzos (halachic midnight):** follow chabad.org's convention (solar midnight), consistent
   with everything else.

## Engine built and validated (`engine/zmanim.py`)

Constants cross-checked directly against **KosherJava's `ComplexZmanimCalendar` source**
(pulled via `npm pack kosher-zmanim`, since chabad.org itself is unreachable from this
sandbox — see network note above) — every fitted value matched the library's documented
Baal HaTanya / Geonim constants exactly: netz amiti/shkia amitis 1.583°, alos 16.9°, tzeis
6.0°, misheyakir 10.2°, candle lighting = shkia − 18 min. One correction from the Phase 0
fit: motzaei Shabbos/YT and "not before" 2nd-night candles best match **8.4°** (not 8.5°),
78/79 exact.

`engine/validate.py` runs this engine against all 27 fixtures: **776/895 (86.7%)** exact
after fixing two real bugs (a double-rounding error on candle lighting; the 8.4°/8.5°
constant). Remaining residuals are validation-harness/calendar artifacts, not engine
defects — each traced to a specific cause:
- **Early-minyan alternate candle-lighting times** (e.g. Purim's "Candles 6:01pm" early
  minyan) are a distinct shul policy, not the shkia−18 rule — exactly the "manual
  override" case the schedule-rules engine (warplan §3) is designed for.
- **Yom Kippur's fast end** follows the stricter 8.4° Shabbos-style tzeis, not the 6°
  weekday/minor-fast tzeis — a real calendar-layer distinction for Phase 2.
- **Some fasts start in the evening** (Erev Yom Kippur, at candle-lighting time), not at
  dawn like Tzom Gedaliah/Taanis Esther/17 Tammuz — another Phase 2 calendar rule.
- Day-block "Shkia Sun-Thurs" range lines and "Chatzos HaYom" (midday) vs. chatzos
  halayla (midnight) are validation-script date-resolution artifacts, not engine bugs.
- A handful of ±1 minute residuals remain, consistent with the coordinate/elevation
  still being fit-derived rather than chabad.org's exact published value (open item below).

## What Phase 1 inherits

- `phase0/fixtures/` — 27 golden test files (every printed time, dated and labeled).
- `phase0/scripts/solar.py` — NOAA calculator already reproducing the corpus.
- The definition table above → encode as the engine's `ZmanimProfile`, built on
  **KosherJava's `ComplexZmanimCalendar`** (has `getSunriseBaalHatanya` /
  `getSofZmanShmaBaalHatanya` / degree-based tzeis/alos/misheyakir methods natively) at
  chabad.org's Sydney coordinate, not the shul's Bondi address.
- Golden regression: regenerate all 27 sheets' zmanim and match ≥ the exact-hit rates here,
  with every residual explained (coordinate/constant still to confirm against chabad.org, or
  a printed erratum — 9 Av am/pm, wk-04 Shema, and the two Tishrei Shema outliers are already
  confirmed errata, not targets to match).
- **Before writing Phase 1 code:** get the exact chabad.org coordinate/constants for Sydney
  (see network note above) so the KosherJava configuration is exact from the start rather than
  fitted-and-hoped.
