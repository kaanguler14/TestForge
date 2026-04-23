import json
import os


def read_json(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"{filepath} not found")
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in {filepath}")
