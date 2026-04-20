#!/bin/bash
# monthly-routine.sh — Run the monthly review

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$HOME/.local/log/generous-ledger"
LOG_FILE="$LOG_DIR/monthly-$(date +%Y-%m-%d).log"

source "$SCRIPT_DIR/lib/provider-runner.sh"

gl_parse_common_args "$@" || exit 1
if [ ${#REMAINING_ARGS[@]} -ne 0 ]; then
    echo "USAGE: ./scripts/monthly-routine.sh [--provider codex|claude] [--vault PATH]" >&2
    exit 1
fi

PROVIDER="$(gl_resolve_provider "$COMMON_PROVIDER")" || exit 1
VAULT_PATH="$(gl_resolve_vault_path "$COMMON_VAULT")"

mkdir -p "$LOG_DIR"

log() {
    echo "$(date '+%H:%M:%S') $1" | tee -a "$LOG_FILE"
}

log "=== Monthly Routine ($(gl_provider_display_name "$PROVIDER")) — $(date) ==="

log "RUN  monthly-review"
if bash "$SCRIPT_DIR/monthly-review-briefing.sh" --provider "$PROVIDER" --vault "$VAULT_PATH" >> "$LOG_FILE" 2>&1; then
    log "OK   monthly-review"
    log "=== Monthly Routine Complete ==="
    exit 0
else
    EXIT_CODE=$?
    log "FAIL monthly-review (exit $EXIT_CODE)"
    exit $EXIT_CODE
fi
