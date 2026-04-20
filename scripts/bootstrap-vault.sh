#!/bin/bash
# bootstrap-vault.sh — Create a clean Obsidian steward vault and deploy the runtime into it

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib/provider-runner.sh"

VAULT_NAME=""
VAULT_PATH=""
INSTALL_SCHEDULE=false
SCHEDULE_PROVIDER=""

usage() {
    echo "USAGE: ./scripts/bootstrap-vault.sh --name NAME [--vault PATH] [--install-schedule --provider codex|claude]" >&2
}

while [ $# -gt 0 ]; do
    case "$1" in
        --name)
            if [ $# -lt 2 ]; then
                echo "ERROR: --name requires a value." >&2
                usage
                exit 1
            fi
            VAULT_NAME="$2"
            shift 2
            ;;
        --vault)
            if [ $# -lt 2 ]; then
                echo "ERROR: --vault requires a value." >&2
                usage
                exit 1
            fi
            VAULT_PATH="$2"
            shift 2
            ;;
        --install-schedule)
            INSTALL_SCHEDULE=true
            shift
            ;;
        --provider)
            if [ $# -lt 2 ]; then
                echo "ERROR: --provider requires a value." >&2
                usage
                exit 1
            fi
            SCHEDULE_PROVIDER="$2"
            shift 2
            ;;
        *)
            echo "ERROR: Unknown argument '$1'." >&2
            usage
            exit 1
            ;;
    esac
done

if [ -z "$VAULT_NAME" ] && [ -z "$VAULT_PATH" ]; then
    echo "ERROR: Provide --name NAME or --vault PATH." >&2
    usage
    exit 1
fi

if [ -z "$VAULT_PATH" ]; then
    VAULT_PATH="$HOME/Documents/$VAULT_NAME"
fi

if [ -z "$VAULT_NAME" ]; then
    VAULT_NAME="$(basename "$VAULT_PATH")"
fi

if $INSTALL_SCHEDULE; then
    SCHEDULE_PROVIDER="$(gl_resolve_provider "$SCHEDULE_PROVIDER")" || exit 1
fi

if [ -e "$VAULT_PATH" ] && [ -n "$(find "$VAULT_PATH" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
    echo "ERROR: Vault path already exists and is not empty: $VAULT_PATH" >&2
    exit 1
fi

mkdir -p \
    "$VAULT_PATH/.obsidian/plugins" \
    "$VAULT_PATH/01_personal" \
    "$VAULT_PATH/data" \
    "$VAULT_PATH/diary" \
    "$VAULT_PATH/reviews/weekly" \
    "$VAULT_PATH/reviews/monthly" \
    "$VAULT_PATH/templates" \
    "$VAULT_PATH/bases"

cat > "$VAULT_PATH/.obsidian/core-plugins.json" <<'EOF'
{
  "file-explorer": true,
  "global-search": true,
  "switcher": true,
  "graph": true,
  "backlink": true,
  "canvas": true,
  "outgoing-link": true,
  "tag-pane": true,
  "footnotes": false,
  "properties": false,
  "page-preview": true,
  "daily-notes": true,
  "templates": true,
  "note-composer": true,
  "command-palette": true,
  "slash-command": false,
  "editor-status": true,
  "bookmarks": true,
  "markdown-importer": false,
  "zk-prefixer": false,
  "random-note": false,
  "outline": true,
  "word-count": true,
  "slides": false,
  "audio-recorder": false,
  "workspaces": false,
  "file-recovery": true,
  "publish": false,
  "sync": true,
  "bases": true,
  "webviewer": false
}
EOF

cat > "$VAULT_PATH/.obsidian/daily-notes.json" <<'EOF'
{
  "template": "",
  "folder": "01_personal"
}
EOF

cat > "$VAULT_PATH/.obsidian/community-plugins.json" <<'EOF'
[
  "generous-ledger"
]
EOF

cat > "$VAULT_PATH/.obsidian/app.json" <<'EOF'
{
  "alwaysUpdateLinks": true,
  "openBehavior": "daily"
}
EOF

cat > "$VAULT_PATH/Start Here.md" <<EOF
# $VAULT_NAME

This is a clean steward vault bootstrapped from Generous Ledger.

## Next Steps

1. Open this folder as an Obsidian vault.
2. Confirm the \`generous-ledger\` community plugin is enabled.
3. Open any note and use \`@Steward\`, or run the \`Begin onboarding\` command.
4. Configure the provider in plugin settings.

The daily notes folder is \`01_personal/\`.
EOF

bash "$SCRIPT_DIR/deploy.sh" --vault "$VAULT_PATH"

if $INSTALL_SCHEDULE; then
    bash "$SCRIPT_DIR/install-schedule.sh" --provider "$SCHEDULE_PROVIDER" --vault "$VAULT_PATH"
fi

echo "Bootstrapped steward vault:"
echo "  Name: $VAULT_NAME"
echo "  Path: $VAULT_PATH"
if $INSTALL_SCHEDULE; then
    echo "  Schedules: installed for $(gl_provider_display_name "$SCHEDULE_PROVIDER")"
else
    echo "  Schedules: unchanged"
fi
