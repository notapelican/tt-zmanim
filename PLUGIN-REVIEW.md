# TTCC Zmanim WordPress Plugin — Review

Review of `wp-plugin/ttcc-zmanim` (v0.3.0) covering practical functionality,
formatting, usability and UX. Every finding below was verified against the
actual code paths (plugin PHP/JS plus the parts of `engine/` and `service/`
the plugin depends on), not inferred. Severity ordering: **A** = critical
functional bugs, **B** = major usability/UX gaps, **C** = polish.

Each remediation step carries a **model recommendation** (§4). Two of the
findings (A5 pagination/preview) have been superseded by an accepted
redesign — the specs are recorded in §5 and are being implemented on this
branch.

---

## 1. Critical functional bugs (A)

### A1. Line overrides bleed across every block on multi-week / yom-tov sheets
`engine/assemble.py:270,350` applies the *full* overrides dict to every
block, and rule ids (`weekday_mincha`, `es_mincha`, `erev_yt_maariv`, …)
repeat identically in every week/day block. Consequences on a 2–4-week
sheet:

- Editing week 1's Mincha silently changes **all** weeks — wrong, since
  zman-anchored times shift week to week.
- Suppressing a line removes it from every week.
- `engine/rules.py:287-289` appends every `add:` line to **every block** —
  an added "Special shiur" for week 1 prints on all weeks *and* all
  yom-tov day blocks.

The UI compounds it: `addLineButton` (`admin/js/dashboard.js:381`) stores
`date: null` for week blocks and the engine ignores `date` anyway.
Multi-week is a first-class UI feature ("Weeks: 1–4"), so per-block editing
is fundamentally broken. **Fix: block-scoped override keys** (being
implemented on this branch as a prerequisite for the new multi-week
layout).

### A2. Public surfaces never show the operator's edited/saved sheet
`[ttcc_week]`, `[ttcc_browse]` and the piSignage page always regenerate
from engine defaults with empty overrides
(`includes/class-ttcc-public.php:73`). A moved minyan or added note — even
saved as **Final** — never reaches the website or the signage screen.
"Final" status has no behavioral meaning anywhere in the plugin. Operators
following the operator guide (edit → Save → embed widget) will publish
times that don't match the PDF they print.
**Fix:** public surfaces should prefer the saved (final) sheet covering the
requested week, falling back to default generation; purge the cache on
save.

### A3. The offline-mode promise is false
The offline banner says "Edits you make are kept and will save", but Save →
REST `save_timesheet` re-builds via the service
(`includes/class-ttcc-rest.php:172`) and returns 503 when it's down.
Nothing is kept locally (a reload loses everything), and the Save button
isn't even disabled while offline (`dashboard.js:97` only disables
Generate/WhatsApp/exports).
**Fix:** either save overrides without rebuilding when the service is down
(store, mark stale, rebuild on reconnect) or disable Save and correct the
banner text; add localStorage draft persistence.

### A4. Exporting a saved sheet silently ignores unsaved edits
`doExport` (`dashboard.js:464`) sends `sheet=<id>` whenever the sheet has
ever been saved, so the export streams the *stored* snapshot. Edit a time →
click PDF → get the old sheet, with no warning.
**Fix:** export current editor state when dirty (or prompt to save first).

### A5. Preview shows only page 1 — superseded
The preview iframe is hard-locked to a single A4 box (`fitPreview`,
`dashboard.js:194-205`); content past one page "falls off the bottom" by
design, with no way to inspect page 2+. Superseded by the accepted
pagination/preview redesign in §5.

### A6. Note-removal overrides are index-based against regenerated content
Note edits store `removed:[int]` indices into the engine's note list
(`includes/class-ttcc-sheet.php:109-136`). If engine/profile output changes
between save and regenerate, the indices silently strike the *wrong* notes.
Also `captureOriginalNotes` swallows failures (`dashboard.js:238`), after
which already-edited notes are mislabeled as originals and indices
misalign.
**Fix:** key note removals by note text hash (or stable note ids from the
engine), and surface capture failures.

