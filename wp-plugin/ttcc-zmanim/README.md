# TTCC Zmanim Timesheets (WordPress plugin)

The wp-admin dashboard, public surfaces and exports for the TTCC times sheets.
It owns storage, UI, auth and publishing; **all halachic times are computed by
the Python engine** via the sheet service (`../../service/`) — the plugin never
computes or re-rounds a time. See the plan record and `../../WARPLAN.md` §4.

## What it provides

- **Dashboard** (`Timesheets → Dashboard`): pick a week/range → Generate → a
  block-level editor over a live HTML preview. Edit any minyan time, remove/add
  lines, add/remove notes; each line shows its source (rule / override / manual)
  with Revert-to-calculated. **"+ Add line"** opens an inline form (label, time,
  section, and — on week blocks — an optional day qualifier) to add a one-off
  custom minyan to a specific block. Zman-anchored edits that cross the halachic
  bound warn (never block). Multi-page A4 preview with zoom / fit-width; edits
  are scoped per block, so a change on one week never leaks to another.
- **Design + style presets**: per-sheet layout (classic / modern), per-type
  fonts, sizes and justification (header / subheader / content), logo + logo
  size (modern). Save a design as a named **preset**, apply it to any sheet, and
  mark one as the default for new sheets.
- **Archive**: saved sheets; edit/regenerate/export. Each row stores the engine
  version it was generated with.
- **Schedule profiles**: edit the seasonal minyan sets and note templates. Use
  **"Add a recurring minyan"** to append a fixed-time davening line to a schedule
  so it appears on every sheet that schedule covers (the full set is still
  editable as JSON below; reset restores the engine defaults).
- **Settings**: sheet-service URL + token, service health, piSignage URL.
- **Public surfaces**:
  - `[ttcc_week]` — current-week widget (auto-rolls), embeddable on any Elementor page.
  - `[ttcc_browse]` — browse any week (read-only; editing stays in wp-admin).
  - `[ttcc_week]`, `[ttcc_browse]` and the weekly signage page apply the
    dashboard edits (line overrides + note edits) of the most-recently-updated
    saved sheet overlapping the displayed week, so the public pages match the
    edited sheet; re-saving a sheet takes effect on the next page load. The
    Shabbos highlights surfaces below stay rule-generated.
  - `[ttcc_shabbos]` — Shabbos & Yom Tov times banner (candle lighting,
    Shabbos/Yom Tov ends, fast begin/end) with Prev / This Week / Next /
    jump-to-date navigation. Attributes: `location="Bondi · Sydney NSW"`,
    `footer="..."`, `nav="no"` (hide the navigation). Data comes from the
    engine's `/highlights` endpoint — the identical assembled times as the
    printed sheet, never Hebcal or a client-side calculation.
  - piSignage page at `/ttcc-signage/<slug>/` — current week, large-type, auto-refresh.
  - piSignage Shabbos screen at `/ttcc-signage/<slug>/shabbos/` — portrait
    (1080×1920-first) large-type screen with the same highlights data plus a
    live clock (site timezone). Non-interactive; re-fetches every 3 hours,
    retries every 5 minutes after a failure, and keeps the last-good times on
    screen through an outage. Both URLs show on the Settings page.
  - `GET /wp-json/ttcc/v1/shabbos-times[?week=YYYY-MM-DD]` — the public
    read-only JSON behind both (server-cached per week, ±2-year window).
- **Exports**: PDF, PNG (3:4 portrait social), optional .docx — streamed from the service.

## Install

1. Deploy and run the sheet service (`../../service/README.md`).
2. Copy `ttcc-zmanim/` into `wp-content/plugins/` (or zip and upload) and activate.
   Activation creates the tables, grants `manage_ttcc_timesheets` to administrators,
   and registers the signage rewrite.
3. In `Timesheets → Settings`, set the service URL + token; confirm the health banner is green.
4. Open `Timesheets → Schedule profiles` once to seed the active profile set from the engine defaults.

## Architecture / storage

- Custom tables: `{prefix}ttcc_timesheets` (range, blocks snapshot, overrides,
  `engine_version`, export history) and `{prefix}ttcc_profile_sets` (active
  profiles + notes JSON). Mirrors the `Timesheet` model in `engine/rules.py`.
- Line edits go through the engine's override mechanism (keyed by `rule_id`);
  block-note edits are applied plugin-side to the generated doc before rendering
  (`class-ttcc-sheet.php`), because notes are not engine lines.
- The service token is only ever sent server-side (bearer token); it never
  reaches the browser. All admin routes require `manage_ttcc_timesheets` and the
  REST nonce; public surfaces are read-only and cached with a last-good fallback.

## Degraded mode

If the service is unreachable, the dashboard health banner turns red and
Generate/preview/export are disabled; edits already loaded stay editable and
save. Public pages serve the cached last-good HTML.

## Note

Two halachic gates remain open before production use (Rov's written sign-off on
the recovered definitions; chabad.org's exact Sydney coordinate). They don't
block building or staging, but no sheet is used in production until both land.
