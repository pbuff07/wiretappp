from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

from backend.domain_match import host_match_sql
from backend.paths import DB_PATH, ensure_dirs

_lock = threading.Lock()
_initialized = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS packets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL,
    host TEXT NOT NULL,
    unique_key TEXT NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    raw_packet TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_packets_host ON packets(host);
CREATE INDEX IF NOT EXISTS idx_packets_unique_key ON packets(unique_key);
CREATE INDEX IF NOT EXISTS idx_packets_captured_at ON packets(captured_at);
CREATE INDEX IF NOT EXISTS idx_packets_host_time ON packets(host, captured_at);
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    domains TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at);
"""


def connect() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db() -> None:
    global _initialized
    with _lock:
        conn = connect()
        try:
            if not _initialized:
                conn.executescript(SCHEMA)
            _migrate(conn)
            conn.commit()
        finally:
            conn.close()
        _initialized = True


def _migrate(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(packets)")}
    if "key_label" not in columns:
        conn.execute("ALTER TABLE packets ADD COLUMN key_label TEXT")


def insert_packet(
    captured_at: str,
    host: str,
    unique_key: str,
    method: str,
    path: str,
    raw_packet: str,
    key_label: str | None = None,
) -> int:
    init_db()
    with _lock:
        conn = connect()
        try:
            cur = conn.execute(
                """
                INSERT INTO packets (captured_at, host, unique_key, method, path, raw_packet, key_label)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (captured_at, host, unique_key, method, path, raw_packet, key_label),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()


