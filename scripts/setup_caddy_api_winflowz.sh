#!/usr/bin/env bash
set -Eeuo pipefail

DOMAIN="${DOMAIN:-api.winflowz.com}"
UPSTREAM="${UPSTREAM:-localhost:3000}"
CADDYFILE="${CADDYFILE:-/etc/caddy/Caddyfile}"
LOG_DIR="${LOG_DIR:-/var/log/contentflow}"
TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
LOG_FILE="$LOG_DIR/caddy-setup-$TIMESTAMP.log"
TMP_CADDYFILE="/tmp/Caddyfile.${DOMAIN}.${TIMESTAMP}"

mkdir -p "$LOG_DIR"
touch "$LOG_FILE"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

run() {
  log "+ $*"
  "$@" 2>&1 | tee -a "$LOG_FILE"
}

cleanup() {
  rm -f "$TMP_CADDYFILE"
}

trap cleanup EXIT
trap 'log "ERROR: script failed at line $LINENO"; exit 1' ERR

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

log "Starting Caddy setup for $DOMAIN -> $UPSTREAM"
log "Logs: $LOG_FILE"

if ! command -v caddy >/dev/null 2>&1; then
  log "ERROR: caddy is not installed"
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  log "ERROR: curl is required"
  exit 1
fi

log "Checking local API health before changing Caddy"
run curl -i --max-time 10 "http://${UPSTREAM}/health"

if [[ -f "$CADDYFILE" ]]; then
  BACKUP_FILE="${CADDYFILE}.bak.${TIMESTAMP}"
  log "Backing up existing Caddyfile to $BACKUP_FILE"
  run cp "$CADDYFILE" "$BACKUP_FILE"
fi

cat > "$TMP_CADDYFILE" <<EOF
${DOMAIN} {
    reverse_proxy ${UPSTREAM}
    encode gzip
}
EOF

log "Generated candidate Caddyfile at $TMP_CADDYFILE"
run cat "$TMP_CADDYFILE"

log "Validating candidate Caddyfile"
run caddy validate --config "$TMP_CADDYFILE"

log "Installing candidate Caddyfile to $CADDYFILE"
run cp "$TMP_CADDYFILE" "$CADDYFILE"

log "Reloading Caddy"
run systemctl reload caddy

log "Waiting briefly for Caddy to apply config"
sleep 3

log "Testing HTTP endpoint"
run curl -I --max-time 15 "http://${DOMAIN}/health"

log "Testing HTTPS endpoint"
if curl -I --max-time 20 "https://${DOMAIN}/health" 2>&1 | tee -a "$LOG_FILE"; then
  log "HTTPS check succeeded"
else
  log "HTTPS check failed; collecting diagnostics"
  run journalctl -u caddy -n 80 --no-pager
  exit 1
fi

log "Completed successfully"
log "Public API base URL: https://${DOMAIN}"
