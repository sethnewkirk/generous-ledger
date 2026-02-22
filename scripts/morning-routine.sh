#!/bin/bash
# morning-routine.sh — Run data adapters then generate daily briefing
#
# USAGE:
#   ./scripts/morning-routine.sh
#
# This is the recommended way to generate daily briefings. It ensures
# adapters run BEFORE the briefing, so the steward has fresh data.
#
# Sequence:
#   1. Weather adapter (always — no credentials needed)
#   2. Calendar adapter (if credentials exist)
#   3. Gmail adapter (if credentials exist)
#   4. iMessage adapter (if chat.db readable)
#   5. Finance adapter (if credentials exist, only on Mondays)
#   6. Daily briefing (Claude Code)
#   7. Cleanup ephemeral data (email + messages)
#
# LOGS:
#   ~/.local/log/generous-ledger/morning-YYYY-MM-DD.log

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ADAPTER_DIR="$SCRIPT_DIR/adapters"
LOG_DIR="$HOME/.local/log/generous-ledger"
LOG_FILE="$LOG_DIR/morning-$(date +%Y-%m-%d).log"
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

log "=== Morning Routine — $(date) ==="

# 1. Weather (always runs — free API, no credentials)
run_adapter "weather" ""

# 2. Calendar (requires Google OAuth token)
run_adapter "calendar" "$CRED_DIR/google-calendar-token.json"

# 3. Gmail (requires Google OAuth token)
run_adapter "gmail" "$CRED_DIR/google-gmail-token.json"

# 4. iMessage (requires readable chat.db)
CHAT_DB="$HOME/Library/Messages/chat.db"
if [ -r "$CHAT_DB" ]; then
    run_adapter "imessage" ""
else
    log "SKIP imessage — $CHAT_DB not readable"
fi

# 5. Finance (requires YNAB token — only run on Mondays)
DAY_OF_WEEK=$(date +%u)  # 1=Monday
if [ "$DAY_OF_WEEK" = "1" ]; then
    run_adapter "finance" "$CRED_DIR/ynab.json"
else
    log "SKIP finance — not Monday"
fi

# 6. Daily briefing
log "RUN  briefing"
if bash "$SCRIPT_DIR/daily-briefing.sh" >> "$LOG_FILE" 2>&1; then
    log "OK   briefing"
else
    log "FAIL briefing (exit $?)"
fi

# 7. Cleanup ephemeral data files
log "RUN  cleanup"
rm -f "$VAULT_PATH/data/email/"*.md
rm -f "$VAULT_PATH/data/messages/"*.md
log "OK   cleanup"

log "=== Morning Routine Complete ==="
