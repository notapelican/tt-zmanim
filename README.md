# TTCC Zmanim Timesheet Generator

## ⚠ Follow-ups needed (action required)

- [ ] **Confirm chabad.org's exact Sydney coordinate/elevation.** chabad.org is unreachable
  from the build sandbox, so the engine's location (`engine/zmanim.py`: −33.88, 151.22, 10 m)
  is fit-derived. This is the source of the remaining ±1-minute residuals in the golden
  regression. To close it: open chabad.org's zmanim page for Sydney and paste back either the
  coordinates it displays, or its printed times (candle lighting, shkia, tzeis, misheyakir,
  sof zman Shema) for 3–4 scattered dates (one summer Friday, one winter Friday, two weekdays).
- [ ] **Rov's written sign-off** on the recovered definitions — especially the **8.4°**
  motzaei Shabbos/YT tzeis (fits 78/79 vs. the standard 8.5°) and the confirmed-errata
  rulings (Tishrei Shema outliers, 9 Av am/pm slip) listed in `phase0/PHASE0-FINDINGS.md`.
  The warplan makes this the halachic gate: nothing ships without it.
- [x] **Confirm whether ttcc.info runs WordPress** — ✅ confirmed WordPress
  (2026-07-12): Phase 4 will be the WP-plugin route (WARPLAN.md §2, Option A).

Neither open item blocks Phases 3–4 (each is a one-line constant in
`engine/zmanim.py`), but **both must land before the Phase 5 pilot** — no sheet
is used in production without the confirmed coordinate and the Rov's sign-off.

Tracked as a GitHub issue as well; tick items off in both places.

---

Generates the weekly / yom-tov "times" sheets for the Tzemach Tzedek Community Centre
(Bondi, Sydney) per the Alter Rebbe's zmanim, matching the established TTCC sheet format.
See `WARPLAN.md` for the full plan and phase gates.

## Layout

- `WARPLAN.md` — plan, system design, phased delivery.
- `phase0/` — fixture corpus (all 27 historical sheets transcribed to JSON), extraction
  and fitting scripts, and `PHASE0-FINDINGS.md` (recovered zmanim definitions + errata).
- `engine/` — Phase 1+ code:
  - `solar.py` — NOAA solar calculator (KosherJava-compatible).
  - `zmanim.py` — zmanim engine (Baal HaTanya definitions, explicit rounding policies).
  - `hebcal.py` — Hebrew calendar core (year arithmetic, Hebrew↔civil, molad).
  - `luach.py` — luach layer: diaspora parsha cycle (doubled sedras, Chazak),
    special Shabbosos, yomim tovim, fasts (with commencement kinds), Rosh Chodesh
    & molad announcements, Omer, Pirkei Avos (Chabad cycle), DST detection,
    NSW public holidays.
  - `validate.py` / `validate_luach.py` — golden regressions against all 27 fixtures
    (Phase 1 zmanim: 782/895 exact with every residual triaged; Phase 2 luach: 352/352).
- `samples/` — original PDFs.

## Running the golden regressions

```sh
python3 engine/validate.py         # zmanim engine; exits nonzero on regression
python3 engine/validate_luach.py   # luach layer; exits nonzero on regression
```
