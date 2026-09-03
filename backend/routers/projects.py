from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend import projects as project_service

router = APIRouter(prefix="/api", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    domains: list[str] = Field(min_length=1)


@router.get("/dashboard")
def get_dashboard():
    return project_service.dashboard()


@router.get("/projects")
def list_projects():
    return {"items": project_service.list_projects()}


@router.post("/projects")
def create_project(payload: ProjectCreate):
    try:
        project = project_service.create_project(payload.name, payload.domains)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    detail = project_service.get_project_detail(project["id"])
    return detail or project


@router.get("/projects/{project_id}")
def get_project(project_id: int):
    detail = project_service.get_project_detail(project_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return detail


@router.get("/projects/{project_id}/hosts")
def get_project_hosts(project_id: int):
    if project_service.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"items": project_service.list_project_hosts(project_id)}


@router.delete("/projects/{project_id}")
def delete_project(project_id: int):
    deleted = project_service.delete_project(project_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"ok": True, "deleted": deleted}
