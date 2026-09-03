from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse


def is_static_path(path_or_url: str, suffixes: list[str]) -> bool:
    parsed = urlparse(path_or_url)
    path = parsed.path or path_or_url.split("?", 1)[0]
    suffix = Path(path).suffix.lower()
    if not suffix:
        return False
    allowed = {s.lower() if s.startswith(".") else f".{s.lower()}" for s in suffixes}
    return suffix in allowed
