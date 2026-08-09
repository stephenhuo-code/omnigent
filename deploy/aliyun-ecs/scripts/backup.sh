#!/usr/bin/env bash
# Dump Postgres and upload it to OSS, then prune old objects.
#
# Dumps to a file before uploading rather than piping straight into ossutil:
# a pipeline hides pg_dump's exit status behind gzip's, and an empty dump
# would upload cleanly and sit there looking like a backup. Checking the file
# first is what makes a silent failure loud.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

[ -f .env ] || { echo ".env missing" >&2; exit 1; }
# shellcheck disable=SC1091
set -a; . ./.env; set +a

: "${OSS_BUCKET:?set OSS_BUCKET in .env}"
PREFIX="${OSS_BACKUP_PREFIX:-backup}"
RETENTION="${BACKUP_RETENTION_DAYS:-30}"
PG_USER="${POSTGRES_USER:-omnigent}"
PG_DB="${POSTGRES_DB:-omnigent}"

command -v ossutil >/dev/null || { echo "ossutil not found — see README" >&2; exit 1; }

stamp="$(date +%F-%H%M)"
dump="/var/tmp/omnigent-db-${stamp}.sql.gz"
trap 'rm -f "$dump"' EXIT

echo "==> dumping ${PG_DB}"
# PIPESTATUS rather than `set -o pipefail` alone, so the message names which
# half failed instead of just reporting a non-zero pipeline.
docker compose exec -T postgres pg_dump -U "$PG_USER" "$PG_DB" | gzip > "$dump"
status=("${PIPESTATUS[@]}")
if [ "${status[0]}" -ne 0 ]; then
    echo "pg_dump failed (exit ${status[0]})" >&2
    exit 1
fi
if [ "${status[1]}" -ne 0 ]; then
    echo "gzip failed (exit ${status[1]})" >&2
    exit 1
fi

if [ ! -s "$dump" ]; then
    echo "dump is empty — refusing to upload" >&2
    exit 1
fi

size="$(du -h "$dump" | cut -f1)"
echo "==> uploading ${dump##*/} (${size})"
ossutil cp -f "$dump" "oss://${OSS_BUCKET}/${PREFIX}/"

echo "==> pruning objects older than ${RETENTION} days"
# --include restricts the delete to our own dumps: the prefix may hold other
# things, and a mis-scoped recursive delete is not recoverable.
cutoff="$(date -u -d "${RETENTION} days ago" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
    || date -u -v-"${RETENTION}"d +%Y-%m-%dT%H:%M:%SZ)"
ossutil rm -r -f \
    --include "omnigent-db-*.sql.gz" \
    --end-time "$cutoff" \
    "oss://${OSS_BUCKET}/${PREFIX}/" || {
        echo "prune failed — the upload above still succeeded" >&2
        exit 1
    }

echo "==> backup complete: oss://${OSS_BUCKET}/${PREFIX}/${dump##*/}"
