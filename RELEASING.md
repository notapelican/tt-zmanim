# Releasing the WordPress plugin (over-the-air updates)

The plugin updates itself from this repo's GitHub **releases** — no more
download / zip / upload. Cutting a release is three steps.

## One-time site setup

1. Create a **fine-grained personal access token** on GitHub with **read-only
   "Contents"** access to `notapelican/tt-zmanim` (Settings → Developer settings
   → Fine-grained tokens). No other scopes.
2. In wp-admin → **Timesheets → Settings → GitHub update token**, paste it and
   save. (Leave blank to turn OTA updates off.)

That's it — the site now checks the repo for new releases and shows the normal
"update available" prompt in **Plugins → Installed Plugins**.

## Cutting a release

1. Bump the version in **two places** in `wp-plugin/ttcc-zmanim/ttcc-zmanim.php`
   — the `Version:` header and the `TTCC_ZMANIM_VERSION` constant — to the new
   number (e.g. `0.2.0`). Commit.
2. Tag it `v<version>` and push the tag:
   ```sh
   git tag v0.2.0
   git push origin v0.2.0
   ```
3. The **Release plugin** GitHub Action (`.github/workflows/release-plugin.yml`)
   builds a plugin-only `ttcc-zmanim.zip` (just `wp-plugin/ttcc-zmanim/`, with
   the vendored update checker) and attaches it to the release for that tag.

Within a day the site shows the update (or click **Check for updates** on the
Plugins page to see it immediately), then **Update now** — one click.

## How it works

- `includes/class-ttcc-updater.php` runs the vendored **Plugin Update Checker**
  (`plugin-update-checker/`, MIT) in GitHub **release-assets** mode: the version
  comes from the release tag and the package is the attached zip. That's why the
  monorepo layout (the repo also holds `engine/` and `service/`) doesn't matter
  — only the plugin zip is installed.
- The GitHub token is sent server-side only, so it also authenticates the
  private-repo download.

## If an update ever installs the wrong thing

Symptom: WordPress reports the plugin was deactivated because its file does not
exist, and it disappears from the Plugins screen. Look in
`wp-content/plugins/ttcc-zmanim/` — if you see `engine/`, `service/` and
`wp-plugin/` in there, the **repo source zip** was installed instead of the
plugin zip, so there is no `ttcc-zmanim.php` at the top level.

Recovery: delete that folder in the host's file manager (a filesystem delete does
**not** run `uninstall.php`, so the tables and settings survive — only the
Plugins-screen *Delete* link drops them), then upload the release's
`ttcc-zmanim.zip` via Plugins → Add New → Upload Plugin and activate. Nothing is
stored in the plugin folder; the archive, presets and settings live in the
database, and activation only runs `dbDelta`.

Both ends of this are now closed and it should not recur: the updater requires a
matching release asset and will never fall back to the source zip
(`includes/class-ttcc-updater.php`), and the workflow attaches the zip to a
*draft* release before publishing it, so a site checking for updates can never
catch a release that has no asset yet.

## Notes

- Releasing only affects the **plugin**. The Python **sheet service** deploys
  separately to Cloud Run (`git pull` + `gcloud run deploy` — see `service/README.md`).
- The version you tag must be **higher** than the installed version for the
  update to register.
- If a release is ever cut by hand rather than by the workflow, attach
  `ttcc-zmanim.zip` **before** publishing it, for the same reason.
