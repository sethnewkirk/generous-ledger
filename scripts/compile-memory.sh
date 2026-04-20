#!/bin/bash
# compile-memory.sh — Compile vault signals into memory/events, memory/claims, and profile projections

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VAULT_PATH="${GL_VAULT_PATH:-$HOME/Documents/Achaean}"
SINCE_DAYS=90

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
        --since-days)
            if [ $# -lt 2 ]; then
                echo "ERROR: --since-days requires a number." >&2
                exit 1
            fi
            SINCE_DAYS="$2"
            shift 2
            ;;
        *)
            echo "USAGE: ./scripts/compile-memory.sh [--vault PATH] [--since-days N]" >&2
            exit 1
            ;;
    esac
done

PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 "$SCRIPT_DIR/compile_memory.py" --vault "$VAULT_PATH" --since-days "$SINCE_DAYS"
