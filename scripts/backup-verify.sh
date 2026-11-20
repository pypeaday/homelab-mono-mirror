#!/usr/bin/env bash
# backup-verify.sh — prove the restic repo actually restores.
#
#   backup-verify.sh                 # full check + restore test + freshness
#   CHECK_ONLY=1 backup-verify.sh    # integrity check only (fast, no restore)
#
# Env:
#   RESTIC_REPO   default sftp:nic@192.168.1.9:/tank/encrypted/nas/nic-home/
#   RESTIC_KEY    default dataops/systemd/restic-docker-compose/.ssh/id_rsa
#   MAX_STALE_DAYS  default 10  (alert if newest snapshot older than this)
#   GOTIFY_URL/GOTIFY_TOKEN  optional - notify on failure
set -euo pipefail

REPO="${RESTIC_REPO:-sftp:nic@192.168.1.9:/tank/encrypted/nas/nic-home/}"
KEY="${RESTIC_KEY:-dataops/systemd/restic-docker-compose/.ssh/id_rsa}"
PASSFILE="${RESTIC_PASSWORD_FILE:-dataops/systemd/restic-docker-compose/.restic-password}"
MAX_STALE_DAYS="${MAX_STALE_DAYS:-10}"

export RESTIC_PASSWORD_FILE="$PASSFILE"
# accept-new: self-heals across host rebuilds; known_hosts in repo may be stale
SSH_OPTS="-i $KEY -o StrictHostKeyChecking=accept-new -o BatchMode=yes"
if [ -n "${RESTIC_KNOWN_HOSTS:-}" ]; then
  SSH_OPTS="$SSH_OPTS -o UserKnownHostsFile=$RESTIC_KNOWN_HOSTS"
fi
RESTIC=(restic -r "$REPO" -o "sftp.args=$SSH_OPTS")

notify() {
  [ -n "${GOTIFY_URL:-}" ] && [ -n "${GOTIFY_TOKEN:-}" ] || return 0
  curl -sf -X POST "$GOTIFY_URL?token=$GOTIFY_TOKEN" \
    -F "title=${2:-backup-verify}" -F "message=$1" -F "priority=${3:-8}" || true
}

if ! command -v restic >/dev/null; then
  echo "installing restic..."
  curl -sL https://github.com/restic/restic/releases/download/v0.18.1/restic_0.18.1_linux_amd64.bz2 \
    | bunzip2 > /tmp/restic && chmod +x /tmp/restic
  RESTIC[0]=/tmp/restic
fi

echo "=== restic check ==="
"${RESTIC[@]}" check
echo "check OK"

RESTORE_TARGET="${RESTORE_TARGET:-/tmp/restic-verify}"

if [ "${CHECK_ONLY:-0}" != "1" ]; then
  mkdir -p "$RESTORE_TARGET"
  if [ "${FULL_RESTORE:-0}" = "1" ]; then
    echo "=== restore test (FULL) ==="
    find "$RESTORE_TARGET" -mindepth 1 -delete
    "${RESTIC[@]}" restore latest --target "$RESTORE_TARGET"
  else
    echo "=== restore test (subset) ==="
    rm -rf "$RESTORE_TARGET" && mkdir -p "$RESTORE_TARGET"
    # RESTORE_INCLUDE: small path that should exist in every snapshot
    "${RESTIC[@]}" restore latest --target "$RESTORE_TARGET" \
      --include "${RESTORE_INCLUDE:-/source/.ssh}"
  fi
  count=$(find "$RESTORE_TARGET" -type f | wc -l)
  size=$(du -s "$RESTORE_TARGET" | cut -f1)
  echo "restored $count files (${size}K)"
  [ "$count" -ge 1 ] && [ "$size" -gt 0 ] || { echo "restore produced nothing"; exit 1; }
fi

echo "=== snapshot freshness ==="
latest=$("${RESTIC[@]}" snapshots --json --latest 1 | python3 -c "import json,sys; print(max(e['time'] for e in json.load(sys.stdin)))")
days=$(( ( $(date +%s) - $(date -d "$latest" +%s) ) / 86400 ))
echo "latest snapshot: $latest (${days}d ago)"
if [ "$days" -gt "$MAX_STALE_DAYS" ]; then
  notify "Latest backup snapshot is ${days} days old — backups appear STOPPED" "backup stale" 8
  echo "FAIL: backup stale"
  exit 1
fi

echo "=== all good ==="
notify "restic check+restore OK (${count:-0} files, snapshot ${days}d old)" "backup verified" 3
