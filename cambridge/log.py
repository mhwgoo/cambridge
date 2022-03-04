"""
This script sets up logger.
"""
import os
import logging
from pathlib import Path

# Logging only to stdout, not to local
# data = Path.home() / ".local" / "share" / "cambridge"
# data.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    # filename=str(data / "dict.log"),
    # filemode="a",
    format="%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__package__)