### A7. Export failure destroys the editor
`doExport` navigates via `window.location.href`; on any service error the
handler `wp_die()`s an HTML page, so the browser leaves the dashboard and
all unsaved edits are gone.
**Fix:** fetch the export via XHR/blob (or a hidden iframe) and surface
errors inline.

### A8. Regenerate / navigation lose work with no guard
`doGenerate` (`dashboard.js:430`) wipes line+note overrides
unconditionally. No confirmation, no dirty-state indicator, no
`beforeunload` warning anywhere in the app.
**Fix:** track dirty state; confirm before Regenerate; add `beforeunload`.

### A9. Export history is wiped on every save
`TTCC_Zmanim_Storage::save_timesheet` always re-encodes `export_history`
from `$data`, and REST never passes it
(`includes/class-ttcc-rest.php:178-189`), so each Save resets the history
to `[]` — the `append_export_history` audit feature is effectively useless.
**Fix:** don't touch `export_history` on update unless explicitly provided.

---

## 2. Major usability / UX gaps (B)

- **B1. No delete, no pagination.** REST `DELETE /timesheets/{id}` exists
  but no UI exposes it — sheets can never be deleted. The Archive caps at
  100 rows with no pager or search; rows offer only Edit + PDF (no
  PNG/DOCX, no export history display).
- **B2. "Edit" a saved sheet actually regenerates it.** `loadSheet`
  previews via live regeneration while the Archive row's PDF prints the
  stored snapshot — the two can silently differ after profile or engine
  changes. `engine_version` is stored precisely to catch this drift but is
  never surfaced or compared.
- **B3. Add-line UX is two chained `window.prompt()`s.** No HH:MM
  validation ("7pm" is accepted and sent to the service), no section
  choice, label uneditable afterwards. "Remove" on an added line replaces
  its whole definition with `{suppress:true}` (`dashboard.js:298-303`), so
  "Restore" restores nothing — the line's data is destroyed.
- **B4. The entire halachic schedule is edited as raw JSON** in two
  textareas with only `JSON.parse` as validation. A structurally wrong
  (but valid-JSON) save is stored unvalidated; every later Generate then
  fails with a cryptic service error. The only recovery is "Reset to
  engine defaults", destroying all local customization — no versioning,
  backup, or undo.
- **B5. Preview races and wasted round-trips.** Preview requests are
  debounced but not sequenced/aborted — a slow older response can
  overwrite a newer one. Every Generate makes two full `/generate`
  round-trips (`captureOriginalNotes` + `refresh`). Toggling "Show page
  boundaries" re-fetches from the service just to inject a `<style>` (and
  therefore breaks while offline). *(Partially addressed by the §5 preview
  rework: the guides toggle becomes client-side.)*
- **B6. Nonce expiry bricks a long-open dashboard.** The REST + export
  nonces are printed once; a tab left open past nonce lifetime gets opaque
  403s on every action with no refresh path — combined with A8, all work
  is lost.
- **B7. `[ttcc_browse]` is an unauthenticated amplification/bloat vector.**
  Any visitor can request any `ttcc_wk=YYYY-MM-DD` (not snapped to Sunday,
  unbounded): each unique date triggers two service calls (30 s timeouts)
  *inside the page request* and permanently writes a
  `ttcc_lastgood_<md5>` option holding a full HTML document. Unbounded
  `wp_options` growth plus trivial service hammering; a cold cache also
  makes public page load time hostage to service latency (worst case
  ~60 s). **Fix:** snap to Sunday, bound the date range, pre-warm via
  cron, cap/prune last-good rows.
- **B8. Last-good cache never pruned.** One permanent option per
  (context|week|css) accumulates forever; `uninstall.php` deletes
  `ttcc_lastgood_%` but misses `_transient_ttcc_lastgood_%` /
  `_transient_timeout_…` rows.
- **B9. Timezone mismatch for "current week".** `dashboard.js` computes
  the default Sunday from the *browser* clock; the public widget/signage
  use the *site* timezone — an operator abroad edits a different default
  week than the site displays.
- **B10. Settings page blocks up to 8 s** on a synchronous health check
  during render when the service is down.

---

## 3. Formatting / polish (C)

