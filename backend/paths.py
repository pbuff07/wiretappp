from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def user_config_dir() -> Path:
    """Per-user WIRETAPPP home (config always lives here)."""
    if env_home := os.environ.get("WIRETAPPP_HOME"):
        return Path(env_home).expanduser().resolve()
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home()
        return base / "wiretappp"
    if sys.platform == "darwin":
        return Path.home() / ".wiretappp"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "wiretappp"
    return Path.home() / ".wiretappp"


def runtime_home() -> Path:
    """Runtime data/logs/run: user home when packaged, project root in dev."""
    if os.environ.get("WIRETAPPP_PACKAGED") == "1":
        return user_config_dir()
    if os.environ.get("WIRETAPPP_HOME"):
        return user_config_dir()
    return ROOT


CONFIG_PATH = user_config_dir() / "config.yaml"
DATA_DIR = runtime_home() / "data"
RUN_DIR = runtime_home() / "run"
LOG_DIR = runtime_home() / "logs"
DB_PATH = DATA_DIR / "packets.db"
PAUSE_FLAG = RUN_DIR / "paused.flag"
MITM_PID_FILE = RUN_DIR / "mitm.pid"
API_PID_FILE = RUN_DIR / "api.pid"
MITM_CONFDIR = DATA_DIR / "mitmproxy"


def ensure_dirs() -> None:
    user_config_dir().mkdir(parents=True, exist_ok=True)
    for path in (DATA_DIR, RUN_DIR, LOG_DIR, MITM_CONFDIR):
        path.mkdir(parents=True, exist_ok=True)
