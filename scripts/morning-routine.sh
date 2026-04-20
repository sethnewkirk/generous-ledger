#!/bin/bash
# morning-routine.sh — Run adapters, then generate the daily briefing

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ADAPTER_DIR="$SCRIPT_DIR/adapters"
LOG_DIR="$HOME/.local/log/generous-ledger"
LOG_FILE="$LOG_DIR/morning-$(date +%Y-%m-%d).log"
CRED_DIR="$HOME/.config/generous-ledger/credentials"

source "$SCRIPT_DIR/lib/provider-runner.sh"

gl_parse_common_args "$@" || exit 1
if [ ${#REMAINING_ARGS[@]} -ne 0 ]; then
    echo "USAGE: ./scripts/morning-routine.sh [--provider codex|claude] [--vault PATH]" >&2
    exit 1
fi

PROVIDER="$(gl_resolve_provider "$COMMON_PROVIDER")" || exit 1
VAULT_PATH="$(gl_resolve_vault_path "$COMMON_VAULT")"

mkdir -p "$LOG_DIR"

log() {
    echo "$(date '+%H:%M:%S') $1" | tee -a "$LOG_FILE"
}

run_adapter() {
    local name="$1"
    local script="$ADAPTER_DIR/$name.py"
    local cred_file="$2"

    if [ ! -f "$script" ]; then
        log "SKIP $name — script not found"
        return
    fi

    if [ -n "$cred_file" ] && [ ! -f "$cred_file" ]; then
        log "SKIP $name — credentials not configured"
        return
    fi

    log "RUN  $name"
    if python3 "$script" --vault "$VAULT_PATH" >> "$LOG_FILE" 2>&1; then
        log "OK   $name"
    else
        log "FAIL $name (exit $?)"
    fi
}

log "=== Morning Routine ($(gl_provider_display_name "$PROVIDER")) — $(date) ==="

run_adapter "contacts" ""
run_adapter "weather" ""
run_adapter "calendar" "$CRED_DIR/google-calendar-token.json"
run_adapter "gmail" "$CRED_DIR/google-gmail-token.json"
run_adapter "tasks" ""
run_adapter "voice_notes" ""
run_adapter "call_log" ""

CHAT_DB="$HOME/Library/Messages/chat.db"
if [ -r "$CHAT_DB" ]; then
    run_adapter "imessage" ""
else
    log "SKIP imessage — $CHAT_DB not readable"
fi

DAY_OF_WEEK=$(date +%u)
if [ "$DAY_OF_WEEK" = "1" ]; then
    run_adapter "finance" "$CRED_DIR/ynab.json"
else
    log "SKIP finance — not Monday"
fi

log "RUN  briefing"
if bash "$SCRIPT_DIR/daily-briefing.sh" --provider "$PROVIDER" --vault "$VAULT_PATH" >> "$LOG_FILE" 2>&1; then
    log "OK   briefing"
    log "RUN  cleanup"
    rm -f "$VAULT_PATH/data/email/"*.md
    rm -f "$VAULT_PATH/data/messages/"*.md
    log "OK   cleanup"
    log "=== Morning Routine Complete ==="
    exit 0
else
    EXIT_CODE=$?
    log "FAIL briefing (exit $EXIT_CODE)"
    log "SKIP cleanup — preserved email and message files for retry/debugging"
    exit $EXIT_CODE
fi
