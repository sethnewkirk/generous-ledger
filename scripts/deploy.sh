#!/bin/bash
# deploy.sh — Deploy plugin assets, runtime docs, templates, and bases into a vault

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VAULT_PATH="${GL_VAULT_PATH:-$HOME/Documents/Achaean}"
PLUGIN_DIR="$VAULT_PATH/.obsidian/plugins/generous-ledger"

DRY_RUN=false
DEPLOY_PLUGIN=false
DEPLOY_CONFIG=false
DEPLOY_BASES=false
DEPLOY_ALL=true

while [ $# -gt 0 ]; do
    case "$1" in
        --plugin)
            DEPLOY_PLUGIN=true
            DEPLOY_ALL=false
            shift
            ;;
        --config)
            DEPLOY_CONFIG=true
            DEPLOY_ALL=false
            shift
            ;;
        --bases)
            DEPLOY_BASES=true
            DEPLOY_ALL=false
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --vault)
            if [ $# -lt 2 ]; then
                echo "ERROR: --vault requires a path." >&2
                exit 1
            fi
            VAULT_PATH="$2"
            PLUGIN_DIR="$VAULT_PATH/.obsidian/plugins/generous-ledger"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            echo "Usage: ./scripts/deploy.sh [--plugin] [--config] [--bases] [--dry-run] [--vault PATH]" >&2
            exit 1
            ;;
    esac
done

if $DEPLOY_ALL; then
    DEPLOY_PLUGIN=true
    DEPLOY_CONFIG=true
    DEPLOY_BASES=true
fi

if [ ! -d "$VAULT_PATH" ]; then
    echo "ERROR: Vault not found at $VAULT_PATH" >&2
    exit 1
fi

copy_file() {
    local src="$1"
    local dst="$2"
    if $DRY_RUN; then
        echo "  [DRY RUN] $src -> $dst"
        return
    fi

    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    echo "  $src -> $dst"
}

copy_tree() {
    local src_root="$1"
    local dst_root="$2"
    if [ ! -d "$src_root" ]; then
        return
    fi

    while IFS= read -r src; do
        local rel="${src#$src_root/}"
        copy_file "$src" "$dst_root/$rel"
    done < <(find "$src_root" -type f)
}

if $DEPLOY_PLUGIN; then
    echo "Deploying plugin..."
    if ! $DRY_RUN; then
        cd "$REPO_DIR"
        npm run build
    else
        echo "  [DRY RUN] npm run build"
    fi

    mkdir -p "$PLUGIN_DIR"
    copy_file "$REPO_DIR/main.js" "$PLUGIN_DIR/main.js"
    copy_file "$REPO_DIR/manifest.json" "$PLUGIN_DIR/manifest.json"
    copy_file "$REPO_DIR/styles.css" "$PLUGIN_DIR/styles.css"
fi

if $DEPLOY_CONFIG; then
    echo "Deploying runtime docs and templates..."
    copy_file "$REPO_DIR/AGENTS.md" "$VAULT_PATH/AGENTS.md"
    copy_file "$REPO_DIR/CLAUDE.md" "$VAULT_PATH/CLAUDE.md"
    copy_file "$REPO_DIR/docs/FRAMEWORK.md" "$VAULT_PATH/docs/FRAMEWORK.md"
    copy_file "$REPO_DIR/docs/STEWARD_SPEC.md" "$VAULT_PATH/docs/STEWARD_SPEC.md"
    copy_file "$REPO_DIR/docs/STEWARD_CORE.md" "$VAULT_PATH/docs/STEWARD_CORE.md"
    copy_tree "$REPO_DIR/docs/framework" "$VAULT_PATH/docs/framework"
    copy_tree "$REPO_DIR/docs/spec" "$VAULT_PATH/docs/spec"
    copy_tree "$REPO_DIR/docs/policy" "$VAULT_PATH/docs/policy"

    if [ -d "$REPO_DIR/templates" ]; then
        for tmpl in "$REPO_DIR"/templates/*.md; do
            if [ -f "$tmpl" ]; then
                copy_file "$tmpl" "$VAULT_PATH/templates/$(basename "$tmpl")"
            fi
        done
    fi
fi

if $DEPLOY_BASES; then
    echo "Deploying bases..."
    if [ -d "$REPO_DIR/bases" ]; then
        for base in "$REPO_DIR"/bases/*.base; do
            if [ -f "$base" ]; then
                copy_file "$base" "$VAULT_PATH/bases/$(basename "$base")"
            fi
        done
    fi
fi

if $DRY_RUN; then
    echo "Dry run complete. No files were changed."
    exit 0
fi

echo "Deploy complete."

if $DEPLOY_PLUGIN; then
    if /Applications/Obsidian.app/Contents/MacOS/Obsidian plugin:reload id=generous-ledger 2>/dev/null; then
        echo "Plugin reloaded."
    else
        echo "Note: Reload the plugin manually if Obsidian is not running."
    fi
fi
