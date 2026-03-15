from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "lyrona"
DATA_HOME_ENV = "LYRONA_HOME"


def data_root() -> Path:
    custom_home = os.environ.get(DATA_HOME_ENV, "").strip()
    if custom_home:
        return Path(custom_home).expanduser().resolve()

    xdg_data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg_data_home:
        return (Path(xdg_data_home).expanduser() / APP_NAME).resolve()

    return (Path.home() / ".local" / "share" / APP_NAME).resolve()


DATA_DIR = data_root()
SONGS_DIR = DATA_DIR / "songs"
METADATA_CACHE_PATH = DATA_DIR / ".lyrona_metadata_cache.json"


def ensure_data_dirs() -> None:
    SONGS_DIR.mkdir(parents=True, exist_ok=True)
