#!/bin/bash
# ambient-briefing.sh — Run the ambient update protocol through the configured provider

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib/provider-runner.sh"

gl_parse_common_args "$@" || exit 1
if [ ${#REMAINING_ARGS[@]} -ne 1 ]; then
    echo "USAGE: ./scripts/ambient-briefing.sh [--provider codex|claude] [--vault PATH] <changed-file-path>" >&2
    exit 1
fi

CHANGED_FILE="${REMAINING_ARGS[0]}"
PROVIDER="$(gl_resolve_provider "$COMMON_PROVIDER")" || exit 1
VAULT_PATH="$(gl_resolve_vault_path "$COMMON_VAULT")"
LOG_DIR="$HOME/.local/log/generous-ledger"
LOG_FILE="$LOG_DIR/ambient-briefing-$(date +%Y-%m-%d).log"
MODEL="$(get_model "ambient")"
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

echo "=== Ambient Update ($(gl_provider_display_name "$PROVIDER")) — $(date) ===" | tee -a "$LOG_FILE"

echo "RUN  compile-memory" | tee -a "$LOG_FILE"
if bash "$SCRIPT_DIR/compile-memory.sh" --vault "$VAULT_PATH" >> "$LOG_FILE" 2>&1; then
    echo "OK   compile-memory" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "FAILURE: memory compilation exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi

POLICY_FILE="$(mktemp "$LOG_DIR/ambient-policy.XXXXXX")"
CONTEXT_FILE="$(mktemp "$LOG_DIR/ambient-context.XXXXXX")"
if gl_build_policy_packet "$VAULT_PATH" routine ambient "$PROVIDER" routine_output file_writing > "$POLICY_FILE"; then
    echo "OK   build-policy" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "FAILURE: ambient policy build exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi

if python3 "$SCRIPT_DIR/build_briefing_context.py" \
    --vault "$VAULT_PATH" \
    --workflow ambient \
    --note "$CHANGED_FILE" > "$CONTEXT_FILE"; then
    echo "OK   build-context" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "FAILURE: ambient context build exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
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
        "<SOURCE_CONTEXT>" \
        "A file was modified: $CHANGED_FILE" \
        "</SOURCE_CONTEXT>" \
        "" \
        "<TASK>" \
        "Follow the Ambient Update workflow rules in $RUNTIME_DOC." \
        "Start from the changed file and keep the response or write narrow and justified." \
        "</TASK>")" \
    8 \
    "$MODEL" >> "$LOG_FILE" 2>&1; then
    echo "SUCCESS: Ambient update complete. Log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit 0
else
    EXIT_CODE=$?
    echo "FAILURE: $(gl_provider_display_name "$PROVIDER") exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi
