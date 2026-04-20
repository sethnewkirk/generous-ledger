#!/bin/bash
# monthly-review-briefing.sh — Generate a monthly review through the configured provider

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib/provider-runner.sh"

gl_parse_common_args "$@" || exit 1
if [ ${#REMAINING_ARGS[@]} -ne 0 ]; then
    echo "USAGE: ./scripts/monthly-review-briefing.sh [--provider codex|claude] [--vault PATH]" >&2
    exit 1
fi

PROVIDER="$(gl_resolve_provider "$COMMON_PROVIDER")" || exit 1
VAULT_PATH="$(gl_resolve_vault_path "$COMMON_VAULT")"
LOG_DIR="$HOME/.local/log/generous-ledger"
LOG_FILE="$LOG_DIR/monthly-review-$(date +%Y-%m-%d).log"
MODEL="$(get_model "monthly_review")"
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

echo "=== Monthly Review ($(gl_provider_display_name "$PROVIDER")) — $(date) ===" | tee -a "$LOG_FILE"

echo "RUN  compile-memory" | tee -a "$LOG_FILE"
if bash "$SCRIPT_DIR/compile-memory.sh" --vault "$VAULT_PATH" >> "$LOG_FILE" 2>&1; then
    echo "OK   compile-memory" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "FAILURE: memory compilation exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi

POLICY_FILE="$(mktemp "$LOG_DIR/monthly-policy.XXXXXX")"
CONTEXT_FILE="$(mktemp "$LOG_DIR/monthly-context.XXXXXX")"
if gl_build_policy_packet "$VAULT_PATH" routine monthly "$PROVIDER" routine_output planning > "$POLICY_FILE"; then
    echo "OK   build-policy" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "FAILURE: monthly policy build exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi

if python3 "$SCRIPT_DIR/build_briefing_context.py" \
    --vault "$VAULT_PATH" \
    --workflow monthly > "$CONTEXT_FILE"; then
    echo "OK   build-context" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "FAILURE: monthly context build exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
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
        "Generate this month's review." \
        "Follow the Monthly Review workflow rules in $RUNTIME_DOC." \
        "</TASK>")" \
    20 \
    "$MODEL" >> "$LOG_FILE" 2>&1; then
    echo "SUCCESS: Monthly review generated. Log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit 0
else
    EXIT_CODE=$?
    echo "FAILURE: $(gl_provider_display_name "$PROVIDER") exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi
