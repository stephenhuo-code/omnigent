#!/usr/bin/env bash
# First-run setup on the ECS box: create .env with freshly generated secrets
# and leave the operator-supplied ones blank.
#
# Idempotent in the way that matters — it refuses to overwrite an existing
# .env, because doing so would rotate the cookie secret (logging everyone
# out) and orphan the Postgres volume from its password.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ -f .env ]; then
    echo ".env already exists — leaving it alone." >&2
    echo "To start over: mv .env .env.bak && $0" >&2
    exit 1
fi

command -v openssl >/dev/null || { echo "openssl not found" >&2; exit 1; }

POSTGRES_PASSWORD="$(openssl rand -hex 16)"
COOKIE_SECRET="$(openssl rand -hex 32)"

sed \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD}|" \
    -e "s|^OMNIGENT_ACCOUNTS_COOKIE_SECRET=.*|OMNIGENT_ACCOUNTS_COOKIE_SECRET=${COOKIE_SECRET}|" \
    .env.example > .env

chmod 600 .env

cat <<'EOF'
==> .env created with generated POSTGRES_PASSWORD and cookie secret.

Still to fill in by hand (open .env in an editor):

  OMNIGENT_IMAGE                        ACR VPC address for omnigent-server
  OMNIGENT_ACCOUNTS_BASE_URL            http://<this box's public IP>:8000
  OMNIGENT_ACCOUNTS_INIT_ADMIN_PASSWORD a strong password for the `admin` user
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY   the OSS RAM user's key
  OMNIGENT_ARTIFACT_URI                 s3://<bucket>/artifacts
  OSS_BUCKET                            <bucket>

Then authenticate to the registry once (credentials persist in
~/.docker/config.json, so deploys afterwards need no password):

  docker login <ACR VPC host> -u <aliyun account name>

Then: ./scripts/deploy.sh
EOF
