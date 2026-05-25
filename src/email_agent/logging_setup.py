import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once, with a single stream handler."""
    root = logging.getLogger()
    if root.handlers:  # idempotent — don't double-configure
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s | %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(level.upper())
