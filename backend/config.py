from __future__ import annotations

from copy import deepcopy
from typing import Any

import yaml

from backend.paths import CONFIG_PATH, ROOT, ensure_dirs

DEFAULTS: dict[str, Any] = {
    "listen_host": "127.0.0.1",
    "listen_port": 8080,
    "api_host": "0.0.0.0",
    "api_port": 18760,
    "static_suffixes": [
        ".js",
        ".mjs",
        ".css",
        ".map",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".webp",
        ".bmp",
        ".avif",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".otf",
        ".mp4",
        ".webm",
        ".mp3",
        ".wav",
        ".ogg",
        ".pdf",
        ".zip",
        ".gz",
        ".wasm",
    ],
    "max_body_bytes": 524288,
}


def _seed_default_config() -> None:
    if CONFIG_PATH.exists():
        return
    bundled = ROOT / "config.yaml"
    if bundled.exists():
        CONFIG_PATH.write_text(bundled.read_text(encoding="utf-8"), encoding="utf-8")
        return
    with CONFIG_PATH.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(
            {
                "listen_host": DEFAULTS["listen_host"],
                "listen_port": DEFAULTS["listen_port"],
                "api_host": DEFAULTS["api_host"],
                "api_port": DEFAULTS["api_port"],
                "static_suffixes": DEFAULTS["static_suffixes"],
                "max_body_bytes": DEFAULTS["max_body_bytes"],
            },
            fh,
            allow_unicode=True,
            sort_keys=False,
        )


def load_config() -> dict[str, Any]:
    ensure_dirs()
    _seed_default_config()
    cfg = deepcopy(DEFAULTS)
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        if not isinstance(raw, dict):
            raise ValueError("config.yaml 必须是映射结构")
        cfg.update(raw)
    cfg["listen_port"] = int(cfg["listen_port"])
    cfg["api_port"] = int(cfg["api_port"])
    cfg["max_body_bytes"] = int(cfg["max_body_bytes"])
    suffixes = cfg.get("static_suffixes") or []
    cfg["static_suffixes"] = [
        s if str(s).startswith(".") else f".{s}" for s in suffixes
    ]
    return cfg


def save_config(updates: dict[str, Any]) -> dict[str, Any]:
    cfg = load_config()
    for key, value in updates.items():
        if key not in DEFAULTS:
            continue
        cfg[key] = value
    cfg["listen_port"] = int(cfg["listen_port"])
    cfg["api_port"] = int(cfg["api_port"])
    cfg["max_body_bytes"] = int(cfg["max_body_bytes"])
    dump = {
        "listen_host": cfg["listen_host"],
        "listen_port": cfg["listen_port"],
        "api_host": cfg["api_host"],
        "api_port": cfg["api_port"],
        "static_suffixes": cfg["static_suffixes"],
        "max_body_bytes": cfg["max_body_bytes"],
    }
    with CONFIG_PATH.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(dump, fh, allow_unicode=True, sort_keys=False)
    return cfg
