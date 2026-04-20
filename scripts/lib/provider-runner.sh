#!/bin/bash

gl_prepend_path() {
    local dir="$1"
    case ":$PATH:" in
        *":$dir:"*) ;;
        *) PATH="$dir:$PATH" ;;
    esac
}

for candidate in \
    "/opt/homebrew/bin" \
    "/usr/local/bin" \
    "/Applications/Codex.app/Contents/Resources"; do
    if [ -d "$candidate" ]; then
        gl_prepend_path "$candidate"
    fi
done
export PATH

SCRIPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_LIB_DIR/model-config.sh"

COMMON_PROVIDER=""
COMMON_VAULT=""
REMAINING_ARGS=()

gl_parse_common_args() {
    COMMON_PROVIDER=""
    COMMON_VAULT=""
    REMAINING_ARGS=()

    while [ $# -gt 0 ]; do
        case "$1" in
            --provider)
                if [ $# -lt 2 ]; then
                    echo "ERROR: --provider requires a value." >&2
                    return 1
                fi
                COMMON_PROVIDER="$2"
                shift 2
                ;;
            --vault)
                if [ $# -lt 2 ]; then
                    echo "ERROR: --vault requires a value." >&2
                    return 1
                fi
                COMMON_VAULT="$2"
                shift 2
                ;;
            --)
                shift
                while [ $# -gt 0 ]; do
                    REMAINING_ARGS+=("$1")
                    shift
                done
                ;;
            *)
                REMAINING_ARGS+=("$1")
                shift
                ;;
        esac
    done
}

gl_resolve_provider() {
    local raw="${1:-${GL_PROVIDER:-}}"
    case "$raw" in
        codex|claude)
            printf '%s\n' "$raw"
            ;;
        "")
            echo "ERROR: Choose a provider with --provider codex|claude or set GL_PROVIDER." >&2
            return 1
            ;;
        *)
            echo "ERROR: Unsupported provider '$raw'. Use codex or claude." >&2
            return 1
            ;;
    esac
}

gl_resolve_vault_path() {
    local raw="${1:-${GL_VAULT_PATH:-$HOME/Documents/Achaean}}"
    printf '%s\n' "$raw"
}

gl_daily_notes_folder() {
    local vault_path="$1"
    local config_path="$vault_path/.obsidian/daily-notes.json"

    if [ ! -f "$config_path" ]; then
        return 1
    fi

    python3 - "$config_path" <<'PY'
import json
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
except Exception:
    sys.exit(1)

folder = data.get("folder")
if not isinstance(folder, str) or not folder.strip():
    sys.exit(1)

print(folder.strip())
PY
}

gl_daily_note_relative_path() {
    local vault_path="$1"
    local offset_days="${2:-0}"
    local folder
    local date_slug

    folder="$(gl_daily_notes_folder "$vault_path")" || return 1
    date_slug="$(python3 - "$offset_days" <<'PY'
from datetime import date, timedelta
import sys

offset = int(sys.argv[1])
print((date.today() + timedelta(days=offset)).isoformat())
PY
)"

    printf '%s/%s.md\n' "$folder" "$date_slug"
}

gl_ensure_note_path() {
    local vault_path="$1"
    local relative_path="$2"
    local target_path="$vault_path/$relative_path"
    local target_dir

    target_dir="$(dirname "$target_path")"
    mkdir -p "$target_dir"
    touch "$target_path"
}

gl_prepend_file() {
    local target_path="$1"
    local snippet_path="$2"
    local tmp_path

    tmp_path="$(mktemp "${target_path}.XXXXXX.tmp")"

    if [ -s "$target_path" ]; then
        cat "$snippet_path" > "$tmp_path"
        printf '\n\n' >> "$tmp_path"
        cat "$target_path" >> "$tmp_path"
    else
        cat "$snippet_path" > "$tmp_path"
        printf '\n' >> "$tmp_path"
    fi

    mv "$tmp_path" "$target_path"
}

gl_provider_display_name() {
    case "$1" in
        codex) echo "Codex" ;;
        claude) echo "Claude" ;;
        *) echo "$1" ;;
    esac
}

gl_runtime_doc_for_provider() {
    case "$1" in
        codex) echo "AGENTS.md" ;;
        claude) echo "CLAUDE.md" ;;
        *) return 1 ;;
    esac
}

