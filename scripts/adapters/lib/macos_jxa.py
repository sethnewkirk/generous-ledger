"""Run small JXA snippets through osascript and decode JSON output."""

from __future__ import annotations

import json
import subprocess


class MacOSBridgeError(RuntimeError):
    pass


def run_jxa_json(script: str, *, app_name: str, timeout: int = 60):
    try:
        completed = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise MacOSBridgeError("osascript is not available on this system.") from exc
    except subprocess.TimeoutExpired as exc:
        raise MacOSBridgeError(f"{app_name} query timed out after {timeout} seconds.") from exc

    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or f"{app_name} query failed."
        raise MacOSBridgeError(message)

    raw = completed.stdout.strip()
    if not raw:
        return []

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MacOSBridgeError(f"{app_name} returned invalid JSON.") from exc
