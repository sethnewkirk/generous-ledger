#!/bin/bash
# daily-briefing.sh — Generate a daily steward briefing via Claude Code
#
# USAGE:
#   ./scripts/daily-briefing.sh
#
# This script invokes Claude Code from the Obsidian vault root, where
# CLAUDE.md is auto-loaded. Claude follows the Daily Briefing Protocol
# defined there: reads the user profile, checks dates/commitments/patterns,
# generates a briefing, and prepends it to the daily note.
#
# PREREQUISITES:
#   - Claude Code CLI (`claude`) must be installed and authenticated
#   - CLAUDE.md, docs/FRAMEWORK.md, and templates/ must be deployed to the vault:
#       npm run build && cp main.js manifest.json styles.css ~/Documents/Achaean/.obsidian/plugins/generous-ledger/
#       cp CLAUDE.md ~/Documents/Achaean/CLAUDE.md
#       cp docs/FRAMEWORK.md ~/Documents/Achaean/docs/FRAMEWORK.md
#       mkdir -p ~/Documents/Achaean/templates && cp templates/profile-*.md ~/Documents/Achaean/templates/
#   - Obsidian must be running (for CLI commands used by the briefing)
#
# LOGS:
#   ~/.local/log/generous-ledger/briefing-YYYY-MM-DD.log

set -e

VAULT_PATH="$HOME/Documents/Achaean"
LOG_DIR="$HOME/.local/log/generous-ledger"
LOG_FILE="$LOG_DIR/briefing-$(date +%Y-%m-%d).log"

# Create log directory if needed
mkdir -p "$LOG_DIR"

echo "=== Daily Briefing — $(date) ===" | tee -a "$LOG_FILE"

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

# Run Claude from the vault root so CLAUDE.md is auto-loaded
cd "$VAULT_PATH"

claude -p "Generate today's daily briefing per the Daily Briefing Protocol in CLAUDE.md." \
    --max-turns 10 \
    --permission-mode bypassPermissions \
    >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "SUCCESS: Briefing generated. Log: $LOG_FILE" | tee -a "$LOG_FILE"
else
    echo "FAILURE: Claude exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
fi

exit $EXIT_CODE
