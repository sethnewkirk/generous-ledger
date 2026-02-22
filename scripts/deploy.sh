#!/bin/bash
# deploy.sh — Deploy all generous-ledger files to the Obsidian vault
#
# USAGE:
#   ./scripts/deploy.sh              # Deploy everything
#   ./scripts/deploy.sh --plugin     # Deploy only the plugin (build + copy)
#   ./scripts/deploy.sh --config     # Deploy only config files (CLAUDE.md, FRAMEWORK.md, templates)
#   ./scripts/deploy.sh --bases      # Deploy only Base views
#   ./scripts/deploy.sh --dry-run    # Show what would be deployed without doing it
#
# This replaces the manual copy commands scattered across the codebase.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VAULT_PATH="$HOME/Documents/Achaean"
PLUGIN_DIR="$VAULT_PATH/.obsidian/plugins/generous-ledger"

DRY_RUN=false
DEPLOY_PLUGIN=false
DEPLOY_CONFIG=false
DEPLOY_BASES=false
DEPLOY_ALL=true

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --plugin)  DEPLOY_PLUGIN=true; DEPLOY_ALL=false ;;
        --config)  DEPLOY_CONFIG=true; DEPLOY_ALL=false ;;
        --bases)   DEPLOY_BASES=true; DEPLOY_ALL=false ;;
        --dry-run) DRY_RUN=true ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: ./scripts/deploy.sh [--plugin] [--config] [--bases] [--dry-run]"
            exit 1
            ;;
    esac
done

if $DEPLOY_ALL; then
    DEPLOY_PLUGIN=true
    DEPLOY_CONFIG=true
    DEPLOY_BASES=true
fi

# Verify vault exists
if [ ! -d "$VAULT_PATH" ]; then
    echo "ERROR: Vault not found at $VAULT_PATH"
    exit 1
fi

copy_file() {
    local src="$1"
    local dst="$2"
    if $DRY_RUN; then
        echo "  [DRY RUN] $src -> $dst"
    else
        mkdir -p "$(dirname "$dst")"
        cp "$src" "$dst"
        echo "  $src -> $dst"
    fi
}

# --- Plugin deployment ---
if $DEPLOY_PLUGIN; then
    echo "Deploying plugin..."
    mkdir -p "$PLUGIN_DIR"

    if ! $DRY_RUN; then
        cd "$REPO_DIR"
        npm run build 2>&1 | tail -1
    else
        echo "  [DRY RUN] npm run build"
    fi

    copy_file "$REPO_DIR/main.js" "$PLUGIN_DIR/main.js"
    copy_file "$REPO_DIR/manifest.json" "$PLUGIN_DIR/manifest.json"
    copy_file "$REPO_DIR/styles.css" "$PLUGIN_DIR/styles.css"

    echo "  Plugin deployed."
fi

# --- Config deployment ---
if $DEPLOY_CONFIG; then
    echo "Deploying config files..."

    copy_file "$REPO_DIR/CLAUDE.md" "$VAULT_PATH/CLAUDE.md"
    copy_file "$REPO_DIR/docs/FRAMEWORK.md" "$VAULT_PATH/docs/FRAMEWORK.md"

    # Deploy templates if they exist
    if [ -d "$REPO_DIR/templates" ]; then
        for tmpl in "$REPO_DIR/templates"/*.md; do
            if [ -f "$tmpl" ]; then
                copy_file "$tmpl" "$VAULT_PATH/templates/$(basename "$tmpl")"
            fi
        done
    fi

    echo "  Config deployed."
fi

# --- Base views deployment ---
if $DEPLOY_BASES; then
    echo "Deploying Base views..."

    for base in "$REPO_DIR"/bases/*.base; do
        if [ -f "$base" ]; then
            copy_file "$base" "$VAULT_PATH/$(basename "$base")"
        fi
    done

    echo "  Base views deployed."
fi

echo ""
if $DRY_RUN; then
    echo "Dry run complete. No files were changed."
else
    echo "Deploy complete."

    # Reload plugin if Obsidian is running and we deployed plugin files
    if $DEPLOY_PLUGIN; then
        if /Applications/Obsidian.app/Contents/MacOS/Obsidian plugin:reload id=generous-ledger 2>/dev/null; then
            echo "Plugin reloaded."
        else
            echo "Note: Reload the plugin manually (Obsidian may not be running)."
        fi
    fi
fi
