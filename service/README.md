# TTCC sheet service

A thin HTTP wrapper around the fixture-validated Python engine (`engine/`), so the
WordPress plugin (PHP, on SiteGround — no shell/Chromium) can generate block data
and rendered output over HTTPS. See `../WARPLAN.md` §4 and the plan record for the
architecture (option a: Python engine is the source of truth; PHP calls this service).

**The service never recomputes or re-rounds a time.** Every value comes verbatim from
`engine.assemble.generate`. It is stateless — all persistence lives in WordPress.

## Endpoints

All require `Authorization: Bearer <TTCC_SERVICE_TOKEN>` except `/health`.

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | — | `{status, engine_version, chromium}` |
| POST | `/generate` | `{start, end, profiles?, notes?, overrides?}` | block dict + `engine_version` |
| POST | `/render/html` | `{start,end,…}` **or** `{doc}` (+`variant?`) | `{html, engine_version}` |
| POST | `/render/pdf` | same as render/html | `application/pdf` |
| POST | `/render/png` | same (+`variant:"portrait"`) | `image/png` (3:4 social) |
| POST | `/render/docx` | same | `.docx` (optional Word copy) |
| GET | `/profiles/default` | — | `{profiles, notes}` seed data for the editor |

> The health endpoint is `/health`, **not** `/healthz`: Google Cloud Run's
> frontend intercepts the literal `/healthz` path and returns its own 404 before
> the request reaches the container. Don't rename it back.

`start`/`end` are ISO dates. `overrides` is keyed by `rule_id`
(`{"<id>":{"time":"19:15"}}` edit, `{"<id>":{"suppress":true}}` drop,
`{"add:<id>":{…}}` insert). Passing `{doc}` to a render endpoint reprints a stored
snapshot without recomputing.

## Configuration (env)

| Var | Default | Meaning |
|---|---|---|
| `TTCC_SERVICE_TOKEN` | — | shared secret; **required** unless `TTCC_ALLOW_NO_AUTH=1` |
| `TTCC_ALLOW_NO_AUTH` | — | `1` disables auth (local dev only) |
| `TTCC_MAX_RANGE_DAYS` | `120` | cap on `end - start` |
| `TTCC_RENDER_TIMEOUT_MS` | `20000` | Chromium timeout |
| `TTCC_CHROMIUM_PATH` | — | override the Chromium executable (else auto-detect) |
| `PLAYWRIGHT_BROWSERS_PATH` | — | where the `chromium` symlink lives |

## Run

```sh
# from the repo root
pip install -r service/requirements.txt
TTCC_SERVICE_TOKEN=secret uvicorn service.app:app --host 0.0.0.0 --port 8000
```

Docker (bundles Chromium; the `Dockerfile` lives at the repo root):

```sh
docker build -t ttcc-sheet-service .
docker run -e TTCC_SERVICE_TOKEN=secret -p 8000:8000 ttcc-sheet-service
```

Google Cloud Run (from the repo root; auto-detects the root Dockerfile):

```sh
gcloud run deploy ttcc-sheet-service --source . --region <region> \
  --allow-unauthenticated --memory 2Gi --cpu 1 --concurrency 4 \
  --min-instances 0 --max-instances 2 --timeout 120 \
  --set-env-vars TTCC_SERVICE_TOKEN=<token>
```

The container honors Cloud Run's `$PORT` (falls back to 8000 elsewhere).

## Tests

```sh
python3 -m service.tests.test_service     # no pytest needed
```

Covers the adapter round-trip identity (`DEFAULT_PROFILES == from_json(to_json(...))`),
engine parity (`/generate` and `/render/html` equal a direct engine call), auth, the
range cap, and — when Chromium is present — PDF/PNG rasterization.

## Deployment note

`engine/` and `phase0/fixtures/` are never modified by the service. The three golden
regressions (`python3 engine/validate.py`, `engine/validate_luach.py`,
`engine/validate_rules.py`) stay green and should run in CI alongside the service tests.
