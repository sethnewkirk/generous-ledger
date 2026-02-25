#!/bin/bash
# monthly-review-briefing.sh — Generate a monthly review via Claude Code
#
# USAGE:
#   ./scripts/monthly-review-briefing.sh
#
# This script invokes Claude Code from the Obsidian vault root, where
# CLAUDE.md is auto-loaded. Claude follows the Monthly Review Protocol
# defined there: reads the month's weekly reviews, diary entries,
# commitments, patterns, and people files to generate a synthesized
# monthly review with trajectory analysis.
#
# PREREQUISITES:
#   - Claude Code CLI (`claude`) must be installed and authenticated
#   - CLAUDE.md, docs/FRAMEWORK.md, and templates/ must be deployed to the vault:
#       npm run build && cp main.js manifest.json styles.css ~/Documents/Achaean/.obsidian/plugins/generous-ledger/
#       cp CLAUDE.md ~/Documents/Achaean/CLAUDE.md
#       cp docs/FRAMEWORK.md ~/Documents/Achaean/docs/FRAMEWORK.md
#       mkdir -p ~/Documents/Achaean/templates && cp templates/profile-*.md ~/Documents/Achaean/templates/
#   - Obsidian must be running (for CLI commands used by the review)
#
# LOGS:
#   ~/.local/log/generous-ledger/monthly-review-YYYY-MM-DD.log

set -e

VAULT_PATH="$HOME/Documents/Achaean"
LOG_DIR="$HOME/.local/log/generous-ledger"
LOG_FILE="$LOG_DIR/monthly-review-$(date +%Y-%m-%d).log"

# Create log directory if needed
mkdir -p "$LOG_DIR"

echo "=== Monthly Review — $(date) ===" | tee -a "$LOG_FILE"

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
MODEL=$(get_model "monthly_review")

# Run Claude from the vault root so CLAUDE.md is auto-loaded
cd "$VAULT_PATH"

# Unset CLAUDECODE so claude -p doesn't refuse to run when invoked
# from within an existing Claude Code session (e.g. manual testing).
unset CLAUDECODE

claude -p "Generate this month's review per the Monthly Review Protocol in CLAUDE.md." \
    --max-turns 20 \
    ${MODEL:+--model "$MODEL"} \
    --permission-mode bypassPermissions \
    >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "SUCCESS: Monthly review generated. Log: $LOG_FILE" | tee -a "$LOG_FILE"
else
    echo "FAILURE: Claude exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
fi

exit $EXIT_CODE
