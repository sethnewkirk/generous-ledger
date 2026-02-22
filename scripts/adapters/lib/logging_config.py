"""
logging_config.py — Shared logging setup for adapters.

Logs go to ~/.local/log/generous-ledger/ (same location as daily briefing logs).

USAGE:
    from lib.logging_config import setup_logging

    logger = setup_logging("weather")
    logger.info("Fetching weather data...")
"""

import logging
from pathlib import Path
from datetime import date


LOG_DIR = Path.home() / ".local" / "log" / "generous-ledger"


def setup_logging(adapter_name: str) -> logging.Logger:
    """Configure logging for an adapter.

    Args:
        adapter_name: Name of the adapter (used in log file name).

    Returns:
        Configured logger instance.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_file = LOG_DIR / f"{adapter_name}-{date.today().isoformat()}.log"

    logger = logging.getLogger(f"generous-ledger.{adapter_name}")
    logger.setLevel(logging.DEBUG)

    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )

    # Console handler (for manual runs)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(
        logging.Formatter("%(levelname)s %(message)s")
    )

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger
