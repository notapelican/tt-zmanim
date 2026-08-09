# TTCC Zmanim Timesheet Generator

## ⚠ Follow-ups needed (action required)

- [x] **Confirm chabad.org's exact Sydney coordinate/elevation** — ✅ resolved
  (2026-07-14) against 8 chabad.org Sydney readouts (locationId 523, ~100 readings,
  Jul–Oct 2026 incl. DST): coordinate **(−33.88, 151.22) at SEA LEVEL** (the fitted 10 m
  elevation was an artifact), motzaei tzeis is the standard **8.5°** (the 8.4° fit was an
  artifact of assuming ceil display rounding — chabad displays nearest), and the sheets
  copy chabad's *displayed* per-row roundings (documented in `engine/zmanim.py`).
  The engine now reproduces 94/98 of the readings exactly; the 4 misses are raw values
  within ~5 s of a minute boundary.
- [ ] **Rov's written sign-off** on the recovered definitions and the confirmed-errata
  rulings (Tishrei Shema outliers, 9 Av am/pm slip) listed in `phase0/PHASE0-FINDINGS.md`.
  (The 8.4°-vs-8.5° question is now settled empirically at 8.5° — see above.)
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
- `RENDERER-CONTRACT.md` — field-by-field spec of the generated block data;
  the .docx/PDF renderer (next session) is built from this document alone.
- `phase0/` — fixture corpus (all 27 historical sheets transcribed to JSON), extraction
  and fitting scripts (`fit_zmanim.py` for zmanim, `fit_rules.py` for minyan rules),
  and `PHASE0-FINDINGS.md` (recovered zmanim definitions + errata).
- `phase3/PHASE3-FINDINGS.md` — recovered schedule rules (minyan-time policies),
  seasonal-profile conditions, and the triage of every residual.
- `engine/` — Phase 1+ code:
  - `solar.py` — NOAA solar calculator (KosherJava-compatible).
  - `zmanim.py` — zmanim engine (Baal HaTanya definitions, explicit rounding policies).
  - `hebcal.py` — Hebrew calendar core (year arithmetic, Hebrew↔civil, molad),
    plus Hebrew-letter rendering (gematria numerals, Chabad month names,
    Adar I/II) for the display screens — `hebrew_date_letters()` gives
    `ה׳ מנחם־אב תשפ״ו`.
  - `chabad.py` — the canonical Chabad-days table (25 dates: the Rebbeim's
    yahrtzeits and birthdays, the liberations, Didan Notzach, Chai Elul …) with a
    **source per date** and Adar dates resolving to Adar II in a leap year.
    Deliberately separate from `luach.holidays()`, which feeds the printed
    sheets: the sheets mark only five of these, and folding twenty more labels
    into `holidays()` would silently change what prints.
  - `luach.py` — luach layer: diaspora parsha cycle (doubled sedras, Chazak),
    special Shabbosos, yomim tovim, fasts (with commencement kinds), Rosh Chodesh
    & molad announcements, Omer, Pirkei Avos (Chabad cycle), DST detection,
    NSW public holidays.
  - `rules.py` — schedule-rules engine: `ScheduleProfile` (seasonal minyan sets
    with date-range/DST/zman activation conditions), `ScheduleRule` (zman-anchored
    with rounding + halachic bound / fixed-clock / manual override — overrides
    always win), `NoteTemplate`, `Timesheet`.
  - `assemble.py` — `generate(start, end)`: combines zmanim + luach + rules into
    plain-data week/day blocks (no layout/styling; see RENDERER-CONTRACT.md).
  - `highlights.py` — per-week Shabbos/Yom Tov headline times (candle lighting,
    Shabbos/YT ends, fast begin/end) extracted from the assembled blocks for the
    public banner widget and the piSignage Shabbos screen; served by the
    service's `/highlights` endpoint.
  - `dayview.py` — per-day payload for the display screens (zmanim + luach +
    Hebrew date + Chabad days), served by `/day`. Neutral, not display-shaped;
    the screens compose their own panes. Two deliberate omissions: candle
    lighting (ask `/highlights`, so one number has one source) and mincha gedola
    (no such zman exists in the engine — adding one is a halachic decision, not a
    formatting one). Publishes `chatzos` as **`chatzos_halayla`**, since in this
    engine it is halachic midnight, and lists which zmanim fall on the next civil
    date — which side of midnight chatzos halayla lands on is seasonal.
  - `validate.py` / `validate_luach.py` / `validate_rules.py` /
    `validate_dayview.py` — golden regressions
    against all 27 fixtures (Phase 1 zmanim: 782/895 exact with every residual
    triaged; Phase 2 luach: 352/352; Phase 3 schedule lines: 778/861 with every
    residual triaged, incl. seasonal-profile switching 59/62).
  - `render_html.py` — **primary renderer.** Turns `assemble.generate()`
    block data into self-contained HTML/CSS matching the house style (בס״ד
    header, blue/purple section bars, dotted leaders, boxed fast notices),
    choosing single-week / multi-week-two-column / yom-tov day-by-day layout
    from the data. Prints to PDF (and PNG) via headless Chromium and powers
    the in-plugin live preview + web surfaces. Layout-only; see
    RENDERER-CONTRACT.md. **Decision (2026-07-12):** HTML is the rendering
    target — editing happens in the plugin, so the export only has to look
    right (WARPLAN §2). CSS reaches the house style far more faithfully than
    hand-built OOXML; the docx path was trialled and demoted.
  - `render_docx.py` — optional secondary "Word copy" export (python-docx).
    Same block data, same shared line-merge/section-order logic. Requires
    `python-docx` (`pip install -r requirements.txt`).
- `wp-plugin/ttcc-zmanim/` — Phase 4 WordPress plugin (calls the sheet service;
  never recomputes a time). Surfaces:
  - the wp-admin dashboard / archive / schedule profiles / settings;
  - the front-end clergy generator, `[ttcc_generator]` — pick week(s), Classic or
    Modern, adjust times and add lines, then export a PDF, a 1:1 WhatsApp image
    (the sheet laid out on a square page, house layout unchanged), a 3:4 image or
    the WhatsApp text. No styling controls and no writes to the archive;
  - the read-only `[ttcc_week]` / `[ttcc_browse]` / `[ttcc_shabbos]` embeds and
    the piSignage screens.

  See `PHASE4-OPERATOR-GUIDE.md`.
- `samples/` — original PDFs.

## Running the golden regressions

```sh
python3 engine/validate.py         # zmanim engine; exits nonzero on regression
python3 engine/validate_luach.py   # luach layer; exits nonzero on regression
python3 engine/validate_rules.py   # schedule rules + profiles; exits nonzero on regression
python3 engine/validate_dayview.py # display layer: hebrew letters, chabad days, /day payload
```