def _project_host_filter(project_id: int) -> tuple[str, list[Any]]:
    init_db()
    conn = connect()
    try:
        row = conn.execute("SELECT domains FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not row:
            return "1=0", []
        domains = json.loads(row["domains"])
        return host_match_sql(domains)
    finally:
        conn.close()


def _where(
    host: str | None,
    start: str | None,
    end: str | None,
    unique_key: str | None = None,
    project_id: int | None = None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    args: list[Any] = []
    if project_id:
        project_clause, project_args = _project_host_filter(project_id)
        clauses.append(f"({project_clause})")
        args.extend(project_args)
    if host:
        clauses.append("host = ?")
        args.append(host)
    if start:
        clauses.append("captured_at >= ?")
        args.append(start)
    if end:
        clauses.append("captured_at <= ?")
        args.append(end)
    if unique_key:
        clauses.append("unique_key = ?")
        args.append(unique_key)
    sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return sql, args


def list_unique_keys(
    host: str | None,
    start: str | None,
    end: str | None,
    page: int,
    page_size: int,
    project_id: int | None = None,
) -> dict[str, Any]:
    init_db()
    where, args = _where(host, start, end, project_id=project_id)
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size
    conn = connect()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM (SELECT 1 FROM packets{where} GROUP BY unique_key, host)",
            args,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT unique_key,
                   COALESCE(MAX(key_label), unique_key) AS key_label,
                   host,
                   MIN(captured_at) AS first_seen,
                   MAX(captured_at) AS last_seen,
                   COUNT(*) AS hit_count
            FROM packets
            {where}
            GROUP BY unique_key, host
            ORDER BY last_seen DESC
            LIMIT ? OFFSET ?
            """,
            [*args, page_size, offset],
        ).fetchall()
        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "items": [dict(row) for row in rows],
        }
    finally:
        conn.close()


def list_raw_packets(
    unique_key: str,
    host: str | None,
    start: str | None,
    end: str | None,
    page: int,
    page_size: int,
    project_id: int | None = None,
) -> dict[str, Any]:
    init_db()
    where, args = _where(host, start, end, unique_key=unique_key, project_id=project_id)
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size
    conn = connect()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM (SELECT 1 FROM packets{where} GROUP BY host, raw_packet)",
            args,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT MAX(id) AS id,
                   MIN(captured_at) AS first_seen,
                   MAX(captured_at) AS captured_at,
                   host,
                   unique_key,
                   COALESCE(MAX(key_label), unique_key) AS key_label,
                   method,
                   path,
                   raw_packet,
                   COUNT(*) AS hit_count
            FROM packets
            {where}
            GROUP BY host, raw_packet
            ORDER BY captured_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [*args, page_size, offset],
        ).fetchall()
        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "items": [dict(row) for row in rows],
        }
    finally:
        conn.close()


def list_hosts(project_id: int | None = None) -> list[str]:
    init_db()
    where, args = _where(None, None, None, project_id=project_id)
    conn = connect()
    try:
        rows = conn.execute(
            f"SELECT host, COUNT(*) AS n FROM packets{where} GROUP BY host ORDER BY n DESC",
            args,
        ).fetchall()
        return [row["host"] for row in rows]
    finally:
        conn.close()


def stats() -> dict[str, Any]:
    init_db()
    conn = connect()
    try:
        packet_count = conn.execute("SELECT COUNT(*) FROM packets").fetchone()[0]
        unique_count = conn.execute(
            "SELECT COUNT(*) FROM (SELECT 1 FROM packets GROUP BY unique_key, host)"
        ).fetchone()[0]
        host_count = conn.execute("SELECT COUNT(DISTINCT host) FROM packets").fetchone()[0]
        latest = conn.execute("SELECT MAX(captured_at) FROM packets").fetchone()[0]
        return {
            "packet_count": packet_count,
            "unique_key_count": unique_count,
            "host_count": host_count,
            "latest_captured_at": latest,
        }
    finally:
        conn.close()


def _endpoint_filters(
    *,
    host: str | None = None,
    start: str | None = None,
    end: str | None = None,
    project_id: int | None = None,
    method: str | None = None,
    path_contains: str | None = None,
    q: str | None = None,
    since: str | None = None,
) -> tuple[str, list[Any], str]:
    where, args = _where(host, start, end, project_id=project_id)
    if method:
        where += (" AND " if where else " WHERE ") + "method = ?"
        args.append(method.upper())
    if path_contains:
        where += (" AND " if where else " WHERE ") + "path LIKE ?"
        args.append(f"%{path_contains}%")
    if q:
        where += (" AND " if where else " WHERE ") + (
            "(path LIKE ? OR host LIKE ? OR COALESCE(key_label, unique_key) LIKE ?)"
        )
        pattern = f"%{q}%"
        args.extend([pattern, pattern, pattern])
    having = ""
    if since:
        having = " HAVING MIN(captured_at) >= ?"
        args.append(since)
    return where, args, having


def _sort_clause(sort: str) -> str:
    mapping = {
        "last_seen": "last_seen DESC",
        "first_seen": "first_seen ASC",
        "hit_count": "hit_count DESC",
    }
    return mapping.get(sort or "last_seen", "last_seen DESC")


def list_endpoint_groups(
    *,
    host: str | None = None,
    method: str | None = None,
    path_contains: str | None = None,
    q: str | None = None,
    since: str | None = None,
    project_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    sort: str = "last_seen",
) -> tuple[list[sqlite3.Row], int]:
    init_db()
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size
    where, args, having = _endpoint_filters(
        host=host,
        project_id=project_id,
        method=method,
        path_contains=path_contains,
        q=q,
        since=since,
    )
    conn = connect()
    try:
        base = f"""
            FROM packets
            {where}
            GROUP BY unique_key, host, method, path
            {having}
        """
        total = conn.execute(
            f"SELECT COUNT(*) FROM (SELECT 1 {base})",
            args,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT unique_key,
                   COALESCE(MAX(key_label), unique_key) AS key_label,
                   host,
                   method,
                   path,
                   MIN(captured_at) AS first_seen,
                   MAX(captured_at) AS last_seen,
                   COUNT(*) AS hit_count
            {base}
            ORDER BY {_sort_clause(sort)}
            LIMIT ? OFFSET ?
            """,
            [*args, page_size, offset],
        ).fetchall()
        return rows, int(total)
    finally:
        conn.close()


def list_endpoint_groups_all(
    *,
    project_id: int | None = None,
    host: str | None = None,
) -> list[dict[str, Any]]:
    init_db()
    where, args, having = _endpoint_filters(host=host, project_id=project_id)
    conn = connect()
    try:
        rows = conn.execute(
            f"""
            SELECT unique_key,
                   COALESCE(MAX(key_label), unique_key) AS key_label,
                   host,
                   method,
                   path,
                   MIN(captured_at) AS first_seen,
                   MAX(captured_at) AS last_seen,
                   COUNT(*) AS hit_count
            FROM packets
            {where}
            GROUP BY unique_key, host, method, path
            {having}
            ORDER BY host ASC, method ASC, path ASC
            """,
            args,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_endpoint_group(
    fingerprint: str,
    host: str,
    *,
    project_id: int | None = None,
) -> sqlite3.Row | None:
    init_db()
    where, args, having = _endpoint_filters(
        host=host,
        project_id=project_id,
    )
    where += (" AND " if where else " WHERE ") + "unique_key = ?"
    args.append(fingerprint)
    conn = connect()
    try:
        row = conn.execute(
            f"""
            SELECT unique_key,
                   COALESCE(MAX(key_label), unique_key) AS key_label,
                   host,
                   method,
                   path,
                   MIN(captured_at) AS first_seen,
                   MAX(captured_at) AS last_seen,
                   COUNT(*) AS hit_count
            FROM packets
            {where}
            GROUP BY unique_key, host, method, path
            {having}
            LIMIT 1
            """,
            args,
        ).fetchone()
        return row
    finally:
        conn.close()


def get_endpoint_sample_packet(
    fingerprint: str,
    host: str,
    *,
    project_id: int | None = None,
) -> dict[str, Any] | None:
    init_db()
    where, args = _where(host, None, None, unique_key=fingerprint, project_id=project_id)
    conn = connect()
    try:
        row = conn.execute(
            f"""
            SELECT id, captured_at, raw_packet
            FROM packets
            {where}
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """,
            args,
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
