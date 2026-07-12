# Renderer contract: TTCC timesheet block data

**Audience:** the session building the .docx/PDF/HTML renderer (warplan module
4, presentation half). This document is self-contained: it specifies, field by
field, the plain-data structure produced by `engine/assemble.py::generate()`,
with two complete example blocks generated from real dates. The renderer's job
is layout/styling only — every time, label, and note in the data is final
(already rounded, already override-resolved). **Never recompute or re-round a
time in the renderer.**

```python
from datetime import date
from engine.assemble import generate

doc = generate(date(2025, 12, 7), date(2025, 12, 27))   # JSON-serializable dict
```

## Top level

```jsonc
{
  "format": "weekly",          // reserved; "weekly" for now
  "start": "2025-12-07",       // ISO dates of the requested range
  "end": "2025-12-27",
  "blocks": [ ... ]            // ordered list of WEEK and DAY blocks
}
```

Blocks appear in chronological order: each week block (Sunday→Shabbos) is
followed by day blocks for any yom tov / erev yom tov days inside that week.
The historical sheets render 1 week per column (single-week sheet) or 2–4
weeks in a two-column layout; day blocks render as boxed day-by-day schedules
(yom tov style).

## WEEK block

| Field | Type | Meaning / rendering |
|---|---|---|
| `type` | `"week"` | discriminator |
| `title` | string | Printed heading, e.g. `"The week of Parshas Vayeishev:"` |
| `parsha` | string | Parsha name alone (doubled sedras use an en dash: `"Matos–Masei"`) |
| `shabbos_labels` | string[] | Extra labels for the **"Shabbos kodesh:"** line, in print order: `Mevorchim`, `Chazak`, `Rosh Chodesh`, `Shekalim`/`Zachor`/`Parah`/`HaChodesh`, `Shira`, `HaGadol`, `Chazon`, `Nachamu`, `Shuva`, … Render as `"Shabbos kodesh: <parsha>, <label1>, <label2>"` |
| `hebrew_dates` | string | e.g. `"17–23 Kislev 5786"` — print under the title |
| `civil_start`/`civil_end` | ISO date | Sunday / Shabbos of the week |
| `friday`/`shabbos` | ISO date | convenience anchors |
| `active_profiles` | string[] | Which schedule profiles produced lines (`base`, `early_erev_shabbos`, `halacha_shiur_season`, `summer_holidays`). Informational — do not branch layout on it; the presence/absence of sections in `entries` is authoritative |
| `entries` | LINE[] | every printed line, see LINE below |
| `molad` | string \| null | Fully formatted molad + Rosh Chodesh announcement (only on Shabbos Mevorchim weeks). Render as its own emphasized paragraph in the Shabbos-day area |
| `notes` | string[] | Luach-triggered notes (kiddush-window text with DST/standard-time variant, DST-changeover warning, public-holiday notices). Render at the block foot; each is independently deletable in the dashboard |

### LINE (one printed line inside `entries`)

```jsonc
{
  "rule_id": "es_kabbolas_shabbos",  // stable id; the dashboard keys manual
                                     // overrides on it. null never occurs;
                                     // zman lines use "z_*" ids, manual
                                     // additions "add:*"
  "section": "Erev Shabbos regular times: candle lighting and davening",
                                     // printed section heading; null = the
                                     // week-top zmanim table (no heading)
  "label": "Kabbolas Shabbos followed by Maariv",
  "kind": "minyan",                  // "zman" | "minyan" | "fast"
  "day_spec": null,                  // day qualifier to print after the label
                                     // ("Sun.–Thurs.", "Mon.–Fri.", "Sun. & Mon.");
                                     // null = the line's date is implied by its
                                     // section (Friday/Shabbos)
  "date": "2025-12-12",              // ISO date the time refers to, when a
                                     // single unambiguous day; null for ranged
                                     // lines and fixed weekly times
  "time": "20:20",                   // 24h HH:MM. Render as 12h am/pm
                                     // ("8:20pm") to match the house style
  "qualifier": null,                 // print before/around the time:
                                     // "approx" | "finish by" | "not before" |
                                     // "not after approx" | "before" |
                                     // "or after" | "from" | "after" | "by"
  "source": "rule",                  // "zmanim" (astronomical), "rule"
                                     // (schedule rule), "override" (manually
                                     // edited), "manual" (manually added).
                                     // The dashboard shows this; the printed
                                     // sheet does NOT distinguish them
  "profile_id": "base",              // present on rule-produced lines only
  "bound": {                         // OPTIONAL: halachic bound for editors.
    "zman": "candle_lighting",       // When a user edits `time`, warn (never
    "direction": "not_before",       // block) if the new time crosses this.
    "date": "2025-12-12",            // direction "not_before": edited time
    "time": "19:43"                  // must be >= bound; "not_after": <=
  }
}
```

