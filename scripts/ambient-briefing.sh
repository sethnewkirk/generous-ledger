#!/bin/bash
# ambient-briefing.sh — Generate an ambient update via Claude Code
#
# USAGE:
#   ./scripts/ambient-briefing.sh <changed-file-path>
#
# This script invokes Claude Code from the Obsidian vault root, where
# CLAUDE.md is auto-loaded. Claude follows the Ambient Update Protocol
# defined there: reads the changed file, assesses whether a profile
# update is warranted, and acts accordingly.
#
# Called by ambient-watcher.sh when a diary/ file is modified.
#
# PREREQUISITES:
#   - Claude Code CLI (`claude`) must be installed and authenticated
#   - CLAUDE.md must be deployed to the vault
#
# LOGS:
#   ~/.local/log/generous-ledger/ambient-briefing-YYYY-MM-DD.log

set -e

CHANGED_FILE="${1:?USAGE: ambient-briefing.sh <changed-file-path>}"
VAULT_PATH="$HOME/Documents/Achaean"
LOG_DIR="$HOME/.local/log/generous-ledger"
LOG_FILE="$LOG_DIR/ambient-briefing-$(date +%Y-%m-%d).log"

# Create log directory if needed
mkdir -p "$LOG_DIR"

echo "=== Ambient Briefing — $(date) ===" | tee -a "$LOG_FILE"

# Verify vault exists
if [ ! -d "$VAULT_PATH" ]; then
    echo "ERROR: Vault not found at $VAULT_PATH" | tee -a "$LOG_FILE"
    exit 1
fi

# Verify CLAUDE.md is deployed
if [ ! -f "$VAULT_PATH/CLAUDE.md" ]; then
    echo "ERROR: CLAUDE.md not found at $VAULT_PATH/CLAUDE.md" | tee -a "$LOG_FILE"
    echo "Deploy it first: cp CLAUDE.md ~/Documents/Achaean/CLAUDE.md" | tee -a "$LOG_FILE"
    exit 1
fi

# Load model config (optional — uses CLI default if absent)
source "$(dirname "$0")/lib/model-config.sh"
MODEL=$(get_model "ambient")

# Run Claude from the vault root so CLAUDE.md is auto-loaded
cd "$VAULT_PATH"

# Unset CLAUDECODE so claude -p doesn't refuse to run when invoked
# from within an existing Claude Code session (e.g. manual testing).
unset CLAUDECODE

claude -p "A file was modified: $CHANGED_FILE. Follow the Ambient Update Protocol in CLAUDE.md." \
    --max-turns 8 \
    ${MODEL:+--model "$MODEL"} \
    --permission-mode bypassPermissions \
    >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "SUCCESS: Ambient briefing complete. Log: $LOG_FILE" | tee -a "$LOG_FILE"
else
    echo "FAILURE: Claude exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
fi

exit $EXIT_CODE
