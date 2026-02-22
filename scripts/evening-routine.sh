#!/bin/bash
# evening-routine.sh — Run data adapters, generate evening review, then clean up
#
# USAGE:
#   ./scripts/evening-routine.sh
#
# This is the recommended way to generate evening reviews. It ensures
# adapters run BEFORE the review, so the steward has fresh data.
# After the review is written, ephemeral data files are cleaned up.
#
# Sequence:
#   1. Gmail adapter (if credentials exist)
#   2. iMessage adapter (if chat.db is readable)
#   3. Evening briefing (Claude Code)
#   4. Cleanup ephemeral data (email + messages)
#
# LOGS:
#   ~/.local/log/generous-ledger/evening-YYYY-MM-DD.log

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ADAPTER_DIR="$SCRIPT_DIR/adapters"
LOG_DIR="$HOME/.local/log/generous-ledger"
LOG_FILE="$LOG_DIR/evening-$(date +%Y-%m-%d).log"
CRED_DIR="$HOME/.config/generous-ledger/credentials"
VAULT_PATH="$HOME/Documents/Achaean"

mkdir -p "$LOG_DIR"

log() {
    echo "$(date '+%H:%M:%S') $1" | tee -a "$LOG_FILE"
}

run_adapter() {
    local name="$1"
    local script="$ADAPTER_DIR/$name.py"
    local cred_file="$2"  # optional — skip check if empty

    if [ ! -f "$script" ]; then
        log "SKIP $name — script not found"
        return
    fi

    if [ -n "$cred_file" ] && [ ! -f "$cred_file" ]; then
        log "SKIP $name — credentials not configured"
        return
    fi

    log "RUN  $name"
    if python3 "$script" >> "$LOG_FILE" 2>&1; then
        log "OK   $name"
    else
        log "FAIL $name (exit $?)"
    fi
}

log "=== Evening Routine — $(date) ==="

# 1. Gmail (requires Google OAuth token)
run_adapter "gmail" "$CRED_DIR/google-gmail-token.json"

# 2. iMessage (requires readable chat.db)
CHAT_DB="$HOME/Library/Messages/chat.db"
if [ -r "$CHAT_DB" ]; then
    run_adapter "imessage" ""
else
    log "SKIP imessage — $CHAT_DB not readable"
fi

# 3. Evening briefing
log "RUN  briefing"
if bash "$SCRIPT_DIR/evening-briefing.sh" >> "$LOG_FILE" 2>&1; then
    log "OK   briefing"
else
    log "FAIL briefing (exit $?)"
fi

# 4. Cleanup ephemeral data files
log "RUN  cleanup"
rm -f "$VAULT_PATH/data/email/"*.md
rm -f "$VAULT_PATH/data/messages/"*.md
log "OK   cleanup"

log "=== Evening Routine Complete ==="
