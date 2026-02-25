#!/bin/bash
# ambient-watcher.sh — Background daemon that watches diary/ for file changes
#
# USAGE:
#   ./scripts/ambient-watcher.sh           # Start foreground daemon
#   ./scripts/ambient-watcher.sh --stop    # Stop running daemon via PID file
#
# Watches the diary/ directory in the Obsidian vault for .md file changes.
# When a change is detected (with 60s debounce), invokes ambient-briefing.sh
# to let the steward assess whether a profile update is warranted.
#
# Rate-limited to at most one Claude invocation per 30 minutes.
#
# PREREQUISITES:
#   - fswatch must be installed: brew install fswatch
#   - Claude Code CLI (`claude`) must be installed and authenticated
#
# LOGS:
#   ~/.local/log/generous-ledger/ambient-YYYY-MM-DD.log

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT_PATH="$HOME/Documents/Achaean"
LOG_DIR="$HOME/.local/log/generous-ledger"
STATE_DIR="$HOME/.config/generous-ledger/state"
PID_FILE="$STATE_DIR/ambient-watcher.pid"
LAST_RUN_FILE="$STATE_DIR/ambient-last-run"
RATE_LIMIT_SECONDS=1800  # 30 minutes

log() {
    local log_file="$LOG_DIR/ambient-$(date +%Y-%m-%d).log"
    echo "$(date '+%H:%M:%S') $1" | tee -a "$log_file"
}

# --- Stop mode ---
if [ "${1:-}" = "--stop" ]; then
    if [ ! -f "$PID_FILE" ]; then
        echo "No PID file found at $PID_FILE — daemon may not be running."
        exit 1
    fi
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        rm -f "$PID_FILE"
        log "STOP ambient-watcher (PID $PID)"
        echo "Stopped ambient-watcher (PID $PID)."
    else
        rm -f "$PID_FILE"
        echo "PID $PID not running. Cleaned up stale PID file."
    fi
    exit 0
fi

# --- Prerequisite check ---
if ! command -v fswatch &>/dev/null; then
    echo "ERROR: fswatch is not installed."
    echo "Install it with: brew install fswatch"
    exit 1
fi

# --- Verify watch target ---
WATCH_PATH="$VAULT_PATH/diary"
if [ ! -d "$WATCH_PATH" ]; then
    echo "ERROR: Watch directory not found at $WATCH_PATH"
    exit 1
fi

# --- Ensure directories ---
mkdir -p "$LOG_DIR"
mkdir -p "$STATE_DIR"

# --- Check for existing daemon ---
if [ -f "$PID_FILE" ]; then
    EXISTING_PID=$(cat "$PID_FILE")
    if kill -0 "$EXISTING_PID" 2>/dev/null; then
        echo "ERROR: ambient-watcher already running (PID $EXISTING_PID)."
        echo "Stop it first: $0 --stop"
        exit 1
    else
        # Stale PID file — clean up
        rm -f "$PID_FILE"
    fi
fi

# --- Write PID and register cleanup ---
echo $$ > "$PID_FILE"

cleanup() {
    rm -f "$PID_FILE"
    log "EXIT ambient-watcher (PID $$)"
}
trap cleanup EXIT

log "START ambient-watcher (PID $$) — watching $WATCH_PATH"

# --- Main watch loop ---
# fswatch options:
#   -l 60       — 60s latency (debounce)
#   --include   — only .md files
#   --exclude   — everything else (applied after include)
#   -e .tmp     — exclude .tmp files
#   -e .DS_Store — exclude .DS_Store
fswatch -l 60 \
    --include '\.md$' \
    -e '\.tmp' \
    -e '\.DS_Store' \
    --exclude '.*' \
    "$WATCH_PATH" | while read -r CHANGED_FILE; do

    log "CHANGE detected: $CHANGED_FILE"

    # --- Rate limit check ---
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

    # --- Invoke ambient briefing ---
    log "RUN  ambient-briefing"
    date +%s > "$LAST_RUN_FILE"

    if bash "$SCRIPT_DIR/ambient-briefing.sh" "$CHANGED_FILE" >> "$LOG_DIR/ambient-$(date +%Y-%m-%d).log" 2>&1; then
        log "OK   ambient-briefing"
    else
        log "FAIL ambient-briefing (exit $?)"
    fi
done
