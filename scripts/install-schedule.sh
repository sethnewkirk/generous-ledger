#!/bin/bash
# install-schedule.sh — Install (or uninstall) the daily briefing LaunchAgent
#
# USAGE:
#   ./scripts/install-schedule.sh              # Install and load the agent
#   ./scripts/install-schedule.sh --uninstall  # Unload and remove the agent
#
# This creates a macOS LaunchAgent that runs daily-briefing.sh at 6:00 AM.
#
# PREREQUISITES:
#   - daily-briefing.sh must exist alongside this script
#   - CLAUDE.md, docs/FRAMEWORK.md, and templates/ must be deployed to the vault:
#       npm run build && cp main.js manifest.json styles.css ~/Documents/Achaean/.obsidian/plugins/generous-ledger/
#       cp CLAUDE.md ~/Documents/Achaean/CLAUDE.md
#       cp docs/FRAMEWORK.md ~/Documents/Achaean/docs/FRAMEWORK.md
#       mkdir -p ~/Documents/Achaean/templates && cp templates/profile-*.md ~/Documents/Achaean/templates/

set -e

LABEL="com.generous-ledger.daily-briefing"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"
VAULT_PATH="$HOME/Documents/Achaean"
LOG_DIR="$HOME/.local/log/generous-ledger"

# Resolve the absolute path to daily-briefing.sh (sibling of this script)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BRIEFING_SCRIPT="$SCRIPT_DIR/daily-briefing.sh"

# --- Uninstall mode ---
if [ "${1:-}" = "--uninstall" ]; then
    echo "Uninstalling daily briefing schedule..."

    if launchctl list "$LABEL" &>/dev/null; then
        launchctl unload "$PLIST_PATH" 2>/dev/null || true
        echo "  Unloaded LaunchAgent."
    else
        echo "  LaunchAgent was not loaded."
    fi

    if [ -f "$PLIST_PATH" ]; then
        rm "$PLIST_PATH"
        echo "  Removed $PLIST_PATH"
    else
        echo "  Plist not found (already removed)."
    fi

    echo "Done. Logs remain at $LOG_DIR if you want to clean them up."
    exit 0
fi

# --- Install mode ---
echo "Installing daily briefing schedule..."

# Verify the briefing script exists
if [ ! -f "$BRIEFING_SCRIPT" ]; then
    echo "ERROR: daily-briefing.sh not found at $BRIEFING_SCRIPT"
    exit 1
fi

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Unload existing agent if present (idempotent reinstall)
if launchctl list "$LABEL" &>/dev/null; then
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    echo "  Unloaded existing agent."
fi

# Write the plist
cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$BRIEFING_SCRIPT</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$VAULT_PATH</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/launchd-stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$LOG_DIR/launchd-stderr.log</string>
</dict>
</plist>
EOF

echo "  Wrote plist to $PLIST_PATH"

# Load the agent
launchctl load "$PLIST_PATH"
echo "  Loaded LaunchAgent. Briefing will run daily at 6:00 AM."

echo ""
echo "Done. Verify with:"
echo "  launchctl list | grep generous-ledger"
echo ""
echo "REMINDER: Ensure CLAUDE.md and supporting files are deployed to the vault:"
echo "  npm run build && cp main.js manifest.json styles.css ~/Documents/Achaean/.obsidian/plugins/generous-ledger/"
echo "  cp CLAUDE.md ~/Documents/Achaean/CLAUDE.md"
echo "  cp docs/FRAMEWORK.md ~/Documents/Achaean/docs/FRAMEWORK.md"
echo "  mkdir -p ~/Documents/Achaean/templates && cp templates/profile-*.md ~/Documents/Achaean/templates/"
