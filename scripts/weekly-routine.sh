#!/bin/bash
# weekly-routine.sh — Run the weekly review
#
# USAGE:
#   ./scripts/weekly-routine.sh
#
# Unlike the evening routine, no adapters are needed here — all data
# is already in the vault from daily routines (diary entries, profile
# updates, commitment changes). This script just sets up logging and
# invokes the weekly review briefing.
#
# LOGS:
#   ~/.local/log/generous-ledger/weekly-YYYY-MM-DD.log

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$HOME/.local/log/generous-ledger"
LOG_FILE="$LOG_DIR/weekly-$(date +%Y-%m-%d).log"

mkdir -p "$LOG_DIR"

log() {
    echo "$(date '+%H:%M:%S') $1" | tee -a "$LOG_FILE"
}

log "=== Weekly Routine — $(date) ==="

# Run weekly review briefing
log "RUN  weekly-review"
if bash "$SCRIPT_DIR/weekly-review-briefing.sh" >> "$LOG_FILE" 2>&1; then
    log "OK   weekly-review"
else
    log "FAIL weekly-review (exit $?)"
fi

log "=== Weekly Routine Complete ==="
