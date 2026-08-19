#!/usr/bin/env bash
# Pull the configured image and bring the stack up. Idempotent: with nothing
# new to pull it is a no-op, which is what lets a timer or a webhook call it
# on a schedule without thinking about it.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

[ -f .env ] || { echo ".env missing — run ./scripts/bootstrap.sh first" >&2; exit 1; }

# shellcheck disable=SC1091
set -a; . ./.env; set +a

# With the HTTPS overlay the app publishes on loopback:8000 and Caddy owns
# 80/443, so OMNIGENT_PORT is not where the app answers.
if [ -n "${OMNIGENT_DOMAIN:-}" ]; then
    PORT=8000
else
    PORT="${OMNIGENT_PORT:-8000}"
fi

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
        HEALTHY=1
        break
    fi
    echo -n .
    sleep 2
done

if [ -z "${HEALTHY:-}" ]; then
    echo
    echo "==> NOT healthy after 120s. Recent logs:" >&2
    docker compose logs --tail 50 omnigent >&2
    exit 1
fi

# The app being up says nothing about TLS: on a first boot Caddy still has an
# ACME exchange to complete, and reporting green while https/ serves nothing
# is the failure this script exists to prevent. --resolve pins the connection
# to the local Caddy while leaving SNI and Host as the real domain, so this
# checks the issued certificate without needing the box to reach its own
# public IP (Aliyun EIPs do not reliably hairpin).
if [ -n "${OMNIGENT_DOMAIN:-}" ]; then
    echo -n "==> waiting for the certificate "
    for _ in $(seq 1 60); do
        if curl -fsS -m 5 --resolve "${OMNIGENT_DOMAIN}:443:127.0.0.1" \
            "https://${OMNIGENT_DOMAIN}/health" >/dev/null 2>&1; then
            echo
            echo "==> TLS ok: https://${OMNIGENT_DOMAIN}"
            docker compose ps
            exit 0
        fi
        echo -n .
        sleep 2
    done
    echo
    echo "==> no working certificate after 120s. Recent caddy logs:" >&2
    docker compose logs --tail 50 caddy >&2
    echo >&2
    echo "    HTTP-01 needs 80/tcp open to 0.0.0.0/0 — an egress-IP" >&2
    echo "    allowlist in the security group fails the challenge." >&2
    exit 1
fi

docker compose ps
