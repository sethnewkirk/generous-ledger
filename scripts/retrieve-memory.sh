#!/bin/bash
# retrieve-memory.sh — Query the derived steward memory context for a workflow

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VAULT_PATH="${GL_VAULT_PATH:-$HOME/Documents/Achaean}"
WORKFLOW=""
SINCE_DAYS=30
SUBJECT_ARGS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --vault)
            if [ $# -lt 2 ]; then
                echo "ERROR: --vault requires a path." >&2
                exit 1
            fi
            VAULT_PATH="$2"
            shift 2
            ;;
        --workflow)
            if [ $# -lt 2 ]; then
                echo "ERROR: --workflow requires a value." >&2
                exit 1
            fi
            WORKFLOW="$2"
            shift 2
            ;;
        --subject)
            if [ $# -lt 2 ]; then
                echo "ERROR: --subject requires a title." >&2
                exit 1
            fi
            SUBJECT_ARGS+=("--subject" "$2")
            shift 2
            ;;
        --since-days)
            if [ $# -lt 2 ]; then
                echo "ERROR: --since-days requires a number." >&2
                exit 1
            fi
            SINCE_DAYS="$2"
            shift 2
            ;;
        *)
            echo "USAGE: ./scripts/retrieve-memory.sh --workflow NAME [--subject TITLE] [--vault PATH] [--since-days N]" >&2
            exit 1
            ;;
    esac
done

if [ -z "$WORKFLOW" ]; then
    echo "ERROR: --workflow is required." >&2
    exit 1
fi

PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 "$SCRIPT_DIR/retrieve_memory.py" --vault "$VAULT_PATH" --workflow "$WORKFLOW" --since-days "$SINCE_DAYS" "${SUBJECT_ARGS[@]}"
