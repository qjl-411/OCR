import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.getenv('INVOICE_DATA_DIR', str(ROOT / 'runtime'))).resolve()
MAX_FILE = 20 * 1024 * 1024
MAX_BATCH = 100 * 1024 * 1024
MAX_FILES = 100
MAX_PAGES = 10
SUPPORTED = {'.pdf', '.png', '.jpg', '.jpeg'}


def ensure_dirs():
    for sub in ['', 'originals', 'previews']:
        (DATA / sub).mkdir(parents=True, exist_ok=True)
