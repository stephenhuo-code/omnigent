#!/usr/bin/env bash
# Restore a backup from OSS.
#
#   ./scripts/restore.sh                       # list what is available
#   ./scripts/restore.sh omnigent-db-2026-08-09-0300.sql.gz
#
# Restores into a SCRATCH database by default and prints how to inspect it.
# A backup nobody has restored is not a backup, and the way to keep that
# check cheap is to make the safe path the default one — overwriting the live
# database takes an explicit --into flag.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

[ -f .env ] || { echo ".env missing" >&2; exit 1; }
# shellcheck disable=SC1091
set -a; . ./.env; set +a

: "${OSS_BUCKET:?set OSS_BUCKET in .env}"
PREFIX="${OSS_BACKUP_PREFIX:-backup}"
PG_USER="${POSTGRES_USER:-omnigent}"

command -v ossutil >/dev/null || { echo "ossutil not found — see README" >&2; exit 1; }

OBJECT=""
TARGET_DB="omnigent_restore_check"
while [ $# -gt 0 ]; do
    case "$1" in
        --into) TARGET_DB="$2"; shift 2 ;;
        *)      OBJECT="$1"; shift ;;
    esac
done

if [ -z "$OBJECT" ]; then
    echo "==> available backups in oss://${OSS_BUCKET}/${PREFIX}/"
    ossutil ls "oss://${OSS_BUCKET}/${PREFIX}/"
    echo
    echo "usage: $0 <object-name> [--into <dbname>]"
    exit 0
fi

local_file="/var/tmp/${OBJECT}"
trap 'rm -f "$local_file"' EXIT

echo "==> downloading ${OBJECT}"
ossutil cp -f "oss://${OSS_BUCKET}/${PREFIX}/${OBJECT}" "$local_file"
[ -s "$local_file" ] || { echo "downloaded file is empty" >&2; exit 1; }

if [ "$TARGET_DB" = "${POSTGRES_DB:-omnigent}" ]; then
    echo
    echo "!! About to restore over the LIVE database '${TARGET_DB}'."
    echo "!! Stop the server first (docker compose stop omnigent) or it will"
    echo "!! write to a database being replaced underneath it."
    read -r -p "Type the database name to confirm: " confirm
    [ "$confirm" = "$TARGET_DB" ] || { echo "aborted" >&2; exit 1; }
fi

echo "==> recreating database ${TARGET_DB}"
docker compose exec -T postgres psql -U "$PG_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS \"${TARGET_DB}\";"
docker compose exec -T postgres psql -U "$PG_USER" -d postgres \
    -c "CREATE DATABASE \"${TARGET_DB}\";"

echo "==> restoring"
gunzip -c "$local_file" | docker compose exec -T postgres psql -q -U "$PG_USER" -d "$TARGET_DB"

echo "==> table count in ${TARGET_DB}:"
docker compose exec -T postgres psql -tA -U "$PG_USER" -d "$TARGET_DB" \
    -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"

echo
echo "==> restored into '${TARGET_DB}'. Compare against the live database:"
echo "    docker compose exec postgres psql -U ${PG_USER} -d ${POSTGRES_DB:-omnigent} \\"
echo "      -c \"SELECT count(*) FROM information_schema.tables WHERE table_schema='public';\""
