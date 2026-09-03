from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.config import load_config
from backend.database import init_db
from backend.mitm_manager import stop_capture
from backend.network import api_urls
from backend.paths import MITM_CONFDIR, ca_cert_pem_path, ensure_dirs
from backend.routers.api import router as api_router
from backend.routers.projects import router as projects_router
from backend.routers.recon import router as recon_router
from backend.routers.query import router as query_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_dirs()
    init_db()
    yield
    stop_capture()


app = FastAPI(
    title="Passive MITM Capture",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(query_router)
app.include_router(api_router)
app.include_router(projects_router)
app.include_router(recon_router)


@app.get("/api/health")
def health():
    cfg = load_config()
    endpoints = api_urls(cfg["api_host"], cfg["api_port"])
    return {
        "ok": True,
        "api_host": cfg["api_host"],
        "api_port": cfg["api_port"],
        **endpoints,
    }


@app.get("/api/ca-cert")
def ca_cert():
    path = ca_cert_pem_path()
    if not path.exists():
        return JSONResponse(
            {"ready": False, "detail": "CA 尚未生成，请先启动捕获"},
            status_code=404,
        )
    return FileResponse(
        path,
        media_type="application/x-pem-file",
        filename="mitmproxy-ca-cert.pem",
    )
