#!/bin/bash
# weekly-review-briefing.sh — Generate a weekly review through the configured provider

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib/provider-runner.sh"

gl_parse_common_args "$@" || exit 1
if [ ${#REMAINING_ARGS[@]} -ne 0 ]; then
    echo "USAGE: ./scripts/weekly-review-briefing.sh [--provider codex|claude] [--vault PATH]" >&2
    exit 1
fi

PROVIDER="$(gl_resolve_provider "$COMMON_PROVIDER")" || exit 1
VAULT_PATH="$(gl_resolve_vault_path "$COMMON_VAULT")"
LOG_DIR="$HOME/.local/log/generous-ledger"
LOG_FILE="$LOG_DIR/weekly-review-$(date +%Y-%m-%d).log"
MODEL="$(get_model "weekly_review")"
RUNTIME_DOC="$(gl_runtime_doc_for_provider "$PROVIDER")"
POLICY_FILE=""
CONTEXT_FILE=""

cleanup() {
    if [ -n "$POLICY_FILE" ] && [ -f "$POLICY_FILE" ]; then
        rm -f "$POLICY_FILE"
    fi
    if [ -n "$CONTEXT_FILE" ] && [ -f "$CONTEXT_FILE" ]; then
        rm -f "$CONTEXT_FILE"
    fi
}
trap cleanup EXIT

mkdir -p "$LOG_DIR"

echo "=== Weekly Review ($(gl_provider_display_name "$PROVIDER")) — $(date) ===" | tee -a "$LOG_FILE"

echo "RUN  compile-memory" | tee -a "$LOG_FILE"
if bash "$SCRIPT_DIR/compile-memory.sh" --vault "$VAULT_PATH" >> "$LOG_FILE" 2>&1; then
    echo "OK   compile-memory" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "FAILURE: memory compilation exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi

POLICY_FILE="$(mktemp "$LOG_DIR/weekly-policy.XXXXXX")"
CONTEXT_FILE="$(mktemp "$LOG_DIR/weekly-context.XXXXXX")"
if gl_build_policy_packet "$VAULT_PATH" routine weekly "$PROVIDER" routine_output planning > "$POLICY_FILE"; then
    echo "OK   build-policy" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "FAILURE: weekly policy build exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi

if python3 "$SCRIPT_DIR/build_briefing_context.py" \
    --vault "$VAULT_PATH" \
    --workflow weekly > "$CONTEXT_FILE"; then
    echo "OK   build-context" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "FAILURE: weekly context build exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi

if gl_run_provider_prompt \
    "$PROVIDER" \
    "$VAULT_PATH" \
    "$(printf '%s\n' \
        "$(cat "$POLICY_FILE")" \
        "" \
        "<RETRIEVED_CONTEXT>" \
        "$(cat "$CONTEXT_FILE")" \
        "</RETRIEVED_CONTEXT>" \
        "" \
        "<TASK>" \
        "Generate this week's review." \
        "Follow the Weekly Review workflow rules in $RUNTIME_DOC." \
        "</TASK>")" \
    15 \
    "$MODEL" >> "$LOG_FILE" 2>&1; then
    echo "SUCCESS: Weekly review generated. Log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit 0
else
    EXIT_CODE=$?
    echo "FAILURE: $(gl_provider_display_name "$PROVIDER") exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi
