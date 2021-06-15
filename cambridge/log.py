"""
This script sets up logger.
"""
import os
import logging
from pathlib import Path

try:
    data = Path(os.environ["XDG_DATA_HOME"]).absolute() / "cambridge"
except KeyError:
    data = Path(os.environ["HOME"]).absolute() / ".local" / "share" / "cambridge"

data.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(data / "dict.log"),
    filemode="a",
    format="%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s",
    level=logging.DEBUG,
)

logger = logging.getLogger("cambridge")