gl_assert_vault_runtime() {
    local provider="$1"
    local vault_path="$2"
    local runtime_doc

    runtime_doc="$(gl_runtime_doc_for_provider "$provider")" || return 1

    if [ ! -d "$vault_path" ]; then
        echo "ERROR: Vault not found at $vault_path" >&2
        return 1
    fi

    if [ ! -f "$vault_path/docs/FRAMEWORK.md" ]; then
        echo "ERROR: docs/FRAMEWORK.md not found in $vault_path" >&2
        return 1
    fi

    if [ ! -f "$vault_path/docs/STEWARD_SPEC.md" ]; then
        echo "ERROR: docs/STEWARD_SPEC.md not found in $vault_path" >&2
        return 1
    fi

    if [ ! -f "$vault_path/docs/STEWARD_CORE.md" ]; then
        echo "ERROR: docs/STEWARD_CORE.md not found in $vault_path" >&2
        return 1
    fi

    if [ ! -f "$vault_path/docs/policy/manifest.json" ]; then
        echo "ERROR: docs/policy/manifest.json not found in $vault_path" >&2
        return 1
    fi

    if [ ! -f "$vault_path/$runtime_doc" ]; then
        echo "ERROR: $runtime_doc not found in $vault_path" >&2
        return 1
    fi
}

gl_assert_provider_ready() {
    local provider="$1"

    if [ "$provider" = "claude" ]; then
        if ! command -v claude >/dev/null 2>&1; then
            echo "ERROR: Claude CLI not found on PATH." >&2
            return 1
        fi

        if ! claude --version >/dev/null 2>&1; then
            echo "ERROR: Claude CLI is installed but did not return a version." >&2
            return 1
        fi

        if ! env -u CLAUDECODE claude -p "ping" --max-turns 1 --permission-mode bypassPermissions >/dev/null 2>&1; then
            echo "ERROR: Claude CLI is not ready. Run 'claude' once and complete authentication." >&2
            return 1
        fi

        return 0
    fi

    if ! command -v codex >/dev/null 2>&1; then
        echo "ERROR: Codex CLI not found on PATH." >&2
        return 1
    fi

    if ! codex --version >/dev/null 2>&1; then
        echo "ERROR: Codex CLI is installed but did not return a version." >&2
        return 1
    fi

    local codex_root="$HOME/.codex"
    local sessions_dir="$codex_root/sessions"

    if [ -e "$codex_root" ] && [ ! -w "$codex_root" ]; then
        echo "ERROR: Codex cannot write to $codex_root." >&2
        return 1
    fi

    if [ ! -e "$codex_root" ] && [ ! -w "$HOME" ]; then
        echo "ERROR: Codex cannot create $codex_root because $HOME is not writable." >&2
        return 1
    fi

    if [ -e "$sessions_dir" ] && [ ! -w "$sessions_dir" ]; then
        echo "ERROR: Codex cannot write session files in $sessions_dir." >&2
        return 1
    fi

    return 0
}

gl_run_provider_prompt() {
    local provider="$1"
    local vault_path="$2"
    local prompt="$3"
    local max_turns="$4"
    local model="${5:-}"

    gl_assert_vault_runtime "$provider" "$vault_path" || return 1
    gl_assert_provider_ready "$provider" || return 1

    if [ "$provider" = "claude" ]; then
        local cmd=(claude -p "$prompt" --max-turns "$max_turns" --permission-mode bypassPermissions)
        if [ -n "$model" ]; then
            cmd+=(--model "$model")
        fi

        (
            cd "$vault_path" || exit 1
            env -u CLAUDECODE "${cmd[@]}"
        )
        return $?
    fi

    local cmd=(codex -a never exec -C "$vault_path" --skip-git-repo-check --sandbox workspace-write)
    if [ -n "$model" ]; then
        cmd+=(--model "$model")
    fi
    cmd+=("$prompt")

    "${cmd[@]}"
}

gl_run_provider_prompt_to_file() {
    local provider="$1"
    local vault_path="$2"
    local prompt="$3"
    local max_turns="$4"
    local model="${5:-}"
    local output_path="$6"

    gl_assert_vault_runtime "$provider" "$vault_path" || return 1
    gl_assert_provider_ready "$provider" || return 1

    mkdir -p "$(dirname "$output_path")"

    if [ "$provider" = "claude" ]; then
        local cmd=(claude -p "$prompt" --max-turns "$max_turns" --permission-mode bypassPermissions)
        if [ -n "$model" ]; then
            cmd+=(--model "$model")
        fi

        (
            cd "$vault_path" || exit 1
            env -u CLAUDECODE "${cmd[@]}" > "$output_path"
        )
        return $?
    fi

    local cmd=(codex -a never exec -C "$vault_path" --skip-git-repo-check --sandbox read-only --output-last-message "$output_path")
    if [ -n "$model" ]; then
        cmd+=(--model "$model")
    fi
    cmd+=("$prompt")

    "${cmd[@]}"
}

gl_build_policy_packet() {
    local vault_path="$1"
    local surface="$2"
    local workflow="$3"
    local provider="$4"
    local write_intent="$5"
    shift 5

    local cmd=(
        python3
        "$SCRIPT_LIB_DIR/../build_policy_packet.py"
        --vault "$vault_path"
        --surface "$surface"
        --workflow "$workflow"
        --provider "$provider"
        --write-intent "$write_intent"
    )

    for intent_tag in "$@"; do
        cmd+=(--intent-tag "$intent_tag")
    done

    "${cmd[@]}"
}
