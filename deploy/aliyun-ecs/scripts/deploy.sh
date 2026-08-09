#!/usr/bin/env bash
# Pull the configured image and bring the stack up. Idempotent: with nothing
# new to pull it is a no-op, which is what lets a timer or a webhook call it
# on a schedule without thinking about it.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

[ -f .env ] || { echo ".env missing — run ./scripts/bootstrap.sh first" >&2; exit 1; }

# shellcheck disable=SC1091
set -a; . ./.env; set +a

PORT="${OMNIGENT_PORT:-8000}"

echo "==> pulling ${OMNIGENT_IMAGE}:${OMNIGENT_IMAGE_TAG:-main}"
docker compose pull

echo "==> starting"
docker compose up -d

# Wait for health rather than declaring success on `up -d` returning: the
# container is up long before the server is answering, and a deploy that
# reports green while the app is crash-looping is worse than one that fails.
echo -n "==> waiting for health "
for _ in $(seq 1 60); do
    if curl -fsS -m 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
        echo
        echo "==> healthy: $(curl -fsS -m 3 "http://127.0.0.1:${PORT}/health")"
        docker compose ps
        exit 0
    fi
    echo -n .
    sleep 2
done

echo
echo "==> NOT healthy after 120s. Recent logs:" >&2
docker compose logs --tail 50 omnigent >&2
exit 1
