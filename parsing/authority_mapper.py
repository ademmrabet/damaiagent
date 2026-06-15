import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
AUTHORITY_PATH = BASE_DIR / "Data" / "authority_codes.json"

with open(AUTHORITY_PATH, "r", encoding="utf-8") as f:
    AUTHORITY_CODES = json.load(f)


def get_authority_meaning(code, level=None):

    if code == "i":
        return AUTHORITY_CODES.get("i")

    if level is None:
        return None

    key = f"{code}{level}"

    return AUTHORITY_CODES.get(key)