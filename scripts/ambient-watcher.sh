#!/bin/bash
# ambient-watcher.sh — Watch diary/ for changes and run ambient updates

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$HOME/.local/log/generous-ledger"
STATE_DIR="$HOME/.config/generous-ledger/state"
PID_FILE="$STATE_DIR/ambient-watcher.pid"
LAST_RUN_FILE="$STATE_DIR/ambient-last-run"
RATE_LIMIT_SECONDS=1800

source "$SCRIPT_DIR/lib/provider-runner.sh"

STOP_MODE=false
ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--stop" ]; then
        STOP_MODE=true
    else
        ARGS+=("$arg")
    fi
done

if $STOP_MODE; then
    if [ ! -f "$PID_FILE" ]; then
        echo "No PID file found at $PID_FILE — daemon may not be running."
        exit 1
    fi

    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        rm -f "$PID_FILE"
        echo "Stopped ambient-watcher (PID $PID)."
    else
        rm -f "$PID_FILE"
        echo "PID $PID not running. Cleaned up stale PID file."
    fi
    exit 0
fi

gl_parse_common_args "${ARGS[@]}" || exit 1
if [ ${#REMAINING_ARGS[@]} -ne 0 ]; then
    echo "USAGE: ./scripts/ambient-watcher.sh [--provider codex|claude] [--vault PATH]" >&2
    echo "       ./scripts/ambient-watcher.sh --stop" >&2
    exit 1
fi

PROVIDER="$(gl_resolve_provider "$COMMON_PROVIDER")" || exit 1
VAULT_PATH="$(gl_resolve_vault_path "$COMMON_VAULT")"
WATCH_PATH="$VAULT_PATH/diary"

log() {
    local log_file="$LOG_DIR/ambient-$(date +%Y-%m-%d).log"
    echo "$(date '+%H:%M:%S') $1" | tee -a "$log_file"
}

if ! command -v fswatch >/dev/null 2>&1; then
    echo "ERROR: fswatch is not installed. Install it with: brew install fswatch" >&2
    exit 1
fi

if [ ! -d "$WATCH_PATH" ]; then
    echo "ERROR: Watch directory not found at $WATCH_PATH" >&2
    exit 1
fi

mkdir -p "$LOG_DIR"
mkdir -p "$STATE_DIR"

if [ -f "$PID_FILE" ]; then
    EXISTING_PID=$(cat "$PID_FILE")
    if kill -0 "$EXISTING_PID" 2>/dev/null; then
        echo "ERROR: ambient-watcher already running (PID $EXISTING_PID)." >&2
        echo "Stop it first: $0 --stop" >&2
        exit 1
    fi
    rm -f "$PID_FILE"
fi

echo $$ > "$PID_FILE"

cleanup() {
    rm -f "$PID_FILE"
    log "EXIT ambient-watcher (PID $$)"
}
trap cleanup EXIT

log "START ambient-watcher ($(gl_provider_display_name "$PROVIDER"), PID $$) — watching $WATCH_PATH"

fswatch -l 60 \
    --include '\.md$' \
    -e '\.tmp' \
    -e '\.DS_Store' \
    --exclude '.*' \
    "$WATCH_PATH" | while read -r CHANGED_FILE; do

    log "CHANGE detected: $CHANGED_FILE"

    if [ -f "$LAST_RUN_FILE" ]; then
        LAST_RUN=$(cat "$LAST_RUN_FILE")
        NOW=$(date +%s)
        ELAPSED=$(( NOW - LAST_RUN ))
        if [ "$ELAPSED" -lt "$RATE_LIMIT_SECONDS" ]; then
            REMAINING=$(( RATE_LIMIT_SECONDS - ELAPSED ))
            log "SKIP rate-limited ($REMAINING s remaining)"
            continue
        fi
    fi

    log "RUN  ambient-briefing"
    date +%s > "$LAST_RUN_FILE"

    if bash "$SCRIPT_DIR/ambient-briefing.sh" --provider "$PROVIDER" --vault "$VAULT_PATH" "$CHANGED_FILE" >> "$LOG_DIR/ambient-$(date +%Y-%m-%d).log" 2>&1; then
        log "OK   ambient-briefing"
    else
        log "FAIL ambient-briefing (exit $?)"
    fi
done
