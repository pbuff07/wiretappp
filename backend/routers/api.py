from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import load_config, save_config
from backend import mitm_manager

router = APIRouter(prefix="/api", tags=["capture"])


class SettingsUpdate(BaseModel):
    listen_host: str | None = None
    listen_port: int | None = Field(default=None, ge=1, le=65535)
    api_host: str | None = None
    api_port: int | None = Field(default=None, ge=1, le=65535)
    static_suffixes: list[str] | None = None
    max_body_bytes: int | None = Field(default=None, ge=1024)


@router.get("/capture/status")
def capture_status():
    return mitm_manager.capture_state()


@router.post("/capture/start")
def capture_start():
    try:
        return mitm_manager.start_capture(unpause=True)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/capture/pause")
def capture_pause():
    state = mitm_manager.capture_state()
    if state["status"] == "stopped":
        raise HTTPException(status_code=409, detail="捕获进程未运行")
    mitm_manager.pause()
    return mitm_manager.capture_state()


@router.post("/capture/resume")
def capture_resume():
    state = mitm_manager.capture_state()
    if state["status"] == "stopped":
        raise HTTPException(status_code=409, detail="捕获进程未运行")
    mitm_manager.resume()
    return mitm_manager.capture_state()


@router.post("/capture/stop")
def capture_stop():
    return mitm_manager.stop_capture()


@router.get("/settings")
def get_settings():
    cfg = load_config()
    return {
        "listen_host": cfg["listen_host"],
        "listen_port": cfg["listen_port"],
        "api_host": cfg["api_host"],
        "api_port": cfg["api_port"],
        "static_suffixes": cfg["static_suffixes"],
        "max_body_bytes": cfg["max_body_bytes"],
    }


@router.put("/settings")
def update_settings(payload: SettingsUpdate):
    updates = payload.model_dump(exclude_none=True)
    if "static_suffixes" in updates:
        updates["static_suffixes"] = [
            s if str(s).startswith(".") else f".{s}"
            for s in updates["static_suffixes"]
        ]
    old = load_config()
    cfg = save_config(updates)
    restarted = False
    listen_changed = (
        cfg["listen_host"] != old["listen_host"]
        or int(cfg["listen_port"]) != int(old["listen_port"])
    )
    if listen_changed and mitm_manager.read_mitm_pid() is not None:
        mitm_manager.restart_capture(unpause=not mitm_manager.is_paused())
        restarted = True
    message = (
        f"监听已切换为 {cfg['listen_host']}:{cfg['listen_port']}，mitm 已自动重启"
        if restarted
        else "配置已保存"
    )
    return {
        "settings": cfg,
        "mitm_restarted": restarted,
        "message": message,
        "capture": mitm_manager.capture_state(),
    }
