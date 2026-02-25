#!/bin/bash
# install-schedule.sh — Install (or uninstall) the generous-ledger LaunchAgents
#
# USAGE:
#   ./scripts/install-schedule.sh              # Install and load all agents
#   ./scripts/install-schedule.sh --uninstall  # Unload and remove all agents
#
# This creates five macOS LaunchAgents:
#   - morning-routine.sh  at 6:00 AM daily (adapters + daily briefing)
#   - evening-routine.sh  at 9:00 PM daily (evening review + diary)
#   - weekly-routine.sh   at 9:30 PM Sundays (weekly review)
#   - monthly-routine.sh  at 10:00 PM 1st of month (monthly review)
#   - ambient-watcher.sh  always running (file change watcher)
#
# PREREQUISITES:
#   - All routine scripts must exist alongside this script
#   - Deploy to vault first: ./scripts/deploy.sh
#   - fswatch must be installed for ambient watcher: brew install fswatch

set -e

MORNING_LABEL="com.generous-ledger.morning-routine"
MORNING_PLIST="$HOME/Library/LaunchAgents/$MORNING_LABEL.plist"
EVENING_LABEL="com.generous-ledger.evening-routine"
EVENING_PLIST="$HOME/Library/LaunchAgents/$EVENING_LABEL.plist"
WEEKLY_LABEL="com.generous-ledger.weekly-routine"
WEEKLY_PLIST="$HOME/Library/LaunchAgents/$WEEKLY_LABEL.plist"
MONTHLY_LABEL="com.generous-ledger.monthly-routine"
MONTHLY_PLIST="$HOME/Library/LaunchAgents/$MONTHLY_LABEL.plist"
AMBIENT_LABEL="com.generous-ledger.ambient-watcher"
AMBIENT_PLIST="$HOME/Library/LaunchAgents/$AMBIENT_LABEL.plist"
VAULT_PATH="$HOME/Documents/Achaean"
LOG_DIR="$HOME/.local/log/generous-ledger"

# Resolve absolute paths to routine scripts (siblings of this script)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MORNING_SCRIPT="$SCRIPT_DIR/morning-routine.sh"
EVENING_SCRIPT="$SCRIPT_DIR/evening-routine.sh"
WEEKLY_SCRIPT="$SCRIPT_DIR/weekly-routine.sh"
MONTHLY_SCRIPT="$SCRIPT_DIR/monthly-routine.sh"
AMBIENT_SCRIPT="$SCRIPT_DIR/ambient-watcher.sh"

# --- Helper: unload and remove a single agent ---
uninstall_agent() {
    local label="$1"
    local plist="$2"
    local name="$3"

    if launchctl list "$label" &>/dev/null; then
        launchctl unload "$plist" 2>/dev/null || true
        echo "  Unloaded $name LaunchAgent."
    else
        echo "  $name LaunchAgent was not loaded."
    fi

    if [ -f "$plist" ]; then
        rm "$plist"
        echo "  Removed $plist"
    else
        echo "  $name plist not found (already removed)."
    fi
}

# --- Uninstall mode ---
if [ "${1:-}" = "--uninstall" ]; then
    echo "Uninstalling all generous-ledger schedules..."

    # Clean up old daily-briefing label if it exists
    OLD_LABEL="com.generous-ledger.daily-briefing"
    OLD_PLIST="$HOME/Library/LaunchAgents/$OLD_LABEL.plist"
    if launchctl list "$OLD_LABEL" &>/dev/null; then
        launchctl unload "$OLD_PLIST" 2>/dev/null || true
        rm -f "$OLD_PLIST"
        echo "  Removed legacy daily-briefing agent."
    fi

    uninstall_agent "$MORNING_LABEL" "$MORNING_PLIST" "morning"
    uninstall_agent "$EVENING_LABEL" "$EVENING_PLIST" "evening"
    uninstall_agent "$WEEKLY_LABEL" "$WEEKLY_PLIST" "weekly"
    uninstall_agent "$MONTHLY_LABEL" "$MONTHLY_PLIST" "monthly"
    uninstall_agent "$AMBIENT_LABEL" "$AMBIENT_PLIST" "ambient"

    echo "Done. Logs remain at $LOG_DIR if you want to clean them up."
    exit 0
