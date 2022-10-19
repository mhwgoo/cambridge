"""
This script sets up logger.
"""

import logging

# Logging only to stdout, not to local
# data = Path.home() / ".local" / "share" / "cambridge"
# data.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    # filename=str(data / "dict.log"),
    # filemode="a",
    # format="%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s",
    format="%(asctime)s %(levelname)s %(filename)s[%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)

logger = logging.getLogger(
    __package__
)  # if imported, all modules will have the same logger called by name of __package__'s value'
