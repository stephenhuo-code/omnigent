#!/usr/bin/env bash
# Push this directory to the ECS box. Run from your laptop.
#
#   ./scripts/sync.sh root@1.2.3.4
#   OMNIGENT_REMOTE_DIR=/srv/omnigent ./scripts/sync.sh root@1.2.3.4
#
# Edit .env here, not over SSH — the repo's .gitignore covers .env and
# **/.env, so a filled-in one cannot be committed by accident. It ships with
# 0600 and lands as the box's .env.
#
# --delete makes the remote match the repo, so a file deleted here stops
# existing there. That is what keeps the box reconstructible: nothing
# survives on it that is not in version control (except .env itself).
set -euo pipefail

REMOTE="${1:-${OMNIGENT_REMOTE:-}}"
REMOTE_DIR="${OMNIGENT_REMOTE_DIR:-/opt/omniagent}"

if [ -z "$REMOTE" ]; then
    echo "usage: $0 <user@host>   (or set OMNIGENT_REMOTE)" >&2
    exit 2
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -f "$HERE/.env" ]; then
    echo "no .env here yet. Create one first:" >&2
    echo "    cp $HERE/.env.example $HERE/.env" >&2
    echo "    ./scripts/gen-secrets.sh          # fills the two random secrets" >&2
    echo "    \$EDITOR $HERE/.env               # fill the rest" >&2
    exit 1
fi

echo "==> syncing $HERE/ -> $REMOTE:$REMOTE_DIR/"
ssh "$REMOTE" "mkdir -p '$REMOTE_DIR'"

# No --chmod: macOS ships openrsync, which rejects it. Permissions are set
# explicitly below anyway, which is the portable thing to rely on.
rsync -az --delete "$HERE/" "$REMOTE:$REMOTE_DIR/"

ssh "$REMOTE" "chmod +x '$REMOTE_DIR'/scripts/*.sh && chmod 600 '$REMOTE_DIR'/.env"

echo "==> done. next:"
echo "    ssh $REMOTE 'cd $REMOTE_DIR && ./scripts/deploy.sh'"
