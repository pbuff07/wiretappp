from __future__ import annotations

from fastapi import APIRouter, Query

from backend import database
from backend.timeutil import parse_query_time

router = APIRouter(prefix="/api", tags=["query"])


@router.get("/packets")
def query_packets(
    host: str | None = Query(default=None, description="按 host 过滤"),
    start: str | None = Query(default=None, description="开始时间，UTC+8"),
    end: str | None = Query(default=None, description="结束时间，UTC+8"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    unique_key: str | None = Query(default=None, description="传入则返回原始数据包"),
    project_id: int | None = Query(default=None, description="按项目域名范围过滤"),
):
    start_iso = parse_query_time(start)
    end_iso = parse_query_time(end)
    if unique_key:
        result = database.list_raw_packets(
            unique_key=unique_key,
            host=host,
            start=start_iso,
            end=end_iso,
            page=page,
            page_size=page_size,
            project_id=project_id,
        )
        result["mode"] = "raw"
        return result
    result = database.list_unique_keys(
        host=host,
        start=start_iso,
        end=end_iso,
        page=page,
        page_size=page_size,
        project_id=project_id,
    )
    result["mode"] = "keys"
    return result


@router.get("/hosts")
def query_hosts(project_id: int | None = Query(default=None)):
    return {"items": database.list_hosts(project_id=project_id)}


@router.get("/stats")
def query_stats():
    return database.stats()
