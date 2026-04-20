#!/bin/bash
# daily-briefing.sh — Generate a daily steward briefing through the configured provider

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib/provider-runner.sh"

gl_parse_common_args "$@" || exit 1
if [ ${#REMAINING_ARGS[@]} -ne 0 ]; then
    echo "USAGE: ./scripts/daily-briefing.sh [--provider codex|claude] [--vault PATH]" >&2
    exit 1
fi

PROVIDER="$(gl_resolve_provider "$COMMON_PROVIDER")" || exit 1
VAULT_PATH="$(gl_resolve_vault_path "$COMMON_VAULT")"
LOG_DIR="$HOME/.local/log/generous-ledger"
LOG_FILE="$LOG_DIR/briefing-$(date +%Y-%m-%d).log"
MODEL="$(get_model "daily_briefing")"
RUNTIME_DOC="$(gl_runtime_doc_for_provider "$PROVIDER")"
TODAY_NOTE_RELATIVE=""
CONTEXT_FILE=""
DRAFT_FILE=""
POLICY_FILE=""

cleanup() {
    if [ -n "$CONTEXT_FILE" ] && [ -f "$CONTEXT_FILE" ]; then
        rm -f "$CONTEXT_FILE"
    fi
    if [ -n "$DRAFT_FILE" ] && [ -f "$DRAFT_FILE" ]; then
        rm -f "$DRAFT_FILE"
    fi
    if [ -n "$POLICY_FILE" ] && [ -f "$POLICY_FILE" ]; then
        rm -f "$POLICY_FILE"
    fi
}
trap cleanup EXIT

mkdir -p "$LOG_DIR"

echo "=== Daily Briefing ($(gl_provider_display_name "$PROVIDER")) — $(date) ===" | tee -a "$LOG_FILE"

echo "RUN  compile-memory" | tee -a "$LOG_FILE"
if bash "$SCRIPT_DIR/compile-memory.sh" --vault "$VAULT_PATH" >> "$LOG_FILE" 2>&1; then
    echo "OK   compile-memory" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "FAILURE: memory compilation exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi

TODAY_NOTE_RELATIVE="$(gl_daily_note_relative_path "$VAULT_PATH" 0 || true)"
if [ -n "$TODAY_NOTE_RELATIVE" ]; then
    gl_ensure_note_path "$VAULT_PATH" "$TODAY_NOTE_RELATIVE"
fi

CONTEXT_FILE="$(mktemp "$LOG_DIR/daily-briefing-context.XXXXXX")"
DRAFT_FILE="$(mktemp "$LOG_DIR/daily-briefing-draft.XXXXXX")"
POLICY_FILE="$(mktemp "$LOG_DIR/daily-policy.XXXXXX")"

if gl_build_policy_packet "$VAULT_PATH" routine daily "$PROVIDER" routine_output planning > "$POLICY_FILE"; then
    echo "OK   build-policy" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "FAILURE: policy packet build exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi

if python3 "$SCRIPT_DIR/build_briefing_context.py" \
    --vault "$VAULT_PATH" \
    --workflow daily \
    --note "$TODAY_NOTE_RELATIVE" > "$CONTEXT_FILE"; then
    echo "OK   build-context" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "FAILURE: briefing context build exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi

POLICY_CONTENT="$(cat "$POLICY_FILE")"
CONTEXT_CONTENT="$(cat "$CONTEXT_FILE")"
PROMPT="$(
    printf '%s\n' \
        "$POLICY_CONTENT" \
        "" \
        "<RETRIEVED_CONTEXT>" \
        "$CONTEXT_CONTENT" \
        "</RETRIEVED_CONTEXT>" \
        "" \
        "<TASK>" \
        "Draft today's daily briefing in concise markdown for the user." \
        "Follow the Daily Briefing workflow rules in $RUNTIME_DOC." \
        "Use only the supplied context below unless it is clearly malformed." \
        "Return only the briefing markdown with no code fences." \
        "Target note path: ${TODAY_NOTE_RELATIVE:-unknown}" \
        "Highlight the most relevant obligations, schedule items, and relationship follow-ups." \
        "Mention missing or stale data only when it materially affects the briefing." \
        "Keep the briefing tight and practical." \
        "Do not mention the implementation process." \
        "</TASK>"
)"

if gl_run_provider_prompt_to_file \
    "$PROVIDER" \
    "$VAULT_PATH" \
    "$PROMPT" \
    6 \
    "$MODEL" \
    "$DRAFT_FILE" >> "$LOG_FILE" 2>&1; then
    if [ ! -s "$DRAFT_FILE" ]; then
        echo "FAILURE: provider returned an empty daily briefing draft. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
        exit 1
    fi
    gl_prepend_file "$VAULT_PATH/$TODAY_NOTE_RELATIVE" "$DRAFT_FILE"
    echo "SUCCESS: Briefing generated and written to $TODAY_NOTE_RELATIVE. Log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit 0
else
    EXIT_CODE=$?
    echo "FAILURE: $(gl_provider_display_name "$PROVIDER") exited with code $EXIT_CODE. Check log: $LOG_FILE" | tee -a "$LOG_FILE"
    exit $EXIT_CODE
fi
