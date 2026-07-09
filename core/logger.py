"""Per-client logging — writes to logs/[client_id]_batch.log."""
import logging
from pathlib import Path


def get_logger(client_id: str) -> logging.Logger:
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"{client_id}_batch.log"

    logger = logging.getLogger(client_id)
    if logger.handlers:
        return logger  # already configured in this session

    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s"))

    logger.addHandler(file_handler)
    return logger
