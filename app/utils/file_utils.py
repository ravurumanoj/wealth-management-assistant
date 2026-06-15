import os
import json
from typing import Any, Dict

def save_json(path: str, data: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)

def load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return json.load(f)

def ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path)

