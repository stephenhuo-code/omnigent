#!/usr/bin/env bash
# Report which .env values are still placeholders. Prints key names only —
# never values — so it is safe to paste the output anywhere.
#
# Run before sync.sh. A placeholder that reaches the box fails at a much
# less obvious moment: a half-substituted image address surfaces as a
# registry auth error, and a wrong BASE_URL only shows up when an invite
# link points somewhere that does not exist.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

[ -f .env ] || { echo "no .env — run ./scripts/gen-secrets.sh first" >&2; exit 1; }

missing=0
while IFS= read -r line; do
    case "$line" in ''|'#'*) continue ;; esac
    key="${line%%=*}"
    val="${line#*=}"
    case "$key" in [A-Z]*) ;; *) continue ;; esac

    reason=""
    if [ -z "$val" ]; then
        reason="empty"
    else
        # Placeholders in .env.example take three shapes: <angle brackets>,
        # runs of x as a stand-in for an ID, and the literal example domain.
        case "$val" in
            *'<'*'>'*)      reason="placeholder <...>" ;;
            *xxxxxxxx*)     reason="placeholder xxxx" ;;
            *example.com*)  reason="example domain" ;;
        esac
    fi

    if [ -n "$reason" ]; then
        printf '  ✗ %-40s %s\n' "$key" "$reason"
        missing=$((missing + 1))
    fi
done < .env

if [ "$missing" -eq 0 ]; then
    echo "==> .env looks complete"
else
    echo
    echo "==> $missing value(s) still need filling in" >&2
    exit 1
fi
