"""
credentials.py — Read credentials from ~/.config/generous-ledger/credentials/.

Credentials are stored OUTSIDE the vault (which syncs to cloud) in a
directory with restrictive permissions.

USAGE:
    from lib.credentials import load_credential, get_config

    token = load_credential("ynab")  # reads ~/.config/generous-ledger/credentials/ynab.json
    config = get_config()            # reads ~/.config/generous-ledger/config.yaml
"""

import json
import os
import yaml
from pathlib import Path


CONFIG_DIR = Path.home() / ".config" / "generous-ledger"
CREDENTIALS_DIR = CONFIG_DIR / "credentials"


def ensure_config_dirs() -> None:
    """Create config directories with restrictive permissions if they don't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    # Set restrictive permissions on credentials directory
    os.chmod(CREDENTIALS_DIR, 0o700)


def load_credential(name: str) -> dict:
    """Load a credential file by name (without extension).

    Args:
        name: Credential name (e.g., "ynab", "google-calendar")

    Returns:
        Dict of credential data.

    Raises:
        FileNotFoundError: If credential file doesn't exist.
    """
    path = CREDENTIALS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Credential not found: {path}\n"
            f"Create it with the appropriate API key/token."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def save_credential(name: str, data: dict) -> Path:
    """Save a credential file.

    Args:
        name: Credential name (e.g., "google-calendar")
        data: Credential data to save.

    Returns:
        Path to the saved file.
    """
    ensure_config_dirs()
    path = CREDENTIALS_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.chmod(path, 0o600)
    return path


def get_config() -> dict:
    """Load the main config file.

    Returns:
        Dict of config data, or defaults if file doesn't exist.
    """
    config_path = CONFIG_DIR / "config.yaml"
    if not config_path.exists():
        return {
            "vault_path": "~/Documents/Achaean",
            "adapters": {
                "weather": {"enabled": True},
                "calendar": {"enabled": False},
                "health": {"enabled": False},
                "finance": {"enabled": False},
                "tasks": {"enabled": False},
            },
        }
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))
