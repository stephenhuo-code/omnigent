#!/usr/bin/env bash
# Push this directory to the ECS box. Run from your laptop.
#
#   ./scripts/sync.sh root@1.2.3.4
#   OMNIGENT_REMOTE_DIR=/srv/omnigent ./scripts/sync.sh root@1.2.3.4
#
# The repository is the source of truth for configuration; secrets live only
# on the box. --delete makes the remote match the repo (so a file deleted here
# stops existing there), and --exclude .env keeps that from touching secrets.
set -euo pipefail

REMOTE="${1:-${OMNIGENT_REMOTE:-}}"
REMOTE_DIR="${OMNIGENT_REMOTE_DIR:-/opt/omniagent}"

if [ -z "$REMOTE" ]; then
    echo "usage: $0 <user@host>   (or set OMNIGENT_REMOTE)" >&2
    exit 2
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> syncing $HERE/ -> $REMOTE:$REMOTE_DIR/"
ssh "$REMOTE" "mkdir -p '$REMOTE_DIR'"

rsync -az --delete \
    --exclude '.env' \
    --exclude '.env.local' \
    --chmod=D755,F644 \
    "$HERE/" "$REMOTE:$REMOTE_DIR/"

# rsync's --chmod applies to files it writes; the +x bit has to be restored
# separately or deploy.sh arrives unrunnable.
ssh "$REMOTE" "chmod +x '$REMOTE_DIR'/scripts/*.sh"

echo "==> done. next:"
echo "    ssh $REMOTE"
echo "    cd $REMOTE_DIR && ./scripts/bootstrap.sh   # first time only"
echo "    ./scripts/deploy.sh"