fi

# --- Install mode ---
echo "Installing all generous-ledger schedules..."

# Verify the routine scripts exist
for script_pair in \
    "morning-routine.sh:$MORNING_SCRIPT" \
    "evening-routine.sh:$EVENING_SCRIPT" \
    "weekly-routine.sh:$WEEKLY_SCRIPT" \
    "monthly-routine.sh:$MONTHLY_SCRIPT" \
    "ambient-watcher.sh:$AMBIENT_SCRIPT"; do
    name="${script_pair%%:*}"
    path="${script_pair#*:}"
    if [ ! -f "$path" ]; then
        echo "ERROR: $name not found at $path"
        exit 1
    fi
done

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Unload existing agents if present (idempotent reinstall)
for label_plist in \
    "$MORNING_LABEL:$MORNING_PLIST" \
    "$EVENING_LABEL:$EVENING_PLIST" \
    "$WEEKLY_LABEL:$WEEKLY_PLIST" \
    "$MONTHLY_LABEL:$MONTHLY_PLIST" \
    "$AMBIENT_LABEL:$AMBIENT_PLIST"; do
    label="${label_plist%%:*}"
    plist="${label_plist#*:}"
    if launchctl list "$label" &>/dev/null; then
        launchctl unload "$plist" 2>/dev/null || true
        echo "  Unloaded existing $label."
    fi
done

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

# Write the weekly plist (Sunday at 9:30 PM)
cat > "$WEEKLY_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$WEEKLY_LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$WEEKLY_SCRIPT</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$VAULT_PATH</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>0</integer>
        <key>Hour</key>
        <integer>21</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/launchd-stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$LOG_DIR/launchd-stderr.log</string>
</dict>
</plist>
EOF

echo "  Wrote weekly plist to $WEEKLY_PLIST"

# Write the monthly plist (1st of month at 10:00 PM)
cat > "$MONTHLY_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$MONTHLY_LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$MONTHLY_SCRIPT</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$VAULT_PATH</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Day</key>
        <integer>1</integer>
        <key>Hour</key>
        <integer>22</integer>
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

echo "  Wrote monthly plist to $MONTHLY_PLIST"

# Write the ambient watcher plist (KeepAlive + RunAtLoad)
cat > "$AMBIENT_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$AMBIENT_LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$AMBIENT_SCRIPT</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$VAULT_PATH</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/launchd-stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$LOG_DIR/launchd-stderr.log</string>
</dict>
</plist>
EOF

echo "  Wrote ambient plist to $AMBIENT_PLIST"

# Load all agents
launchctl load "$MORNING_PLIST"
echo "  Loaded morning LaunchAgent. Morning routine will run daily at 6:00 AM."

launchctl load "$EVENING_PLIST"
echo "  Loaded evening LaunchAgent. Evening routine will run daily at 9:00 PM."

launchctl load "$WEEKLY_PLIST"
echo "  Loaded weekly LaunchAgent. Weekly review will run Sundays at 9:30 PM."

launchctl load "$MONTHLY_PLIST"
echo "  Loaded monthly LaunchAgent. Monthly review will run 1st of month at 10:00 PM."

launchctl load "$AMBIENT_PLIST"
echo "  Loaded ambient LaunchAgent. File watcher will run continuously."

echo ""
echo "Done. 5 agents installed. Verify with:"
echo "  launchctl list | grep generous-ledger"
echo ""
echo "REMINDER: Deploy to vault first if you haven't already:"
echo "  ./scripts/deploy.sh"
