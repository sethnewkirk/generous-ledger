#!/bin/bash
# install-schedule.sh — Install or uninstall macOS LaunchAgents for stewardship routines

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib/provider-runner.sh"

UNINSTALL=false
ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--uninstall" ]; then
        UNINSTALL=true
    else
        ARGS+=("$arg")
    fi
done

gl_parse_common_args "${ARGS[@]}" || exit 1
if [ ${#REMAINING_ARGS[@]} -ne 0 ]; then
    echo "USAGE: ./scripts/install-schedule.sh --provider codex|claude [--vault PATH]" >&2
    echo "       ./scripts/install-schedule.sh --uninstall" >&2
    exit 1
fi

MORNING_LABEL="com.generous-ledger.morning-routine"
EVENING_LABEL="com.generous-ledger.evening-routine"
WEEKLY_LABEL="com.generous-ledger.weekly-routine"
MONTHLY_LABEL="com.generous-ledger.monthly-routine"
AMBIENT_LABEL="com.generous-ledger.ambient-watcher"
LOG_DIR="$HOME/.local/log/generous-ledger"

MORNING_PLIST="$HOME/Library/LaunchAgents/$MORNING_LABEL.plist"
EVENING_PLIST="$HOME/Library/LaunchAgents/$EVENING_LABEL.plist"
WEEKLY_PLIST="$HOME/Library/LaunchAgents/$WEEKLY_LABEL.plist"
MONTHLY_PLIST="$HOME/Library/LaunchAgents/$MONTHLY_LABEL.plist"
AMBIENT_PLIST="$HOME/Library/LaunchAgents/$AMBIENT_LABEL.plist"

MORNING_SCRIPT="$SCRIPT_DIR/morning-routine.sh"
EVENING_SCRIPT="$SCRIPT_DIR/evening-routine.sh"
WEEKLY_SCRIPT="$SCRIPT_DIR/weekly-routine.sh"
MONTHLY_SCRIPT="$SCRIPT_DIR/monthly-routine.sh"
AMBIENT_SCRIPT="$SCRIPT_DIR/ambient-watcher.sh"

uninstall_agent() {
    local label="$1"
    local plist="$2"
    local name="$3"

    if launchctl list "$label" >/dev/null 2>&1; then
        launchctl unload "$plist" 2>/dev/null || true
        echo "  Unloaded $name LaunchAgent."
    fi

    if [ -f "$plist" ]; then
        rm "$plist"
        echo "  Removed $plist"
    fi
}

write_plist() {
    local plist="$1"
    local label="$2"
    local script_path="$3"
    local schedule_block="$4"
    local provider="$5"
    local vault_path="$6"

    cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$label</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$script_path</string>
        <string>--provider</string>
        <string>$provider</string>
        <string>--vault</string>
        <string>$vault_path</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
$schedule_block
    <key>StandardOutPath</key>
    <string>$LOG_DIR/launchd-stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$LOG_DIR/launchd-stderr.log</string>
</dict>
</plist>
EOF
}

if $UNINSTALL; then
    echo "Uninstalling all generous-ledger schedules..."
    uninstall_agent "$MORNING_LABEL" "$MORNING_PLIST" "morning"
    uninstall_agent "$EVENING_LABEL" "$EVENING_PLIST" "evening"
    uninstall_agent "$WEEKLY_LABEL" "$WEEKLY_PLIST" "weekly"
    uninstall_agent "$MONTHLY_LABEL" "$MONTHLY_PLIST" "monthly"
    uninstall_agent "$AMBIENT_LABEL" "$AMBIENT_PLIST" "ambient"
    echo "Done. Logs remain at $LOG_DIR."
    exit 0
fi

PROVIDER="$(gl_resolve_provider "$COMMON_PROVIDER")" || exit 1
VAULT_PATH="$(gl_resolve_vault_path "$COMMON_VAULT")"

for script_path in \
    "$MORNING_SCRIPT" \
    "$EVENING_SCRIPT" \
    "$WEEKLY_SCRIPT" \
    "$MONTHLY_SCRIPT" \
    "$AMBIENT_SCRIPT"; do
    if [ ! -f "$script_path" ]; then
        echo "ERROR: Missing routine script at $script_path" >&2
        exit 1
    fi
done

mkdir -p "$LOG_DIR"

for label_plist in \
    "$MORNING_LABEL:$MORNING_PLIST" \
    "$EVENING_LABEL:$EVENING_PLIST" \
    "$WEEKLY_LABEL:$WEEKLY_PLIST" \
    "$MONTHLY_LABEL:$MONTHLY_PLIST" \
    "$AMBIENT_LABEL:$AMBIENT_PLIST"; do
    label="${label_plist%%:*}"
    plist="${label_plist#*:}"
    if launchctl list "$label" >/dev/null 2>&1; then
        launchctl unload "$plist" 2>/dev/null || true
    fi
done

write_plist "$MORNING_PLIST" "$MORNING_LABEL" "$MORNING_SCRIPT" '
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
' "$PROVIDER" "$VAULT_PATH"

write_plist "$EVENING_PLIST" "$EVENING_LABEL" "$EVENING_SCRIPT" '
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>21</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
' "$PROVIDER" "$VAULT_PATH"

write_plist "$WEEKLY_PLIST" "$WEEKLY_LABEL" "$WEEKLY_SCRIPT" '
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>0</integer>
        <key>Hour</key>
        <integer>21</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>
' "$PROVIDER" "$VAULT_PATH"

write_plist "$MONTHLY_PLIST" "$MONTHLY_LABEL" "$MONTHLY_SCRIPT" '
    <key>StartCalendarInterval</key>
    <dict>
        <key>Day</key>
        <integer>1</integer>
        <key>Hour</key>
        <integer>22</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
' "$PROVIDER" "$VAULT_PATH"

write_plist "$AMBIENT_PLIST" "$AMBIENT_LABEL" "$AMBIENT_SCRIPT" '
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
' "$PROVIDER" "$VAULT_PATH"

launchctl load "$MORNING_PLIST"
launchctl load "$EVENING_PLIST"
launchctl load "$WEEKLY_PLIST"
launchctl load "$MONTHLY_PLIST"
launchctl load "$AMBIENT_PLIST"

echo "Installed generous-ledger schedules for $(gl_provider_display_name "$PROVIDER")."
echo "Vault path: $VAULT_PATH"
echo "Verify with: launchctl list | grep generous-ledger"
