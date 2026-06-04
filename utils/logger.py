"""
logger.py — PiCamPro Logging Configuration
===========================================
Sets up file + console logging for the entire application.
"""

import logging
import logging.handlers
import sys
from pathlib import Path


def setup_logging(log_dir: Path, level: int = logging.INFO) -> None:
    """
    Configure root logger with:
      - Rotating file handler  → log_dir/picampro.log
      - Coloured stream handler → stdout

    Call this once at application startup before importing any other module.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "picampro.log"

    fmt = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    root.setLevel(level)

    # Rotating file handler (10 MB × 5 backup files)
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter(fmt, date_fmt))
    root.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(_ColourFormatter(fmt, date_fmt))
    root.addHandler(ch)

    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("picamera2").setLevel(logging.WARNING)


class _ColourFormatter(logging.Formatter):
    """Adds ANSI colour to console log levels for readability."""
    COLOURS = {
        logging.DEBUG:    "\033[36m",   # cyan
        logging.INFO:     "\033[32m",   # green
        logging.WARNING:  "\033[33m",   # yellow
        logging.ERROR:    "\033[31m",   # red
        logging.CRITICAL: "\033[1;31m", # bold red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        colour = self.COLOURS.get(record.levelno, "")
        record.levelname = f"{colour}{record.levelname}{self.RESET}"
        return super().format(record)
