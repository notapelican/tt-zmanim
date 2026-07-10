# Warplan: TTCC Zmanim Timesheet Generator

**Client:** Tzemach Tzedek Community Centre, 1 Penkivil St, Bondi, NSW (Sydney, Australia)
**Goal:** Software that generates the weekly/yom-tov "times" sheets on demand, calculated per the Alter Rebbe's zmanim, editable in a dashboard and in regular word-processing software (Word), matching the established TTCC format.

This plan is based on analysis of 27 historical sheets (5781–5786) supplied in `Times.zip`.

---

## 1. What the historical sheets show

Three document formats are in use, all sharing the same building blocks:

1. **Single-week sheet** (e.g. `5786 times -wk 04`): one column/page, one Shabbos.
2. **Multi-week sheet** (e.g. `5786 times -wk 41 to 44`): 2–4 weeks in a two-column layout, one "week block" per parsha.
3. **Yom tov schedule** (e.g. Pesach, Tishrei, Purim): day-by-day blocks with holiday-specific items (Bedikas Chometz, Eruv Tavshilin, chometz deadlines, Yizkor, Seudas Moshiach, Omer counts, fast times, all-night learning, Kinus Torah, etc.).

### Anatomy of a week block

| Section | Contents | Source |
|---|---|---|
| Header | "The week of Parshas X:", Hebrew date range, civil date range | Calendar engine |
| Weekly zmanim | Mi'sheyakir ("approx"), Netz Hachamah, Morning Shema ("finish by"), Shkia (Sun–Thurs), Tzeis (Sun–Thurs) | Zmanim engine |
| Weekday davening | Shacharis minyanim (varies Sun vs Mon–Fri vs public holidays), Mincha, Maariv | Rules engine + overrides |
| Shabbos header | "Shabbos kodesh: [Parsha][, Mevorchim][, Chazak][, special Shabbos name e.g. Chazon/Nachamu]" | Calendar engine |
| Erev Shabbos key times | Plag Hamincha, Shkia, Tzeis hachochavim | Zmanim engine |
| Erev Shabbos schedule | Candle lighting, Mincha, Kabbolas Shabbos followed by Maariv | Zmanim + rules |
| Shabbos day | Tehillim 8:15am (Mevorchim) *or* Chassidus 9:15am; Morning Shema "finish by"; Shacharis 10:00/10:10/10:15; Molad + Rosh Chodesh announcement (Mevorchim only); Mincha with Pirkei Avos chapter (Pesach→Rosh Hashanah) and Seder Nigunim; Motzaei Shabbos Maariv | All three + fixed policies |
| Interleaved items | Fast-day boxes (start/end), Rosh Chodesh notes, Omer day numbers, DST changeover warnings, public holiday notes, Kiddush-window note (fixed text, DST/EST variants, per Mogen Avrohom & Alter Rebbe SA O.C. 271), free-text announcements | Calendar engine + notes library + free text |

### Observed calculation conventions (to be confirmed in Phase 0)

- **Candle lighting (erev Shabbos):** shkia − 18 min, **rounded down** to the minute.
- **Candle lighting 2nd night YT / motzaei Shabbos that is YT:** printed as "not before X", **rounded up** to the minute (e.g. 1st day Pesach → "not before 7:26pm").
- **Havdalah / Motzaei Shabbos Maariv:** later than weekday tzeis (samples show ~39–43 min after Friday shkia vs ~28–30 min for weekday tzeis) — i.e. two distinct tzeis definitions, both almost certainly degree-based and season-dependent. **Rounded up.**
- **Weekday Mincha:** ~10 min before shkia; **Maariv:** at weekday tzeis; **Erev Shabbos Mincha:** ~8 min after candle lighting; **Kabbolas Shabbos:** ~26 min after Mincha. These are shul policies, not halachic constants → must be configurable rules with per-week manual override.
- Mi'sheyakir is printed as "approx"; Morning Shema is "finish by" (sof zman Krias Shema per the Alter Rebbe's shitta).
- Molad announced in Jerusalem Standard Time with chalakim; Rosh Chodesh days spelled out ("yom revi'i and yom chamishi").

**⚠ Critical Phase 0 task:** reverse-engineer the *exact* zmanim definitions (elevation, degrees for alos/misheyakir/tzeis variants, shitta for sof zman Shema) by fitting candidate formulas against all 27 historical sheets for the Bondi coordinates, then have the Rov confirm the recovered definitions in writing. Do not guess; do not ship until the engine reproduces published sheets to ±1 minute (accounting for the stated rounding directions). Note: automation will also catch errata — e.g. the 5786 wk 41–44 sheet prints "Fast of 9 Av starts Wed. at 5:09**am**" where pm (shkia) is evidently intended.

---

## 2. Software options and recommendation

| Option | What it is | Pros | Cons |
|---|---|---|---|
| **A. WordPress plugin** (recommended **if** ttcc.info runs WordPress) | Plugin adds a "Timesheets" section in wp-admin; PHP zmanim library; .docx export | Dashboard for free (wp-admin), login/users/hosting already exist, sheets can also be published to the site as pages, PHP has mature libraries (PhpZmanim — a port of KosherJava; PHPWord for .docx) | Coupled to the site's hosting/PHP version; WP updates are a maintenance surface |
| **B. Standalone web app** (recommended otherwise) | Small self-hosted app (Laravel/PHP or Next.js/TypeScript with `kosher-zmanim` + `docx`) | Independent of the website; cleanest architecture; easy to add users | Needs its own hosting + login (can be a $5/mo VPS or free-tier host) |
| **C. Local tool** (fallback / cheapest) | Python script + `zmanim` pip package + `python-docx`, with a simple Streamlit dashboard run on one computer | Fastest to build, zero hosting | Single-machine, less polished, harder to hand over |

**Recommendation:** Build the core as a **standalone, framework-agnostic library + document templates**, then wrap it in **Option A (WP plugin)** if ttcc.info is WordPress, otherwise **Option B**. The wrapper is thin either way; the value (zmanim engine, rules, templates) is portable. *Decision gate: confirm the ttcc.info CMS before Phase 4 (it was not reachable from the build sandbox).*

### Output & editing model ("compatible with regular word editing software")

