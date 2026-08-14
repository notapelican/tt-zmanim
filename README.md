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

---

## Shipping: three independent levers

This repo is easy to misread as "the timesheets plugin". It is three separate
things that ship three separate ways, and **the screens are a fourth thing in
another repo**. Nothing here has to move in step with anything else.

| What changed | What ships | How |
|---|---|---|
| `engine/` or `service/` | the **Cloud Run service** | merge to `main`, then `gcloud run deploy`. **No tag.** |
| `wp-plugin/ttcc-zmanim/` | the **timesheets plugin** | bump its version, tag `v…`, push the tag |
| Nothing here — `notapelican/ttcc-display` | the **display plugin** (the screens) | bump its version, tag `v…` in *that* repo |

**The trap:** the release workflow in this repo fires on any `v*` tag and builds
a **timesheets plugin** release. So never tag this repo just because you deployed
the service — you would publish a plugin update nobody asked for. Deploying the
service involves no tag at all.

### Deploying the service (engine changes)

Adding an endpoint or changing a zman means a service deploy. There is only ever
**one** service; you are replacing its code, never creating a second one.

```sh
git checkout main && git pull                  # 1. get the merged code
python3 engine/validate.py && python3 engine/validate_luach.py \
  && python3 engine/validate_rules.py && python3 engine/validate_dayview.py   # 2. must pass
gcloud run services list                       # 3. find your region if unsure
gcloud run deploy ttcc-sheet-service --source . --region <region> \
  --allow-unauthenticated --memory 2Gi --cpu 1 --concurrency 4 \
  --min-instances 0 --max-instances 2 --timeout 120
```

**Do not pass `--set-env-vars` on a redeploy.** On an existing service that flag
*replaces* the whole environment, so it would wipe or rotate
`TTCC_SERVICE_TOKEN` and break both plugins until you updated their settings.
Leaving it off keeps the existing values. Only include it when you genuinely mean
to change the token — and then update both plugins' settings pages.

Check it worked:

```sh
SVC=$(gcloud run services describe ttcc-sheet-service --region <region> --format='value(status.url)')
curl -s "$SVC/health"
```

`engine_version` in the response should match your latest commit. A stale value
means the new revision is not serving yet.

Nothing else is needed: both plugins call the service live, so a deploy reaches
the screens and the sheets within their normal cache window.

### Releasing the timesheets plugin (`wp-plugin/` changes only)

```sh
# 1. bump BOTH the Version: header and TTCC_ZMANIM_VERSION
#    in wp-plugin/ttcc-zmanim/ttcc-zmanim.php, then commit
git tag v0.7.0 && git push origin v0.7.0        # 2. tag must match that version
```

The GitHub Action builds the plugin zip and attaches it to the release; the site
then offers the usual one-click update. Full detail and the failure modes are in
[`RELEASING.md`](RELEASING.md).

The version you tag must be **higher** than what is installed, or the update will
not register.
