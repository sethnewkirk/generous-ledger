#!/bin/bash
# install-schedule.sh — Install (or uninstall) the morning and evening routine LaunchAgents
#
# USAGE:
#   ./scripts/install-schedule.sh              # Install and load both agents
#   ./scripts/install-schedule.sh --uninstall  # Unload and remove both agents
#
# This creates two macOS LaunchAgents:
#   - morning-routine.sh at 6:00 AM (adapters + daily briefing)
#   - evening-routine.sh at 9:00 PM (evening review + diary)
#
# PREREQUISITES:
#   - morning-routine.sh, evening-routine.sh, and daily-briefing.sh must exist alongside this script
#   - Deploy to vault first: ./scripts/deploy.sh

set -e

MORNING_LABEL="com.generous-ledger.morning-routine"
MORNING_PLIST="$HOME/Library/LaunchAgents/$MORNING_LABEL.plist"
EVENING_LABEL="com.generous-ledger.evening-routine"
EVENING_PLIST="$HOME/Library/LaunchAgents/$EVENING_LABEL.plist"
VAULT_PATH="$HOME/Documents/Achaean"
LOG_DIR="$HOME/.local/log/generous-ledger"

# Resolve absolute paths to routine scripts (siblings of this script)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MORNING_SCRIPT="$SCRIPT_DIR/morning-routine.sh"
EVENING_SCRIPT="$SCRIPT_DIR/evening-routine.sh"

# --- Uninstall mode ---
if [ "${1:-}" = "--uninstall" ]; then
    echo "Uninstalling morning and evening routine schedules..."

    # Also clean up old daily-briefing label if it exists
    OLD_LABEL="com.generous-ledger.daily-briefing"
    OLD_PLIST="$HOME/Library/LaunchAgents/$OLD_LABEL.plist"
    if launchctl list "$OLD_LABEL" &>/dev/null; then
        launchctl unload "$OLD_PLIST" 2>/dev/null || true
        rm -f "$OLD_PLIST"
        echo "  Removed legacy daily-briefing agent."
    fi

    # Uninstall morning routine
    if launchctl list "$MORNING_LABEL" &>/dev/null; then
        launchctl unload "$MORNING_PLIST" 2>/dev/null || true
        echo "  Unloaded morning LaunchAgent."
    else
        echo "  Morning LaunchAgent was not loaded."
    fi

    if [ -f "$MORNING_PLIST" ]; then
        rm "$MORNING_PLIST"
        echo "  Removed $MORNING_PLIST"
    else
        echo "  Morning plist not found (already removed)."
    fi

    # Uninstall evening routine
    if launchctl list "$EVENING_LABEL" &>/dev/null; then
        launchctl unload "$EVENING_PLIST" 2>/dev/null || true
        echo "  Unloaded evening LaunchAgent."
    else
        echo "  Evening LaunchAgent was not loaded."
    fi

    if [ -f "$EVENING_PLIST" ]; then
        rm "$EVENING_PLIST"
        echo "  Removed $EVENING_PLIST"
    else
        echo "  Evening plist not found (already removed)."
    fi

    echo "Done. Logs remain at $LOG_DIR if you want to clean them up."
    exit 0
fi

# --- Install mode ---
echo "Installing morning and evening routine schedules..."

# Verify the routine scripts exist
if [ ! -f "$MORNING_SCRIPT" ]; then
    echo "ERROR: morning-routine.sh not found at $MORNING_SCRIPT"
    exit 1
fi
if [ ! -f "$EVENING_SCRIPT" ]; then
    echo "ERROR: evening-routine.sh not found at $EVENING_SCRIPT"
    exit 1
fi

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Unload existing agents if present (idempotent reinstall)
if launchctl list "$MORNING_LABEL" &>/dev/null; then
    launchctl unload "$MORNING_PLIST" 2>/dev/null || true
    echo "  Unloaded existing morning agent."
fi
if launchctl list "$EVENING_LABEL" &>/dev/null; then
    launchctl unload "$EVENING_PLIST" 2>/dev/null || true
    echo "  Unloaded existing evening agent."
fi

# Write the morning plist
cat > "$MORNING_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$MORNING_LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$MORNING_SCRIPT</string>
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

echo "  Wrote morning plist to $MORNING_PLIST"

# Write the evening plist
cat > "$EVENING_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$EVENING_LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$EVENING_SCRIPT</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$VAULT_PATH</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>21</integer>
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

echo "  Wrote evening plist to $EVENING_PLIST"

# Load both agents
launchctl load "$MORNING_PLIST"
echo "  Loaded morning LaunchAgent. Morning routine will run daily at 6:00 AM."

launchctl load "$EVENING_PLIST"
echo "  Loaded evening LaunchAgent. Evening routine will run daily at 9:00 PM."

echo ""
echo "Done. Verify with:"
echo "  launchctl list | grep generous-ledger"
echo ""
echo "REMINDER: Deploy to vault first if you haven't already:"
echo "  ./scripts/deploy.sh"