- **i18n:** every user-facing string in `dashboard.js` / `profiles.js` is
  hard-coded English while PHP is fully `__()`-wrapped; only the one
  "offline" string is localized. No `load_plugin_textdomain` call either.
- **Accessibility:** time inputs and note checkboxes have no programmatic
  labels; "×" delete buttons lack aria-labels; line source is conveyed by
  color-only badges; preview/embed iframes are unsandboxed (service HTML
  runs same-origin in wp-admin and on the public site — a trust-boundary
  nit).
- **Token exposure claim:** Settings echoes the service + GitHub tokens
  back into password-field `value` attributes; "never exposed to the
  browser" is only true for non-admins.
- **Ad-hoc export via GET:** the whole overrides JSON rides the query
  string — heavily edited sheets can exceed URL length limits.
- Small nits: signage `meta refresh` is 1800 s but the comment says
  hourly; `inject_head` is duplicated verbatim as `inject_head_static`;
  health polls every 30 s forever even in background tabs; `public.css`
  is enqueued on every front-end page regardless of shortcode presence.

---

## 4. Which Claude model for each remediation step

Current lineup (per MTok in/out): Fable 5 $10/$50 · Opus 4.8 $5/$25 ·
Sonnet 5 $3/$15 (intro $2/$10) · Haiku 4.5 $1/$5.

**Decision: run everything on Claude Opus 4.8 and tune cost with the
effort setting instead of model-switching.** The codebase is small enough
that Sonnet's ~40–60% saving on mid-tier steps is marginal, one avoided
bad iteration on the hard steps outweighs it, and a single model removes
per-task judgment calls.

| Step | Opus 4.8 effort | Notes |
|---|---|---|
| A1 override-scoping engine fix (engine + service + plugin + JS) | **xhigh** | Halachically load-bearing, cross-layer data-model change with stored-override migration |
| §5 pagination + fit-to-page renderer rework | **xhigh** | Complex layout/print work verified against 27 golden fixtures |
| §5 preview rework (dashboard JS/CSS) | **high** (default) | Well-scoped frontend work with a clear spec |
| A2 publish-to-public wiring; A3/A4/A7/A8/A9 save/export fixes; B1 delete + pagination; B7/B8 cache hardening; B3/B4 editor UX | **high** (default) | Ordinary WordPress PHP/JS with this review as the spec; independent focused sessions |
| C-items: i18n wrapping, aria-labels, comment/CSS nits, helper dedupe | **low–medium** | Mechanical sweeps. (Optional: Haiku 4.5 is quality-safe here at 5× cheaper, but not worth the model juggling) |
| Final review/verification pass (code-review + fixture regressions) | **high–xhigh** | Verification recall is the point |

Fable 5 is not needed for any step (2× Opus price; reserve for a full
architectural redo if Opus ever stalls).

---

## 5. Accepted redesign: pagination + preview (implemented on this branch)

### 5.1 Page layout (generator)

- **Single week** → one A4 page; content fills the page inside a
  whitespace margin; never overflows to a second page.
- **Multi-week** → 4 weeks per page in a 2×2 grid, filling the page with a
  margin. Additional weeks overflow to further pages in the same 4-up
  grid, except:
  - a **2-week remainder** renders as two full-height columns side by
    side on its own page;
  - a **1-week remainder** renders as a single-week full page.
  - (a 3-week remainder stays in the 2×2 grid with one empty cell.)
- Yom-tov day blocks occupy grid cells like weeks.
- Implementation: explicit fixed-size A4 `.page` containers with an
  embedded fit script that uniformly scales each page's content to fill
  the printable area (larger type on sparse pages, shrink-to-fit on dense
  ones). Same HTML drives the preview, PDF and PNG, so all three match.

### 5.2 Preview (dashboard)

- Multi-page preview: pages stack vertically; every page keeps a locked
  A4 ratio — never shaped by the browser window.
- Preview size is user-adjustable (zoom + fit-width); content scales with
  the preview size, not the window. Default zoom auto-fits the pane width
  within min/max clamps.
- Exports match the preview (same HTML + fit script at A4) unless the
  Settings export-paper override says otherwise.
