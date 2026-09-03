from __future__ import annotations

import os
import shutil
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
USER_DATA_DIR = user_config_dir() / "data"
DATA_DIR = runtime_home() / "data"
RUN_DIR = runtime_home() / "run"
LOG_DIR = runtime_home() / "logs"
DB_PATH = DATA_DIR / "packets.db"
PAUSE_FLAG = RUN_DIR / "paused.flag"
MITM_PID_FILE = RUN_DIR / "mitm.pid"
API_PID_FILE = RUN_DIR / "api.pid"
# Always under user home so the same CA is reused across dev sessions and project paths.
MITM_CONFDIR = USER_DATA_DIR / "mitmproxy"


def ca_cert_pem_path() -> Path:
    return MITM_CONFDIR / "mitmproxy-ca-cert.pem"


def _legacy_mitm_confdirs() -> list[Path]:
    candidates = [
        ROOT / "data" / "mitmproxy",
        runtime_home() / "data" / "mitmproxy",
        Path.home() / ".wiretap" / "data" / "mitmproxy",
    ]
    seen: set[Path] = set()
    legacy: list[Path] = []
    target = MITM_CONFDIR.resolve()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or resolved == target:
            continue
        seen.add(resolved)
        legacy.append(path)
    return legacy


def migrate_legacy_mitm_confdir() -> None:
    """Copy an existing project-local mitm CA into the stable user confdir once."""
    if ca_cert_pem_path().exists():
        return
    MITM_CONFDIR.mkdir(parents=True, exist_ok=True)
    for legacy in _legacy_mitm_confdirs():
        pem = legacy / "mitmproxy-ca-cert.pem"
        if not pem.exists():
            continue
        for item in legacy.iterdir():
            if not item.is_file():
                continue
            dest = MITM_CONFDIR / item.name
            if not dest.exists():
                shutil.copy2(item, dest)
        return


def ensure_dirs() -> None:
    user_config_dir().mkdir(parents=True, exist_ok=True)
    migrate_legacy_mitm_confdir()
    for path in (DATA_DIR, RUN_DIR, LOG_DIR, USER_DATA_DIR, MITM_CONFDIR):
        path.mkdir(parents=True, exist_ok=True)
