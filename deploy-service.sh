#!/usr/bin/env bash
#
# Deploy the Python sheet service to Cloud Run.
#
# Use this instead of typing `gcloud run deploy` by hand. It exists because two
# traps have bitten this service in production, and both are silent:
#
#   1. Running the deploy from the WRONG DIRECTORY. `--source .` uploads
#      whatever is in the current directory, and in Cloud Shell the prompt
#      "~ (tt-zmanim)" shows the GCP *project*, not a folder — so it is easy to
#      deploy an empty home directory. gcloud then finds no Dockerfile, falls
#      back to Buildpacks, and ships a static file server that answers every
#      path with 404 "File not found.". The plugin goes offline and the cause is
#      nowhere near the symptom. This script always deploys the repo it lives
#      in, whatever directory you call it from, and refuses to run if that repo
#      does not look right.
#
#   2. Forgetting --clear-base-image. Once a Buildpacks deploy has happened, the
#      service carries automatic base-image tracking, which is incompatible with
#      a Dockerfile build, and every later deploy fails until the flag clears it.
#      Passed automatically below when the installed gcloud supports it.
#
# Deliberately NOT passed: --set-env-vars. On an existing service that flag
# replaces the whole environment, wiping TTCC_SERVICE_TOKEN and breaking both
# plugins. Set the token by hand, once, when you actually mean to change it.
#
# Usage:
#   ./deploy-service.sh                # test, deploy, verify
#   ./deploy-service.sh --skip-tests   # deploy without re-running the regressions
#
# Env overrides: SERVICE, REGION.
set -euo pipefail

SERVICE="${SERVICE:-ttcc-sheet-service}"
REGION="${REGION:-australia-southeast1}"
SKIP_TESTS=0
[[ "${1:-}" == "--skip-tests" ]] && SKIP_TESTS=1

# Trap 1: always operate on the repo this script lives in.
cd "$(dirname "$(readlink -f "$0")")"

for required in Dockerfile engine service; do
  if [[ ! -e "$required" ]]; then
    echo "error: $PWD does not look like the tt-zmanim repo (no '$required')." >&2
    echo "       Deploying from here would ship a Buildpacks static server." >&2
    exit 1
  fi
done
echo "==> deploying from $PWD ($(git rev-parse --short HEAD 2>/dev/null || echo 'not a git repo'))"

if [[ "$SKIP_TESTS" -eq 0 ]]; then
  echo "==> golden regressions"
  python3 engine/validate.py >/dev/null
  python3 engine/validate_luach.py >/dev/null
  python3 engine/validate_rules.py >/dev/null
  python3 -m engine.validate_dayview >/dev/null
  python3 -m engine.validate_davening >/dev/null
  echo "    all five pass"
fi

# Trap 2: clear base-image tracking, but only if this gcloud knows the flag.
base_image_flag=()
if gcloud run deploy --help 2>/dev/null | grep -q -- --clear-base-image; then
  base_image_flag=(--clear-base-image)
fi

echo "==> gcloud run deploy $SERVICE ($REGION)"
gcloud run deploy "$SERVICE" --source . --region "$REGION" \
  --allow-unauthenticated --memory 2Gi --cpu 1 --concurrency 4 \
  --min-instances 0 --max-instances 2 --timeout 120 \
  "${base_image_flag[@]}"

url="$(gcloud run services describe "$SERVICE" --region "$REGION" \
        --format='value(status.url)')"

# Verify the app is actually answering, not a Buildpacks file server. /health
# needs no token, and its engine_version should match the commit deployed above.
echo "==> GET $url/health"
health="$(curl -fsS --max-time 20 "$url/health" || true)"
echo "$health"
case "$health" in
  *engine_version*)
    echo "==> OK: the service is live"
    case "$health" in
      *'"chromium":true'*|*'"chromium": true'*) ;;
      *) echo "warning: chromium missing — PDF and image exports will fail" >&2 ;;
    esac
    ;;
  *)
    echo "error: /health did not return the app's JSON. A 'File not found.' body" >&2
    echo "       means a Buildpacks build is serving traffic; re-run this script." >&2
    exit 1
    ;;
esac
