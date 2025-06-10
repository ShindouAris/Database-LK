import json
import pathlib

DATA_DIR = pathlib.Path(__file__).parent.parent / "Data"

def read_json_file(file_path: str):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)
    

def get_captions_post():
    return read_json_file(DATA_DIR / "captions-post.json")

def get_timelines():
    return read_json_file(DATA_DIR / "timelines.json")

def get_donators():
    return read_json_file(DATA_DIR / "donators.json")

def get_themes():
    return read_json_file(DATA_DIR / "themes.json")

def get_notifications():
    return read_json_file(DATA_DIR / "notification.json")