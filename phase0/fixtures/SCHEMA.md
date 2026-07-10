# Fixture schema (Phase 0)

One JSON file per source sheet, named `<extracted-txt-stem>.json`, in this directory.
Purpose: a lossless, structured transcription of every **printed clock time** on the sheet,
with enough date context to test calculations against it. Transcribe **as printed** — never
"fix" a value; if something looks wrong, copy it verbatim and record it in `suspected_errata`.

```jsonc
{
  "source_pdf": "5786_20times_20-wk_2004.pdf",
  "readable_name": "5786 times -wk 04",
  "hebrew_year": 5786,
  "format": "weekly",              // "weekly" (single/multi-week sheets) or "yomtov" (day-by-day schedules)
  "blocks": [
    // WEEK BLOCK — one per "The week of Parshas X" section
    {
      "type": "week",
      "title_raw": "The week of Parshas Bereishis:",
      "parsha": "Bereishis",
      "shabbos_labels": ["Mevorchim"],          // extra labels from "Shabbos kodesh:" line (Mevorchim, Chazak, Chazon, Nachamu, ...)
      "hebrew_dates_raw": "20–26 Tishrei 5786",
      "civil_start": "2025-10-12",              // ISO, Sunday of the printed range
      "civil_end": "2025-10-18",                // ISO, Shabbos
      "friday": "2025-10-17",                   // ISO (derive from the printed civil range)
      "shabbos": "2025-10-18",
      "entries": [ /* see ENTRY below */ ],
      "molad_raw": "Molad for Cheshvan: Wed. 12:54am and 8 chalakim, Jerusalem Standard Time.  Rosh Chodesh Cheshvan: yom revii and yom chamishi.",  // or null
      "notes": ["Note: The Erev Shabbos early minyan ...", "It is customary to not make Kiddush ..."],
      "suspected_errata": []                    // strings describing anything that looks like a typo, with the verbatim text
    },
    // DAY BLOCK — used in yomtov schedules (one per day heading)
    {
      "type": "day",
      "title_raw": "Erev Pesach",
      "weekday_raw": "Wed.",
      "hebrew_date_raw": "14 Nisan",
      "date": "2026-04-01",                     // ISO from printed civil date
      "labels": ["Erev Pesach"],                // e.g. ["2nd day Pesach", "Erev Shabbos"], ["Isru Chag"]
      "omer_day": null,                         // integer if printed ("Day 5 of Omer")
      "entries": [ /* ENTRY */ ],
      "notes": [],
      "suspected_errata": []
    }
  ]
}
```

## ENTRY (one per printed time)

```jsonc
{
  "section": "Erev Shabbos key times",   // the heading the line sits under, verbatim; null if none
  "label": "Shkia",                      // the line's label, lightly normalised (strip dots/parentheticals)
  "kind": "zman",                        // zman | minyan | deadline | fast | other
                                         //   zman  = astronomical/halachic time (shkia, tzeis, plag, netz, misheyakir, shema, alos, chatzot, candle lighting)
                                         //   minyan = a shul event (Shacharis, Mincha, Maariv, Kabbolas Shabbos, Tehillim, Chassidus, Megillah, Yizkor...)
                                         //   deadline = "finish eating chometz by", "finish burning...", "Bedikas..."
                                         //   fast  = fast start/end
  "day_spec_raw": "Sun.-Thurs.",         // verbatim day qualifier on the line; null if none
  "date": null,                          // ISO date if the line refers to ONE unambiguous day
                                         //   (Friday sections → friday; Shabbos-day sections → shabbos; day blocks → the block date;
                                         //    ranges like Sun-Thurs → null)
  "time": "19:06",                       // 24-hour HH:MM
  "qualifier": null,                     // "approx" | "finish by" | "not before" | "by" | null
  "raw": "Shkia Sun.-Thurs. ................ 7:06pm"   // the full source line (dots may be collapsed to a few)
}
```

Rules:
- **Every clock time printed on the sheet must appear in exactly one entry** (lines with two times, e.g. "Shacharis 6:15am & 7:30am", become two entries with the same raw/label). Times inside `molad_raw` and inside `notes` strings stay there and do NOT become entries (e.g. the fixed Kiddush-window note).
- Convert am/pm to 24h. Preserve the printed minute exactly.
- Fast boxes: two entries, labels "Fast start"/"Fast end", kind "fast", with `date` resolved from the printed weekday, and the fast's name in `section` (e.g. "Fast of 17 Tammuz").
- Multi-week sheets: one week block per week, in printed order.
- Yom tov schedules that embed "Times for the week ahead" mini-tables: put those entries in the nearest containing week block if the sheet has one, else in a day-less week block with `parsha: null` and the printed date range.
- Long prose passages without clock times (minhagim essays, halachic notes): record the heading in `notes` as "PROSE: <heading>" — do not transcribe the body.
- Derive civil years from context (Hebrew year 5786 ≈ Sept 2025–Sept 2026); the sheets print day+month and abbreviated years.
