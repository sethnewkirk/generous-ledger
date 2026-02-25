#!/bin/bash
# model-config.sh — Shared helper for reading model configuration
#
# USAGE:
#   source "$(dirname "$0")/lib/model-config.sh"
#   MODEL=$(get_model "daily_briefing")
#   claude -p "..." ${MODEL:+--model "$MODEL"} ...
#
# Reads the model ID for a given task type from ~/.config/generous-ledger/config.yaml.
# Returns empty string if config is missing, key is absent, or python3 is unavailable.

get_model() {
    local task_type="$1"
    local config_file="$HOME/.config/generous-ledger/config.yaml"

    # No config file — return empty (use CLI default)
    if [ ! -f "$config_file" ]; then
        return
    fi

    # Parse with python3 (already a dependency for adapters)
    python3 -c "
import yaml, sys
try:
    with open('$config_file') as f:
        cfg = yaml.safe_load(f) or {}
    model = cfg.get('models', {}).get('$task_type', '')
    if model:
        print(model)
except Exception:
    pass
" 2>/dev/null
}
