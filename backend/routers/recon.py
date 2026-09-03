from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend import endpoints as endpoint_service
from backend.timeutil import parse_query_time

router = APIRouter(prefix="/api", tags=["recon"])


@router.get("/endpoints")
def list_endpoints(
    host: str | None = Query(default=None),
    method: str | None = Query(default=None),
    path_contains: str | None = Query(default=None, description="path 子串匹配"),
    q: str | None = Query(default=None, description="搜索 path / host / key_label"),
    since: str | None = Query(default=None, description="仅 first_seen >= since 的端点"),
    project_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="last_seen", description="last_seen | first_seen | hit_count"),
):
    since_iso = parse_query_time(since)
    return endpoint_service.list_endpoints(
        host=host,
        method=method,
        path_contains=path_contains,
        q=q,
        since=since_iso,
        project_id=project_id,
        page=page,
        page_size=page_size,
        sort=sort,
    )


@router.get("/endpoints/new")
def list_new_endpoints(
    since: str = Query(..., description="起始时间（UTC+8），返回此时间后首次出现的端点"),
    project_id: int | None = Query(default=None),
    host: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    since_iso = parse_query_time(since)
    if not since_iso:
        raise HTTPException(status_code=422, detail="since 时间格式无效")
    return endpoint_service.list_new_endpoints(
        since=since_iso,
        project_id=project_id,
        host=host,
        page=page,
        page_size=page_size,
    )


@router.get("/endpoints/describe")
def describe_endpoint(
    fingerprint: str = Query(..., description="端点 MD5 指纹（unique_key）"),
    host: str = Query(..., description="host"),
    project_id: int | None = Query(default=None),
    include_raw: bool = Query(default=False, description="是否包含未脱敏 raw_packet"),
):
    detail = endpoint_service.describe_endpoint(
        fingerprint,
        host,
        project_id=project_id,
        include_raw=include_raw,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="端点不存在")
    return detail


@router.get("/sitemap")
def get_sitemap(
    project_id: int | None = Query(default=None),
    host: str | None = Query(default=None),
):
    return endpoint_service.build_sitemap(project_id=project_id, host=host)


@router.get("/recon")
def recon_project(
    project_id: int = Query(..., description="项目 ID"),
    since: str | None = Query(default=None, description="若提供则附带此时间后的新端点"),
    top: int = Query(default=20, ge=1, le=100, description="Top N 端点数量"),
):
    since_iso = parse_query_time(since) if since else None
    result = endpoint_service.recon_project(project_id, since=since_iso, top=top)
    if result is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return result
