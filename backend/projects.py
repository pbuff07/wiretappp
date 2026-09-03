from __future__ import annotations

import json
import sqlite3
from typing import Any

from backend.database import connect, init_db
from backend.domain_match import host_match_sql, normalize_domain_pattern
from backend.timeutil import now_cst_iso


def _row_to_project(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["domains"] = json.loads(data["domains"])
    return data


def _ensure_projects_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            domains TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at)")


def get_project(project_id: int) -> dict[str, Any] | None:
    init_db()
    conn = connect()
    try:
        _ensure_projects_table(conn)
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return _row_to_project(row) if row else None
    finally:
        conn.close()


def normalize_domains(domains: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in domains:
        pattern = normalize_domain_pattern(raw)
        if not pattern or pattern in seen:
            continue
        seen.add(pattern)
        cleaned.append(pattern)
    return cleaned


def create_project(name: str, domains: list[str]) -> dict[str, Any]:
    init_db()
    title = name.strip()
    if not title:
        raise ValueError("项目名称不能为空")
    domain_list = normalize_domains(domains)
    if not domain_list:
        raise ValueError("至少填写一个域名范围")
    created_at = now_cst_iso()
    conn = connect()
    try:
        _ensure_projects_table(conn)
        cur = conn.execute(
            "INSERT INTO projects (name, domains, created_at) VALUES (?, ?, ?)",
            (title, json.dumps(domain_list, ensure_ascii=False), created_at),
        )
        conn.commit()
        project_id = int(cur.lastrowid)
    finally:
        conn.close()
    project = get_project(project_id)
    assert project is not None
    return project


def list_projects() -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        _ensure_projects_table(conn)
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC, id DESC").fetchall()
        return [_row_to_project(row) for row in rows]
    finally:
        conn.close()


def _project_stats(conn: sqlite3.Connection, domains: list[str]) -> dict[str, int]:
    clause, args = host_match_sql(domains)
    where = f"WHERE {clause}"
    subdomain_count = conn.execute(
        f"SELECT COUNT(DISTINCT host) FROM packets {where}",
        args,
    ).fetchone()[0]
    unique_key_count = conn.execute(
        f"SELECT COUNT(*) FROM (SELECT 1 FROM packets {where} GROUP BY unique_key, host)",
        args,
    ).fetchone()[0]
    packet_count = conn.execute(
        f"SELECT COUNT(*) FROM packets {where}",
        args,
    ).fetchone()[0]
    return {
        "subdomain_count": int(subdomain_count),
        "unique_key_count": int(unique_key_count),
        "packet_count": int(packet_count),
    }


def project_with_stats(project: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    stats = _project_stats(conn, project["domains"])
    return {**project, **stats}


def dashboard() -> dict[str, Any]:
    init_db()
    conn = connect()
    try:
        _ensure_projects_table(conn)
        projects = list_projects()
        items = [project_with_stats(project, conn) for project in projects]
        return {"project_count": len(items), "items": items}
    finally:
        conn.close()


def get_project_detail(project_id: int) -> dict[str, Any] | None:
    init_db()
    project = get_project(project_id)
    if project is None:
        return None
    conn = connect()
    try:
        return project_with_stats(project, conn)
    finally:
        conn.close()


def list_project_hosts(project_id: int) -> list[str]:
    project = get_project(project_id)
    if project is None:
        return []
    clause, args = host_match_sql(project["domains"])
    conn = connect()
    try:
        rows = conn.execute(
            f"""
            SELECT host, COUNT(*) AS n
            FROM packets
            WHERE {clause}
            GROUP BY host
            ORDER BY n DESC, host ASC
            """,
            args,
        ).fetchall()
        return [row["host"] for row in rows]
    finally:
        conn.close()


def delete_project(project_id: int) -> dict[str, Any] | None:
    init_db()
    project = get_project(project_id)
    if project is None:
        return None
    conn = connect()
    try:
        _ensure_projects_table(conn)
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
    finally:
        conn.close()
    return project
