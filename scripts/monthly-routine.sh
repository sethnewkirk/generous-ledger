#!/bin/bash
# monthly-routine.sh — Run the monthly review
#
# USAGE:
#   ./scripts/monthly-routine.sh
#
# Like the weekly routine, no adapters are needed here — all data
# is already in the vault from daily and weekly routines (diary entries,
# weekly reviews, profile updates, commitment changes). This script
# just sets up logging and invokes the monthly review briefing.
#
# LOGS:
#   ~/.local/log/generous-ledger/monthly-YYYY-MM-DD.log

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$HOME/.local/log/generous-ledger"
LOG_FILE="$LOG_DIR/monthly-$(date +%Y-%m-%d).log"

mkdir -p "$LOG_DIR"

log() {
    echo "$(date '+%H:%M:%S') $1" | tee -a "$LOG_FILE"
}

log "=== Monthly Routine — $(date) ==="

# Run monthly review briefing
log "RUN  monthly-review"
if bash "$SCRIPT_DIR/monthly-review-briefing.sh" >> "$LOG_FILE" 2>&1; then
    log "OK   monthly-review"
else
    log "FAIL monthly-review (exit $?)"
fi

log "=== Monthly Routine Complete ==="
