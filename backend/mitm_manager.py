from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from backend.config import load_config
from backend.paths import (
    LOG_DIR,
    MITM_CONFDIR,
    MITM_PID_FILE,
    PAUSE_FLAG,
    ROOT,
    ca_cert_pem_path,
    ensure_dirs,
)

_proc: subprocess.Popen | None = None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_mitm_pid() -> int | None:
    if not MITM_PID_FILE.exists():
        return None
    try:
        pid = int(MITM_PID_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        return None
    if _pid_alive(pid):
        return pid
    MITM_PID_FILE.unlink(missing_ok=True)
    return None


def is_paused() -> bool:
    return PAUSE_FLAG.exists()


def pause() -> None:
    ensure_dirs()
    PAUSE_FLAG.write_text("1\n", encoding="utf-8")


def resume() -> None:
    PAUSE_FLAG.unlink(missing_ok=True)


def capture_state() -> dict:
    cfg = load_config()
    pid = read_mitm_pid()
    paused = is_paused()
    if pid is None:
        status = "stopped"
    elif paused:
        status = "paused"
    else:
        status = "running"
    ca_cert = ca_cert_pem_path()
    return {
        "status": status,
        "paused": paused,
        "pid": pid,
        "listen_host": cfg["listen_host"],
        "listen_port": cfg["listen_port"],
        "mitm_confdir": str(MITM_CONFDIR),
        "ca_cert_ready": ca_cert.exists(),
        "ca_cert_path": str(ca_cert),
        "static_suffixes": cfg["static_suffixes"],
    }


def start_capture(*, unpause: bool = True) -> dict:
    global _proc
    ensure_dirs()
    existing = read_mitm_pid()
    if existing is not None:
        if unpause:
            resume()
        return capture_state()

    cfg = load_config()
    python = sys.executable
    addon = ROOT / "backend" / "capture_addon.py"
    log_file = LOG_DIR / "mitm.log"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    mitmdump = Path(python).parent / "mitmdump"
    if mitmdump.exists():
        cmd = [str(mitmdump)]
    else:
        cmd = [python, "-m", "mitmproxy.tools.dump"]
    cmd.extend(
        [
            "-s",
            str(addon),
            "--listen-host",
            str(cfg["listen_host"]),
            "--listen-port",
            str(cfg["listen_port"]),
            "--set",
            f"confdir={MITM_CONFDIR}",
            "--set",
            "block_global=false",
            "--ssl-insecure",
        ]
    )
    fh = log_file.open("a", encoding="utf-8")
    _proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    MITM_PID_FILE.write_text(str(_proc.pid), encoding="utf-8")
    if unpause:
        resume()
    time.sleep(0.4)
    if _proc.poll() is not None:
        raise RuntimeError(f"mitm 进程启动失败，详见 {log_file}")
    return capture_state()


def stop_capture() -> dict:
    global _proc
    pid = read_mitm_pid()
    if pid is not None:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except OSError:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        for _ in range(20):
            if not _pid_alive(pid):
                break
            time.sleep(0.1)
        if _pid_alive(pid):
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except OSError:
                pass
    MITM_PID_FILE.unlink(missing_ok=True)
    _proc = None
    return capture_state()


def restart_capture(*, unpause: bool | None = None) -> dict:
    if unpause is None:
        unpause = not is_paused()
    stop_capture()
    return start_capture(unpause=unpause)
