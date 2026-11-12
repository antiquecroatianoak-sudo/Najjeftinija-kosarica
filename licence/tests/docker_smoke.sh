#!/usr/bin/env bash
# Docker smoke test (docs/DEPLOY.md): build, refuse insecure config, run hardened,
# health, auth, CRUD, persistence across restart, integrity check, backup.
# Usage: tests/docker_smoke.sh [image-tag]
set -euo pipefail
IMAGE="${1:-license-pulse:ci}"
NAME="lp-smoke-$$"
VOL="lp-smoke-$$"
PORT="${SMOKE_PORT:-18080}"
PASS="smoke-lozinka-123"
fail() { echo "FAIL: $*"; docker logs "$NAME" 2>&1 | tail -20 || true; exit 1; }
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; docker volume rm -f "$VOL" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker build -q -t "$IMAGE" "$(dirname "$0")/.." >/dev/null
echo "ok   build"

set +e; docker run --rm "$IMAGE" >/dev/null 2>&1; code=$?; set -e
[ "$code" = 2 ] || fail "production without LICENCE_SECRET_KEY must exit 2 (got $code)"
echo "ok   refuses to start without secret key"

wait_healthy() {
  for _ in $(seq 1 40); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' "$NAME")" = healthy ] && return 0
    sleep 1
  done
  fail "container not healthy"
}

docker volume create "$VOL" >/dev/null
docker run -d --name "$NAME" -p "127.0.0.1:$PORT:8000" --read-only --tmpfs /tmp --cap-drop ALL \
  --security-opt no-new-privileges:true -v "$VOL:/data" \
  -e LICENCE_SECRET_KEY="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')" \
  -e LICENCE_ADMIN_USER=admin -e LICENCE_ADMIN_PASSWORD="$PASS" -e LICENCE_ADMIN_ORG="Smoke d.o.o." \
  -e LICENCE_RATES_AUTO=0 "$IMAGE" >/dev/null
wait_healthy
echo "ok   healthy"

[ "$(docker exec "$NAME" id -u)" = 10001 ] || fail "must run as uid 10001"
docker exec "$NAME" sh -c 'touch /app/x' 2>/dev/null && fail "/app must be read-only"
echo "ok   non-root, read-only"

URL="http://127.0.0.1:$PORT"
[ "$(curl -s -o /dev/null -w '%{http_code}' "$URL/")" = 401 ] || fail "page without login must be 401"
curl -sI -u "admin:$PASS" "$URL/" | grep -qi "content-security-policy: default-src 'self'" || fail "CSP header missing"
code=$(curl -s -o /dev/null -w '%{http_code}' -u "admin:$PASS" -X POST -H 'Content-Type: application/json' \
  -H 'X-Requested-With: LicensePulse' -d '{"name":"Slack","category":"Komunikacija","cost":"8.75","currency":"EUR","billing_cycle":"monthly","start_date":"2025-01-01"}' \
  "$URL/api/licenses")
[ "$code" = 201 ] || fail "create license (got $code)"
echo "ok   auth, headers, create"

docker restart "$NAME" >/dev/null
wait_healthy
curl -s -u "admin:$PASS" "$URL/api/licenses" | grep -q '"name": "Slack"' || fail "data lost after restart"
docker exec "$NAME" python3 -m licence_app check >/dev/null || fail "integrity check"
docker exec "$NAME" python3 -m licence_app backup /data/backups >/dev/null || fail "backup"
echo "ok   persistence, integrity check, backup"
echo "DOCKER SMOKE OK"
