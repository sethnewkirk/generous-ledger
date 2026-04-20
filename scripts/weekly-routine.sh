#!/bin/bash
# weekly-routine.sh — Run the weekly review

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$HOME/.local/log/generous-ledger"
LOG_FILE="$LOG_DIR/weekly-$(date +%Y-%m-%d).log"

source "$SCRIPT_DIR/lib/provider-runner.sh"

gl_parse_common_args "$@" || exit 1
if [ ${#REMAINING_ARGS[@]} -ne 0 ]; then
    echo "USAGE: ./scripts/weekly-routine.sh [--provider codex|claude] [--vault PATH]" >&2
    exit 1
fi

PROVIDER="$(gl_resolve_provider "$COMMON_PROVIDER")" || exit 1
VAULT_PATH="$(gl_resolve_vault_path "$COMMON_VAULT")"

mkdir -p "$LOG_DIR"

log() {
    echo "$(date '+%H:%M:%S') $1" | tee -a "$LOG_FILE"
}

log "=== Weekly Routine ($(gl_provider_display_name "$PROVIDER")) — $(date) ==="

log "RUN  weekly-review"
if bash "$SCRIPT_DIR/weekly-review-briefing.sh" --provider "$PROVIDER" --vault "$VAULT_PATH" >> "$LOG_FILE" 2>&1; then
    log "OK   weekly-review"
    log "=== Weekly Routine Complete ==="
    exit 0
else
    EXIT_CODE=$?
    log "FAIL weekly-review (exit $EXIT_CODE)"
    exit $EXIT_CODE
fi
