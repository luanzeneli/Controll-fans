"""Save and load lighting profiles as JSON files in the profiles/ folder.

A profile captures the active effect and its settings so you can flip between
looks ("Gaming", "Chill", "Work") instantly.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List

PROFILE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "profiles")


def _ensure_dir():
    os.makedirs(PROFILE_DIR, exist_ok=True)


def list_profiles() -> List[str]:
    _ensure_dir()
    return sorted(
        f[:-5] for f in os.listdir(PROFILE_DIR) if f.endswith(".json")
    )


def save_profile(name: str, data: Dict) -> str:
    _ensure_dir()
    safe = "".join(c for c in name if c.isalnum() or c in " -_").strip()
    if not safe:
        safe = "profile"
    path = os.path.join(PROFILE_DIR, f"{safe}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return safe


def load_profile(name: str) -> Dict:
    path = os.path.join(PROFILE_DIR, f"{name}.json")
    with open(path) as f:
        return json.load(f)


def delete_profile(name: str) -> None:
    path = os.path.join(PROFILE_DIR, f"{name}.json")
    if os.path.exists(path):
        os.remove(path)
