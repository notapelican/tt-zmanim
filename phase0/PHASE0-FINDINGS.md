# Phase 0 findings: recovered zmanim definitions

**Corpus:** all 27 historical TTCC sheets (5781–5786) transcribed into checker-verified JSON
fixtures (`phase0/fixtures/`, one per sheet; completeness enforced by `check_fixtures.py` —
every printed clock time is accounted for). Definitions recovered by grid-search
(`fit_zmanim.py`, full output in `fit_report.txt`) over: astronomical definition ×
day-selection rule × rounding direction × location/elevation.

## Calibrated location

Published times fit **Sydney city coordinates, not Bondi**: best fit at ≈ **-33.88, 151.22**
(Sydney CBD/Observatory area), with a small (~10 m) elevation-equivalent offset on
sunrise/sunset. Conclusion: the shul's times are copied/derived from a Sydney-wide luach
(plausibly chabad.org's Sydney zmanim or a communal Sydney table), not computed for the
shul's own street address. **Ask the gabbai which table/site is the source** — Phase 1 then
replicates that source's exact chain instead of approximating it.

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

## Open questions for the Rov / gabbai (Phase 0 gate)

1. **Which published table is the source?** (chabad.org Sydney / printed communal luach /
   other). This pins the last ±1-min residuals — different sites round hidden intermediate
   values differently.
2. Confirm the intended published values: tzeis 6.0° vs 6.1°; Shabbos/YT end 8.5°;
   misheyakir 10.2°; alos 16.9°.
3. Confirm the print-rounding policy as implemented: candle lighting **down**, all
   end-of-day/"not before" times **up**, informational zmanim nearest (with "approx" on
   misheyakir), weekly ranged values take the safe end of the range (latest netz/misheyakir,
   earliest shkia).
4. The 5785 Tishrei sheet's Ha'azinu/Shuva Shabbos Shema (9:28) and Yom Kippur Shema (9:23)
   don't fit the weekday formula (−55 min / +4 min) — different convention for those days,
   or errata?
5. Two chatzos samples disagree by a minute — trivial, but confirm solar-midnight convention.

## What Phase 1 inherits

- `phase0/fixtures/` — 27 golden test files (every printed time, dated and labeled).
- `phase0/scripts/solar.py` — NOAA calculator already reproducing the corpus.
- The definition table above → encode as the engine's `ZmanimProfile`, then the golden
  regression is: regenerate all 27 sheets' zmanim and match ≥ the exact-hit rates here,
  with every residual explained (source-table quirk or printed erratum).
