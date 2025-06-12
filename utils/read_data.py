import json
import pathlib
from functools import lru_cache

DATA_DIR = pathlib.Path(__file__).parent.parent / "Data"

@lru_cache(maxsize=1)
def read_json_file(file_path: str):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)
    

@lru_cache(maxsize=1)
def get_captions_post():
    return read_json_file(str(DATA_DIR / "captions-post.json"))

@lru_cache(maxsize=1)
def get_timelines():
    return read_json_file(str(DATA_DIR / "timelines.json"))

@lru_cache(maxsize=1)
def get_donators():
    return read_json_file(str(DATA_DIR / "donators.json"))

@lru_cache(maxsize=1)
def get_themes():
    return read_json_file(str(DATA_DIR / "themes.json"))

@lru_cache(maxsize=1)
def get_notifications():
    return read_json_file(str(DATA_DIR / "notification.json"))