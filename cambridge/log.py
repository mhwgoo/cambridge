import os
from pathlib import Path
import logging

try:
    data = Path(os.environ["XDG_DATA_HOME"]).absolute() / "cambrige"
except KeyError:
    data = Path(os.environ["HOME"]).absolute() / ".local" / "share" / "cambrige"

data.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(data / "dict.log"),
    filemode="a",
    format="%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s",
    level=logging.DEBUG,
)

logger = logging.getLogger("cambrige")