- **Primary output: .docx** generated from a styled template that mirrors the existing sheets (fonts, blue/purple section bars, dotted leaders, boxed fast-day notices, בס"ד header). The user opens it in Word and edits freely — this is the guaranteed-editable deliverable.
- **Dashboard editing before export:** every section/line is a toggleable, editable block (include/remove Chassidus vs Tehillim, add a note, change a minyan time, insert a free-text announcement) so most edits never require Word.
- **Secondary outputs:** PDF (for printing/WhatsApp distribution) and optionally HTML (publish to the website).

---

## 3. System design

Five modules, deliberately separable:

1. **Zmanim engine** — wraps KosherJava-family library (PhpZmanim / kosher-zmanim), configured for Bondi (lat/long/elevation, `Australia/Sydney` tz incl. DST) and the Alter Rebbe definitions recovered in Phase 0. Exposes each zman with an explicit **rounding policy** (`FLOOR` for Friday/erev-YT candle lighting; `CEIL` for havdalah, motzaei-Shabbos Maariv, and 2nd-day-YT "not before" candle lighting; nearest-minute or "approx" for informational zmanim).
2. **Luach (calendar) layer** — Hebrew↔civil dates, parsha (Diaspora cycle incl. doubled sedras and Chazak), special Shabbosos (Mevorchim, Chazon, Nachamu, Shuva, HaGadol, Shira, the four parshiyos), yomim tovim (2-day diaspora), fasts (with commencement rules — dawn for minor fasts, shkia for 9 Av/YK), Rosh Chodesh, molad (JST + chalakim, formatted text), Omer day numbers, Pirkei Avos chapter (Chabad cycle: Pesach → Rosh Hashanah), Chanukah, DST transition detection, NSW public holidays.
3. **Schedule rules engine** — the shul's minyan-time policies expressed as editable rules ("weekday Mincha = shkia − 10 min, rounded to 1 min", "Kabbolas Shabbos = Mincha + 26 min", "Shacharis Sun 8:00 & 9:15; Mon–Fri 6:15 & 7:30; add 9:15 on public holidays", "Mevorchim → Tehillim 8:15 + Shacharis 10:10; otherwise Chassidus 9:15 + Shacharis 10:00"). Rules produce a draft; every value remains manually overridable per sheet.
4. **Document generator** — assembles week blocks / yom-tov day blocks into the three formats; renders .docx (PHPWord or `docx` npm), PDF, HTML. Includes the notes library (kiddush-window text with DST/EST variants, Eruv Tavshilin reminder, DST changeover, "A Kosheren un Freilichen Pesach!", etc.) auto-suggested by the luach layer but individually removable.
5. **Dashboard** — pick a date range (weeks and/or a yom tov) → generate draft → block-level editor (toggle sections, edit any time or text, drag in saved notes) → export .docx/PDF → archive of past sheets (regenerate/duplicate/edit).

**Data model:** `Location` (coords, tz), `ZmanimProfile` (definitions + rounding), `ScheduleRule` (rules engine config), `NoteTemplate` (reusable texts + trigger conditions), `Timesheet` (date range, format, generated JSON of blocks, manual overrides, export history).

---

## 4. Phased delivery plan

**Phase 0 — Calibration & fixtures (the foundation; do first)**
- Transcribe all 27 PDFs into structured JSON fixtures (every printed time + label + date).
- Fit candidate zmanim definitions against fixtures for Bondi; recover the exact shittos and the shul's minyan-rule constants; document discrepancies/errata.
- **Gate:** Rov signs off on the recovered definitions and both rounding rules. ✋ Nothing halachic ships without this.

**Phase 1 — Zmanim engine**: implement + unit tests; golden regression test = reproduce every zman on all 27 sheets to ±1 min with correct rounding direction.

**Phase 2 — Luach layer**: parsha/YT/fasts/molad/Omer/Pirkei Avos/Mevorchim/DST; golden test = reproduce every header, label, molad line and note trigger in the fixtures.

**Phase 3 — Rules engine + document generator**: draft sheets for a sample span (regular week, Mevorchim week, fast week, DST-change week, Pesach, Tishrei); .docx opens cleanly in Word/LibreOffice/Google Docs and visually matches the house style.

**Phase 4 — Dashboard** (WP plugin or standalone per the decision gate): generate-on-demand, block editor, exports, archive, user login.

**Phase 5 — Pilot & handover**: run in parallel with manual production for 4–6 weeks (e.g. through a yom tov season); fix divergences; write a one-page operator guide; hand over admin access + repo.

Rough effort: Phases 0–3 are the bulk (~70%); with AI-assisted development this is realistically **2–4 weeks part-time**, dominated by calibration and Rov review latency, not coding.

---

## 5. Which AI agents for which parts

| Work | Recommended agent/tooling | Why |
|---|---|---|
| PDF → JSON fixture transcription (27 files) | Claude Code **multi-agent workflow**: one vision-capable agent per PDF producing schema-validated JSON, plus a second independent agent per file that re-reads and diffs (adversarial verification) | Mechanical but zero-tolerance for typos; parallel + cross-checked beats one long manual pass. Ask Claude Code to "use a workflow" for this. |
| Reverse-engineering the zmanim definitions | Claude Code (Opus/Fable tier) interactively, writing fitting scripts against the fixtures | Requires numeric reasoning + halachic domain knowledge; keep a human (you/the Rov) in the loop on every conclusion |
| Architecture finalisation | Claude Code **Plan mode / Plan agent** | Produces a reviewable step-by-step plan before code is written |
| Zmanim engine + luach layer implementation | Claude Code, strongest model tier, test-driven (write golden tests first) | Highest correctness stakes in the project |
| Dashboard UI, CRUD, .docx templating | Claude Code, standard tier (Sonnet-class) — routine web work | Cheaper/faster; low ambiguity |
| Code review & security review before deploy | Claude Code `/code-review` and `/security-review` skills | Second-pass adversarial check, esp. for a WP plugin exposed on a live site |
| End-to-end verification | Claude Code `/verify` + `/run` skills (drives the real app, opens generated .docx) | Confirms behaviour, not just green tests |
| CI/PR babysitting | Claude Code PR-watch (`subscribe_pr_activity`) | Auto-fixes CI failures and responds to review comments |
| Template/visual design iteration | Claude with artifact previews (HTML mock of the sheet) before committing to .docx styling | Fast visual feedback loop |
| **Not** an AI job | Final halachic sign-off of definitions, rounding, and each season's first sheet | The Rov. The system should make review easy (diff view vs last year's sheet), never replace it. |

Ongoing use: once live, generating a sheet is a human clicking a button; optionally a **scheduled agent/routine** can pre-draft next week's sheet every Sunday and email it for review.

---

## 6. Risks & open questions

1. **Exact shittos unknown until Phase 0** — the two tzeis values and misheyakir/alos definitions must be recovered from data and confirmed by the Rov, not assumed.
2. **CMS unconfirmed** — verify ttcc.info is WordPress before committing to Option A (decision gate before Phase 4).
3. **Sydney specifics** — Southern Hemisphere seasons, `Australia/Sydney` DST transitions (sheets explicitly flag changeover nights), NSW public holidays affect minyan times.
4. **Rounding correctness is a halachic safety issue** — encode rounding *direction* per zman-use in one place, property-test it (never round candle lighting up; never round havdalah down).
5. **Historical sheets contain occasional errata** (one file is even named "CORRECTED") — calibration must tolerate/flag outliers rather than fit to them.
6. **Word fidelity** — .docx styling should be validated in desktop Word, Word Online, and Google Docs early (Phase 3), not at the end.
