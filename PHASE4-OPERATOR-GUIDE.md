# Phase 4 — operator guide (TTCC Zmanim Timesheets)

One page for whoever runs the sheets each week. Architecture: a small Python
**sheet service** (wraps the fixture-validated engine, owns Chromium) runs off
SiteGround; the **WordPress plugin** on ttcc.org.au calls it. Halachic times are
always the engine's — the plugin never recomputes them.

## ⛔ Before production use — two halachic gates (not yet closed)

No sheet goes out to the public until **both** land (see `README.md`):

1. **The Rov's written sign-off** on the recovered zmanim definitions (esp. the
   8.4° motzaei-Shabbos/YT tzeis) and the confirmed errata.
2. **chabad.org's exact Sydney coordinate/elevation** pasted into
   `engine/zmanim.py` (currently fit-derived; source of the ±1-minute residuals).

Staging and review are fine now; distribution is not.

## Deploy

**Sheet service** (once, on a small host off SiteGround — a ~$5/mo VPS or a
container PaaS):
```sh
docker build -f service/Dockerfile -t ttcc-sheet-service .
docker run -d --restart=unless-stopped -e TTCC_SERVICE_TOKEN='<long-random-secret>' \
  -p 8000:8000 ttcc-sheet-service
```
Put it behind HTTPS (reverse proxy / the PaaS's TLS). Confirm `GET /health`
returns `{"status":"ok", ... "chromium":true}`.

**Plugin** (on ttcc.org.au): copy `wp-plugin/ttcc-zmanim/` into
`wp-content/plugins/` and activate. Then `Timesheets → Settings`: set the
service URL and the same token; the banner should go green (and show Chromium
available). Open `Timesheets → Schedule profiles` once to seed the schedule from
the engine defaults.

After the first install the plugin updates **over the air**: add a GitHub
read-only token in `Timesheets → Settings → GitHub update token`, and thereafter
new releases appear as one-click updates on the Plugins screen — no more
zip/upload. Cutting a release is a tag push; see `RELEASING.md`.

## Weekly workflow

1. `Timesheets → Dashboard`. Pick the week's Sunday (and end date for a
   multi-week sheet), press **Generate**.
2. Edit in the left panel; the right panel previews live with page-boundary
   guides so you can see it fit. Minyan times are editable; astronomical times
   (blue "zman" badge) are not. A ⚠ appears if an edit crosses a halachic bound
   — allowed, but check. **Revert** returns a line to the calculated value.
3. Add/remove lines and notes as needed. Give it a **Title**, set status, **Save**.
4. **Export**: PDF (print), PNG square (the sheet exactly as printed, centred on
   a 1:1 2160×2160 canvas — the shape WhatsApp shows in full, padded so a crop
   cannot clip a time; covers the first printed sheet), PNG portrait (3:4 for
   social/screens), or Word.
5. Past sheets live in **Archive** (edit/regenerate/re-export). Each records the
   engine version it was made with — regenerating after an engine update may
   change times; the stored snapshot reprints exactly as approved.

## Clergy self-service page

Put `[ttcc_generator]` on a normal page and any clergy member can produce a
sheet themselves — no wp-admin login, no styling decisions:

1. Pick the week beginning (Sunday) and how many weeks (1–4).
2. **Classic** or **Modern** — that is the only styling choice. Everything else
   (fonts, sizes, logo, colours) comes from the house design: the default style
   preset if one is saved, otherwise `Settings → Modern layout defaults`.
3. **Add or adjust times** opens the same kind of editor as the dashboard, with
   "+ Add a line" at the head of each week:
   change a minyan time, hide a line (it moves to "Hidden lines" so it can come
   back), add a line — with or without a time — and add or hide notes.
   Astronomical times stay read-only.
4. Above the preview, **Sheet / Square 1:1 / Tall 3:4** switches what is on
   screen. The two image views show the *actual rendered PNG* the download
   gives, so a sheet can be checked in its share shape before it goes out.
5. **Download PDF**, **WhatsApp image** (the printed sheet on a square 1:1
   canvas, ready to send), **WhatsApp
   text** (with Copy and "Open in WhatsApp"), or **Tall image** (3:4 for social).
   When a range fills more than one printed sheet — a yom-tov fortnight, say —
   the page says so: the square image covers the first sheet, the PDF has all
   of them.

A block that cannot fill its page — a light week, or `Fixed size` sizing — is
centred on it, so the leftover paper is shared between head and foot instead of
sitting under the sheet. Sheets on this page always **fill their page**: the design comes from the house
preset, but content sizing is forced to Fill, so the block is scaled up
uniformly — same fonts, same proportions — until it reaches the page. A preset
saved in `Fixed size` mode would otherwise print at its base font size and end
halfway down, which reads as dead paper on the PDF and a half-empty WhatsApp
image. (The dashboard keeps its Fixed option for an operator who wants it.)
The preview box also trims whatever paper is left, so it hugs the sheet and its
border.

The page never writes to the archive: edits made there are for that one sheet
and vanish on reload. Any corrections **you** saved in the dashboard for those
weeks are applied first, so a clergy member's sheet matches what the shul
published. Requests are capped at 4 weeks and rate-limited per visitor;
`Settings → Clergy generator` can restrict the page to signed-in users (or turn
it off), and unedited sheets are cached for 30 minutes so browsing weeks is
cheap.

## Public surfaces

- Current-week widget: put `[ttcc_week]` on any page/Elementor block.
- Browse page: `[ttcc_browse]` (read-only).
- Shabbos & Yom Tov banner: `[ttcc_shabbos]`.
- Clergy generator: `[ttcc_generator]` (see above).
- piSignage: the URL shown on the Settings page (`/ttcc-signage/<slug>/`).

## If the service is down

The dashboard banner turns red and Generate/preview/export are disabled; edits
you already have stay editable and save. Public pages keep serving the last
good copy. Restart the service container; the banner returns to green on the
next 30-second poll.

## Guardrails

- `engine/` and `phase0/fixtures/` are never modified by Phase 4. The three
  golden regressions must stay green after any change:
  `python3 engine/validate.py && python3 engine/validate_luach.py && python3 engine/validate_rules.py`.
- The service token is the only shared secret; rotate it by updating both the
  container env and the plugin Settings.