Rendering conventions carried over from the historical sheets:

- Lines print as `label [day_spec] <dotted leader> [qualifier] time`.
  Two lines with the same `section` + `label` + `day_spec` but different
  qualifiers (the early-minyan candle window, the kiddush window) merge onto
  one printed line: `"Candle lighting … not before 6:34pm, not after approx
  6:44pm"`.
- Consecutive `Shacharis` lines in the same section with the same `day_spec`
  merge: `"Shacharis: Sun. 8:00am & 9:15am; Mon.–Fri. 6:15am & 7:30am"`.
- `kind: "fast"` entries come in start/end pairs sharing a `section` like
  `"Fast of 9 Av"`; render as the boxed fast notice ("Fast of 9 Av: starts
  Wed. at 5:09pm; ends Thurs. at 5:37pm").
- Section print order (matching the sheets): the section-less zmanim table,
  `Davening times during the week`, `Erev Shabbos early minyan (and essential
  halachic details)` (when present), `Erev Shabbos key times`,
  `Erev Shabbos [regular times:] candle lighting and davening`,
  `Shabbos Day and Motzaei Shabbos`. `entries` already arrives in this order.
- When the early minyan runs, the regular Erev Shabbos section is titled
  `"Erev Shabbos regular times: candle lighting and davening"`; otherwise
  `"Erev Shabbos candle lighting and davening"`. The data already carries the
  right string.
- The Shabbos Mincha label already includes the season's Pirkei Avos chapter
  (`"Mincha, Pirkei Avos 3, Seder Nigunim"`) — no lookup needed.

## DAY block (yom tov / erev yom tov)

| Field | Type | Meaning |
|---|---|---|
| `type` | `"day"` | discriminator |
| `title` | string \| null | e.g. `"Pesach day 1"` (joined `labels`) |
| `weekday` | string | `"Thurs."` — print with the date heading |
| `hebrew_date` | string | `"15 Nisan"` |
| `date` | ISO date | civil date |
| `labels` | string[] | holiday labels for the day (may include `"Erev Shabbos"`, `"Erev Yom Tov"`, fast names) |
| `omer_day` | int \| null | print `"Day N of the Omer"` when non-null |
| `entries` | LINE[] | same LINE shape as week blocks; `section` is usually null (day blocks are short) |
| `notes` | string[] | day-specific notes |

Day-block minyan times are **editable defaults** (`source: "rule"`): the
corpus shows yom-tov minyan times are the most frequently hand-adjusted lines
(see `phase3/PHASE3-FINDINGS.md`), so the dashboard treats every day-block
line as expected-to-be-reviewed. Deadline lines specific to Pesach (chometz
deadlines, Bedikas Chometz) and Tishrei/Purim extras are Phase-4 additions and
will arrive as more LINE entries in the same shape — render generically from
`label`/`qualifier`/`time`, do not hard-code holiday logic.

## Manual overrides

`generate(..., overrides={...})` applies dashboard edits before you ever see
the data — a renderer never needs the overrides dict. For reference:
`{"<rule_id>": {"time": "19:15"}}` edits, `{"<rule_id>": {"suppress": true}}`
removes, `{"add:<id>": {<full LINE>}}` inserts (appears with
`source: "manual"`). Edited lines keep `source: "override"` and their `bound`.

---

## Example 1 — a regular (Mevorchim, early-minyan season) week

Generated from real data: `assemble_week(date(2025, 12, 7))` — week of
Parshas Vayeishev 5786. Cross-checked against the published sheet
"5786 times -wk 11 to 13" (all times match; the shul hand-nudged three lines
that week: Shabbos Mincha 19:40 and the shiur 19:10, both −5 from rule, and
Shacharis 10:15 for 10:10).

```json
{
  "type": "week",
  "title": "The week of Parshas Vayeishev:",
  "parsha": "Vayeishev",
  "shabbos_labels": ["Mevorchim"],
  "hebrew_dates": "17–23 Kislev 5786",
  "civil_start": "2025-12-07",
  "civil_end": "2025-12-13",
  "friday": "2025-12-12",
  "shabbos": "2025-12-13",
  "active_profiles": ["base", "early_erev_shabbos", "halacha_shiur_season"],
  "entries": [
    {"rule_id": "z_misheyakir", "section": null, "label": "Mi'sheyakir (earliest tallis & tefillin)", "kind": "zman", "day_spec": "Sun.–Fri.", "date": null, "time": "04:44", "qualifier": "approx", "source": "zmanim"},
    {"rule_id": "z_netz", "section": null, "label": "Netz Hachamah (sunrise)", "kind": "zman", "day_spec": "Sun.–Fri.", "date": null, "time": "05:38", "qualifier": null, "source": "zmanim"},
    {"rule_id": "z_shema_wk", "section": null, "label": "Morning Shema", "kind": "zman", "day_spec": "Sun.–Fri.", "date": null, "time": "09:09", "qualifier": "finish by", "source": "zmanim"},
    {"rule_id": "z_shkia_wk", "section": null, "label": "Shkia", "kind": "zman", "day_spec": "Sun.–Thurs.", "date": null, "time": "19:56", "qualifier": null, "source": "zmanim"},
    {"rule_id": "z_tzeis_wk", "section": null, "label": "Tzeis", "kind": "zman", "day_spec": "Sun.–Thurs.", "date": null, "time": "20:29", "qualifier": null, "source": "zmanim"},
    {"rule_id": "shacharis_sun_1", "section": "Davening times during the week", "label": "Shacharis", "kind": "minyan", "day_spec": "Sun.", "date": null, "time": "08:00", "qualifier": null, "source": "rule", "profile_id": "base"},
    {"rule_id": "shacharis_sun_2", "section": "Davening times during the week", "label": "Shacharis", "kind": "minyan", "day_spec": "Sun.", "date": null, "time": "09:15", "qualifier": null, "source": "rule", "profile_id": "base"},
    {"rule_id": "shacharis_wk_1", "section": "Davening times during the week", "label": "Shacharis", "kind": "minyan", "day_spec": "Mon.–Fri.", "date": null, "time": "06:15", "qualifier": null, "source": "rule", "profile_id": "base"},
    {"rule_id": "shacharis_wk_2", "section": "Davening times during the week", "label": "Shacharis", "kind": "minyan", "day_spec": "Mon.–Fri.", "date": null, "time": "07:30", "qualifier": null, "source": "rule", "profile_id": "base"},
    {"rule_id": "weekday_mincha", "section": "Davening times during the week", "label": "Mincha", "kind": "minyan", "day_spec": "Sun.–Thurs.", "date": null, "time": "19:46", "qualifier": null, "source": "rule", "bound": {"zman": "shkia", "direction": "not_after", "date": "2025-12-07", "time": "19:56"}, "profile_id": "base"},
    {"rule_id": "weekday_maariv", "section": "Davening times during the week", "label": "Maariv", "kind": "minyan", "day_spec": "Sun.–Thurs.", "date": null, "time": "20:29", "qualifier": null, "source": "rule", "bound": {"zman": "tzeis", "direction": "not_before", "date": "2025-12-11", "time": "20:29"}, "profile_id": "base"},
    {"rule_id": "early_es_mincha", "section": "Erev Shabbos early minyan (and essential halachic details)", "label": "Mincha (must be completely finished before Plag Hamincha)", "kind": "minyan", "day_spec": null, "date": "2025-12-12", "time": "18:14", "qualifier": null, "source": "rule", "bound": {"zman": "plag_hamincha", "direction": "not_after", "date": "2025-12-12", "time": "18:33"}, "profile_id": "early_erev_shabbos"},
    {"rule_id": "early_es_candles_from", "section": "Erev Shabbos early minyan (and essential halachic details)", "label": "Candle lighting", "kind": "zman", "day_spec": null, "date": "2025-12-12", "time": "18:34", "qualifier": "not before", "source": "rule", "bound": {"zman": "plag_hamincha", "direction": "not_before", "date": "2025-12-12", "time": "18:34"}, "profile_id": "early_erev_shabbos"},
    {"rule_id": "early_es_candles_to", "section": "Erev Shabbos early minyan (and essential halachic details)", "label": "Candle lighting", "kind": "zman", "day_spec": null, "date": "2025-12-12", "time": "18:44", "qualifier": "not after approx", "source": "rule", "profile_id": "early_erev_shabbos"},
    {"rule_id": "early_es_ks", "section": "Erev Shabbos early minyan (and essential halachic details)", "label": "Kabbolas Shabbos (followed by Maariv)", "kind": "minyan", "day_spec": null, "date": "2025-12-12", "time": "18:34", "qualifier": null, "source": "rule", "bound": {"zman": "plag_hamincha", "direction": "not_before", "date": "2025-12-12", "time": "18:34"}, "profile_id": "early_erev_shabbos"},
    {"rule_id": "early_es_kiddush_before", "section": "Erev Shabbos early minyan (and essential halachic details)", "label": "Start Kiddush & meal", "kind": "zman", "day_spec": null, "date": "2025-12-12", "time": "20:00", "qualifier": "before", "source": "rule", "profile_id": "early_erev_shabbos"},
    {"rule_id": "early_es_kiddush_after", "section": "Erev Shabbos early minyan (and essential halachic details)", "label": "Start Kiddush & meal", "kind": "zman", "day_spec": null, "date": "2025-12-12", "time": "20:30", "qualifier": "or after", "source": "rule", "profile_id": "early_erev_shabbos"},
    {"rule_id": "early_es_shema", "section": "Erev Shabbos early minyan (and essential halachic details)", "label": "Kerias Shema (said from Tzeis Hachochavim)", "kind": "zman", "day_spec": null, "date": "2025-12-12", "time": "20:30", "qualifier": "from", "source": "rule", "profile_id": "early_erev_shabbos"},
    {"rule_id": "early_es_kezayis", "section": "Erev Shabbos early minyan (and essential halachic details)", "label": "Eat another kezayis bread after Tzeis Hachochavim", "kind": "zman", "day_spec": null, "date": "2025-12-12", "time": "20:30", "qualifier": "after", "source": "rule", "profile_id": "early_erev_shabbos"},
    {"rule_id": "z_plag_fri", "section": "Erev Shabbos key times", "label": "Plag Hamincha", "kind": "zman", "day_spec": null, "date": "2025-12-12", "time": "18:34", "qualifier": null, "source": "zmanim"},
    {"rule_id": "z_shkia_fri", "section": "Erev Shabbos key times", "label": "Shkia", "kind": "zman", "day_spec": null, "date": "2025-12-12", "time": "20:00", "qualifier": null, "source": "zmanim"},
    {"rule_id": "z_tzeis_fri", "section": "Erev Shabbos key times", "label": "Tzeis hachochavim", "kind": "zman", "day_spec": null, "date": "2025-12-12", "time": "20:30", "qualifier": null, "source": "zmanim"},
    {"rule_id": "z_candles_fri", "section": "Erev Shabbos regular times: candle lighting and davening", "label": "Candle lighting", "kind": "zman", "day_spec": null, "date": "2025-12-12", "time": "19:42", "qualifier": null, "source": "zmanim"},
    {"rule_id": "es_mincha", "section": "Erev Shabbos regular times: candle lighting and davening", "label": "Mincha", "kind": "minyan", "day_spec": null, "date": "2025-12-12", "time": "19:50", "qualifier": null, "source": "rule", "bound": {"zman": "shkia", "direction": "not_after", "date": "2025-12-12", "time": "20:00"}, "profile_id": "base"},
    {"rule_id": "es_kabbolas_shabbos", "section": "Erev Shabbos regular times: candle lighting and davening", "label": "Kabbolas Shabbos followed by Maariv", "kind": "minyan", "day_spec": null, "date": "2025-12-12", "time": "20:20", "qualifier": null, "source": "rule", "bound": {"zman": "candle_lighting", "direction": "not_before", "date": "2025-12-12", "time": "19:43"}, "profile_id": "base"},
    {"rule_id": "z_shema_shab", "section": "Shabbos Day and Motzaei Shabbos", "label": "Morning Shema", "kind": "zman", "day_spec": null, "date": "2025-12-13", "time": "09:11", "qualifier": "finish by", "source": "zmanim"},
    {"rule_id": "shab_tehillim", "section": "Shabbos Day and Motzaei Shabbos", "label": "Tehillim", "kind": "minyan", "day_spec": null, "date": null, "time": "08:15", "qualifier": null, "source": "rule", "profile_id": "base"},
    {"rule_id": "shab_shacharis_mev", "section": "Shabbos Day and Motzaei Shabbos", "label": "Shacharis (Kiddush / farbrengen after Musaf)", "kind": "minyan", "day_spec": null, "date": null, "time": "10:10", "qualifier": null, "source": "rule", "profile_id": "base"},
    {"rule_id": "shab_mincha", "section": "Shabbos Day and Motzaei Shabbos", "label": "Mincha followed by Seder Nigunim", "kind": "minyan", "day_spec": null, "date": "2025-12-13", "time": "19:45", "qualifier": null, "source": "rule", "bound": {"zman": "shkia", "direction": "not_after", "date": "2025-12-13", "time": "20:01"}, "profile_id": "base"},
    {"rule_id": "motzaei_maariv", "section": "Shabbos Day and Motzaei Shabbos", "label": "Motzaei Shabbos, Maariv", "kind": "minyan", "day_spec": null, "date": "2025-12-13", "time": "20:44", "qualifier": null, "source": "rule", "bound": {"zman": "tzeis_shabbos", "direction": "not_before", "date": "2025-12-13", "time": "20:44"}, "profile_id": "base"},
    {"rule_id": "shab_halacha_shiur", "section": "Shabbos Day and Motzaei Shabbos", "label": "Halacha shiur, from the Shulchan Aruch Harav", "kind": "minyan", "day_spec": null, "date": "2025-12-13", "time": "19:15", "qualifier": null, "source": "rule", "profile_id": "halacha_shiur_season"}
  ],
  "molad": "Molad for Teves: Shabbos 2:22am and 10 chalakim, Jerusalem Standard Time.  Rosh Chodesh Teves: Shabbos kodesh and yom rishon.",
  "notes": [
    "It is customary to not make Kiddush on Friday nights between 6:55pm and 7:55pm Daylight Saving Time (per the Mogen Avrohom; Alter Rebbe's Shulchan Aruch O.C. 271)."
  ]
}
```

## Example 2 — a yom tov day

Generated from real data: `assemble_day(date(2026, 4, 2))` — 1st day Pesach
5786. Note the "not before" 2nd-night candle lighting (rounded UP, never
earlier) and that minyan lines are editable defaults (`source: "rule"`).
Cross-checked against the published "5786 times -wk 28b & 29 Pesach" sheet
(candles 19:26 exact; the shul hand-set Mincha 18:40 and Maariv 19:25 that
day, ±1 from the defaults).

```json
{
  "type": "day",
  "title": "Pesach day 1",
  "weekday": "Thurs.",
  "hebrew_date": "15 Nisan",
  "date": "2026-04-02",
  "labels": ["Pesach day 1"],
  "omer_day": null,
  "entries": [
    {"rule_id": "yt_shacharis", "section": null, "label": "Shacharis", "kind": "minyan", "day_spec": null, "date": "2026-04-02", "time": "10:00", "qualifier": null, "source": "rule"},
    {"rule_id": "yt_mincha", "section": null, "label": "Mincha", "kind": "minyan", "day_spec": null, "date": "2026-04-02", "time": "18:39", "qualifier": null, "source": "rule"},
    {"rule_id": "yt_candles_2nd", "section": null, "label": "Candle lighting", "kind": "zman", "day_spec": null, "date": "2026-04-02", "time": "19:26", "qualifier": "not before", "source": "zmanim"},
    {"rule_id": "yt_maariv_2nd", "section": null, "label": "Maariv", "kind": "minyan", "day_spec": null, "date": "2026-04-02", "time": "19:26", "qualifier": null, "source": "rule"}
  ],
  "notes": []
}
```

## Invariants the renderer may rely on

1. Every entry has all of: `rule_id`, `section`, `label`, `kind`, `day_spec`,
   `date`, `time`, `qualifier`, `source` (verified over two full generated
   years). `bound` and `profile_id` are optional.
2. `time` is always zero-padded 24h `HH:MM`, already rounded per the halachic
   rounding policy (candle lighting floor; end-of-Shabbos/YT ceil).
3. `entries` arrive grouped by section in print order; group boundaries are
   where `section` changes.
4. Strings may contain `’`/`–` (curly apostrophe, en dash) — use fonts that
   cover them; the house style prints them literally.
5. A week always has the section-less zmanim table and the Shabbos-day
   section; the early-minyan section appears only in season; `molad` is
   non-null iff `"Mevorchim"` is in `shabbos_labels`.
6. `Timesheet` (engine/rules.py) is the persistence shape for the dashboard:
   `blocks` (this structure) + `overrides` + `export_history`.
