import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

log_dir = Path("debate_logs")
log_dir.mkdir(exist_ok=True)

logger = logging.getLogger("Debaite")
logger.setLevel(logging.DEBUG)
logger.propagate = False

formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)

if not logger.handlers:
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)

    file_h = RotatingFileHandler(
        log_dir / "debaite.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_h.setLevel(logging.DEBUG)
    file_h.setFormatter(formatter)
    logger.addHandler(file_h)


def get_debate_logger(topic_name, session_id, debate_id):
    safe_topic = (
        "".join(c if c.isalnum() or c in (" ", "-", "_") else "" for c in topic_name)
        .strip()
        .replace(" ", "_")
        .lower()
    )
    path = log_dir / safe_topic / session_id
    path.mkdir(parents=True, exist_ok=True)

    debate_logger = logging.getLogger(f"Debate_{debate_id}")
    debate_logger.setLevel(logging.DEBUG)
    debate_logger.propagate = False

    if not debate_logger.handlers:
        fh = logging.FileHandler(path / f"{debate_id}.log", encoding="utf-8")
        fh.setFormatter(
            logging.Formatter("%(asctime)s - %(message)s", datefmt="%H:%M:%S")
        )
        debate_logger.addHandler(fh)

    return debate_logger
