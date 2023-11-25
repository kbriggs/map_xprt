import json
import os

DOTPATH = "~/.map_xprt"


def state_path(filename: str) -> str:
    return os.path.join(os.path.expanduser(DOTPATH), filename)


def _add_ext(stem: str) -> str:
    if stem.endswith(".json"):
        return stem
    return f"{stem}.json"


def read_json(stem: str) -> dict:
    path = state_path(_add_ext(stem))
    with open(path, "r") as f:
        return json.load(f)


def write_json(stem: str, data: dict) -> None:
    path = state_path(_add_ext(stem))
    with open(path, "w") as f:
        json.dump(dict, f)
