#!/bin/bash
# evening-briefing.sh — Generate an evening review through the configured provider

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib/provider-runner.sh"

gl_parse_common_args "$@" || exit 1
if [ ${#REMAINING_ARGS[@]} -ne 0 ]; then
    echo "USAGE: ./scripts/evening-briefing.sh [--provider codex|claude] [--vault PATH]" >&2
    exit 1
fi

PROVIDER="$(gl_resolve_provider "$COMMON_PROVIDER")" || exit 1
VAULT_PATH="$(gl_resolve_vault_path "$COMMON_VAULT")"
LOG_DIR="$HOME/.local/log/generous-ledger"
LOG_FILE="$LOG_DIR/evening-briefing-$(date +%Y-%m-%d).log"
MODEL="$(get_model "evening_review")"
RUNTIME_DOC="$(gl_runtime_doc_for_provider "$PROVIDER")"
TODAY_NOTE_RELATIVE=""
TOMORROW_NOTE_RELATIVE=""
CONTEXT_FILE=""
POLICY_FILE=""

cleanup() {
    if [ -n "$CONTEXT_FILE" ] && [ -f "$CONTEXT_FILE" ]; then
        rm -f "$CONTEXT_FILE"
    fi
    if [ -n "$POLICY_FILE" ] && [ -f "$POLICY_FILE" ]; then
        rm -f "$POLICY_FILE"
    fi
}
trap cleanup EXIT

mkdir -p "$LOG_DIR"

echo "=== Evening Review ($(gl_provider_display_name "$PROVIDER")) — $(date) ===" | tee -a "$LOG_FILE"

echo "RUN  compile-memory" | tee -a "$LOG_FILE"
if bash "$SCRIPT_DIR/compile-memory.sh" --vault "$VAULT_PATH" >> "$LOG_FILE" 2>&1; then
    echo "OK   compile-memory" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "FAILURE: memory compilation exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi

TODAY_NOTE_RELATIVE="$(gl_daily_note_relative_path "$VAULT_PATH" 0 || true)"
TOMORROW_NOTE_RELATIVE="$(gl_daily_note_relative_path "$VAULT_PATH" 1 || true)"

if [ -n "$TODAY_NOTE_RELATIVE" ]; then
    gl_ensure_note_path "$VAULT_PATH" "$TODAY_NOTE_RELATIVE"
fi

if [ -n "$TOMORROW_NOTE_RELATIVE" ]; then
    gl_ensure_note_path "$VAULT_PATH" "$TOMORROW_NOTE_RELATIVE"
fi

CONTEXT_FILE="$(mktemp "$LOG_DIR/evening-briefing-context.XXXXXX")"
POLICY_FILE="$(mktemp "$LOG_DIR/evening-policy.XXXXXX")"

if gl_build_policy_packet "$VAULT_PATH" routine evening "$PROVIDER" routine_output planning > "$POLICY_FILE"; then
    echo "OK   build-policy" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "FAILURE: evening policy build exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi

if python3 "$SCRIPT_DIR/build_briefing_context.py" \
    --vault "$VAULT_PATH" \
    --workflow evening \
    --note "$TODAY_NOTE_RELATIVE" > "$CONTEXT_FILE"; then
    echo "OK   build-context" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "FAILURE: evening context build exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi

POLICY_CONTENT="$(cat "$POLICY_FILE")"
CONTEXT_CONTENT="$(cat "$CONTEXT_FILE")"

if gl_run_provider_prompt \
    "$PROVIDER" \
    "$VAULT_PATH" \
    "$(printf '%s\n' \
        "$POLICY_CONTENT" \
        "" \
        "<RETRIEVED_CONTEXT>" \
        "$CONTEXT_CONTENT" \
        "</RETRIEVED_CONTEXT>" \
        "" \
        "<TASK>" \
        "Generate tonight's evening review." \
        "Follow the Evening Review workflow rules in $RUNTIME_DOC." \
        "Today's daily note path is ${TODAY_NOTE_RELATIVE:-unknown}." \
        "Tomorrow's daily note path is ${TOMORROW_NOTE_RELATIVE:-unknown}." \
        "Use the supplied context first and do not run broad vault searches unless the context is malformed." \
        "</TASK>")" \
    10 \
    "$MODEL" >> "$LOG_FILE" 2>&1; then
    echo "SUCCESS: Evening review generated. Log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit 0
else
    EXIT_CODE=$?
    echo "FAILURE: $(gl_provider_display_name "$PROVIDER") exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi
