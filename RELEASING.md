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

## Notes

- Releasing only affects the **plugin**. The Python **sheet service** deploys
  separately to Cloud Run (`git pull` + `gcloud run deploy` — see `service/README.md`).
- The version you tag must be **higher** than the installed version for the
  update to register.
