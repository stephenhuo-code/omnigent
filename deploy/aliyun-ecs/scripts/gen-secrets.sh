#!/usr/bin/env bash
# Fill the two generated secrets in .env. Run locally, before sync.sh.
#
# Creates .env from .env.example if it does not exist, then writes a random
# POSTGRES_PASSWORD and OMNIGENT_ACCOUNTS_COOKIE_SECRET into it. The rest
# (image address, public IP, admin password, OSS keys) you fill in yourself.
#
# Only fills blanks. Rotating the cookie secret signs everyone out, and
# rotating the Postgres password orphans an existing volume from its
# credentials — so a value already present is left alone.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

command -v openssl >/dev/null || { echo "openssl not found" >&2; exit 1; }

if [ ! -f .env ]; then
    cp .env.example .env
    echo "==> created .env from .env.example"
fi
chmod 600 .env

fill() {  # fill <KEY> <value> — only when the key's value is empty
    local key="$1" value="$2"
    if grep -qE "^${key}=.+" .env; then
        echo "    ${key} already set, leaving it"
        return
    fi
    # A trailing sed -i '' differs between GNU and BSD; a temp file avoids
    # caring which one is on the box.
    sed -e "s|^${key}=.*|${key}=${value}|" .env > .env.tmp
    mv .env.tmp .env
    chmod 600 .env
    echo "    ${key} generated"
}

fill POSTGRES_PASSWORD "$(openssl rand -hex 16)"
fill OMNIGENT_ACCOUNTS_COOKIE_SECRET "$(openssl rand -hex 32)"

cat <<'EOF'

==> now fill in the rest of .env by hand:

  OMNIGENT_IMAGE                        the ACR address for omnigent-server
  OMNIGENT_IMAGE_TAG                    sha-<short> while validating
  OMNIGENT_ACCOUNTS_BASE_URL            http://<ECS public IP>:8000
  OMNIGENT_ACCOUNTS_INIT_ADMIN_PASSWORD a strong password for the `admin` user
  OMNIGENT_ARTIFACT_URI / OSS_BUCKET    your bucket
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY   the OSS RAM user's key

then:  ./scripts/sync.sh root@<ECS IP>

.env is covered by the repo's .gitignore, so a filled-in copy cannot be
committed by accident.
EOF
