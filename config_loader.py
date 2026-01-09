import logging
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def get_env(key, default=None):
    return os.environ.get(key, default)

DATA_DIR = Path(get_env("DATA_DIR", "./data")).absolute()
if not DATA_DIR.exists():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

CACHE_FILE = DATA_DIR / "movie_cache.json"
HISTORY_FILE = DATA_DIR / "processed_history.json"
LOG_FILE = DATA_DIR / "app.log"

TMDB_API_KEY = get_env("TMDB_API_KEY")
OMDB_API_KEY = get_env("OMDB_API_KEY")
MEDIA_DIR = os.path.abspath(get_env("MEDIA_DIRECTORY", "."))
OUTPUT_DIR = os.path.abspath(get_env("OUTPUT_DIRECTORY", MEDIA_DIR))
ACTION = get_env("ACTION", "move").lower()
DRY_RUN = get_env("DRY_RUN", "True").lower() in ("true", "1", "yes")

ALLOWED_CATEGORIES = get_env("ALLOWED_CATEGORIES", "").split(",")
PORT = int(get_env("SERVER_PORT", 5000))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("processor")