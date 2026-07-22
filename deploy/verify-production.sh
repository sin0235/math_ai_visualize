#!/usr/bin/env bash
set -euo pipefail

APP_ID="${APP_ID:-f94827d0-9d28-4047-9a06-68129dc99199}"
DB_CLUSTER_ID="${DB_CLUSTER_ID:-d1e9bd7a-b85f-4f29-ad5c-234a58740585}"
GITHUB_REPO="${GITHUB_REPO:-sin0235/ai-math-visualizer}"
PRODUCT_RULESET_ID="${PRODUCT_RULESET_ID:-18782037}"
BASE_URL="${BASE_URL:-https://starfish-app-e3i2c.ondigitalocean.app}"
MAX_BACKUP_AGE_HOURS="${MAX_BACKUP_AGE_HOURS:-36}"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

for command in curl date doctl gh jq rg; do
  command -v "$command" >/dev/null || fail "missing command: $command"
done

app_json="$(doctl apps get "$APP_ID" --output json)"
app="$(jq 'if type == "array" then .[0] else . end' <<<"$app_json")"
service_name="$(jq -r '.spec.services[0].name' <<<"$app")"

[[ "$(jq -r '.active_deployment.phase' <<<"$app")" == "ACTIVE" ]] || fail "deployment is not ACTIVE"
[[ "$(jq -r '.spec.services[0].github.branch' <<<"$app")" == "product" ]] || fail "deploy branch is not product"
[[ "$(jq -r '.spec.services[0].github.deploy_on_push' <<<"$app")" == "true" ]] || fail "deploy_on_push is disabled"
[[ "$(jq -r '.spec.services[0].health_check.http_path' <<<"$app")" == "/api/health/ready" ]] || fail "readiness health check is not configured"

secret_keys=(
  APPWRITE_API_KEY D1_API_TOKEN FIREBASE_CREDENTIALS_JSON GOOGLE_OAUTH_CLIENT_SECRET
  NVIDIA_API_KEY OLLAMA_API_KEY OPENROUTER_API_KEY RESEND_API_KEY ROUTER9_API_KEY
  DATABASE_URL OPENAI_COMPAT_API_KEY CLOUDINARY_API_KEY CLOUDINARY_API_SECRET TURNSTILE_SECRET_KEY
)
for key in "${secret_keys[@]}"; do
  jq -e --arg key "$key" '.spec.services[0].envs | any(.key == $key and .type == "SECRET")' <<<"$app" >/dev/null \
    || fail "$key is not SECRET"
done

backups="$(doctl databases backups "$DB_CLUSTER_ID" --output json)"
latest_backup="$(jq -r 'max_by(.created_at).created_at // empty' <<<"$backups")"
[[ -n "$latest_backup" ]] || fail "no database backup found"
backup_age_hours="$(( ($(date -u +%s) - $(date -u -d "$latest_backup" +%s)) / 3600 ))"
(( backup_age_hours <= MAX_BACKUP_AGE_HOURS )) || fail "latest backup is ${backup_age_hours}h old"

ruleset="$(gh api "repos/${GITHUB_REPO}/rulesets/${PRODUCT_RULESET_ID}")"
jq -e '.enforcement == "active" and (.conditions.ref_name.include | index("refs/heads/product")) != null' <<<"$ruleset" >/dev/null \
  || fail "product ruleset is not active"
for check in "Backend tests" "Frontend build" "Docker build (smoke)"; do
  jq -e --arg check "$check" '.rules | any(.type == "required_status_checks" and (.parameters.required_status_checks | any(.context == $check)))' <<<"$ruleset" >/dev/null \
    || fail "missing required check: $check"
done
jq -e '.rules | any(.type == "pull_request")' <<<"$ruleset" >/dev/null || fail "pull requests are not required"

runtime_logs="$(doctl apps logs "$APP_ID" "$service_name" --type run --tail 200 2>&1)"
rg -q 'render-worker entered RUNNING state' <<<"$runtime_logs" || fail "render worker RUNNING evidence not found"

curl -fsS --connect-timeout 10 --max-time 20 "${BASE_URL}/api/health" >/dev/null
curl -fsS --connect-timeout 10 --max-time 20 "${BASE_URL}/api/health/ready" \
  | jq -e '.status == "ready" and .database.ok == true' >/dev/null

printf 'OK: deployment=%s backup=%s age=%sh branch=product health=ready worker=running ruleset=active\n' \
  "$(jq -r '.active_deployment.id' <<<"$app")" "$latest_backup" "$backup_age_hours"
