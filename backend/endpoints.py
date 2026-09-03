from __future__ import annotations

from typing import Any

from backend import database, projects
from backend.config import load_config
from backend.packet_parse import (
    extract_auth_hints,
    extract_content_types,
    extract_status_codes,
    parse_key_label,
)
from backend.redact import redact_packet_text


def _enrich_row(row: dict[str, Any]) -> dict[str, Any]:
    label = row.get("key_label") or row.get("unique_key") or ""
    url_names, body_names = parse_key_label(label)
    item = {
        "fingerprint": row["unique_key"],
        "unique_key": row["unique_key"],
        "key_label": label,
        "host": row["host"],
        "method": row["method"],
        "path": row["path"],
        "url_param_names": url_names,
        "body_param_names": body_names,
        "first_seen": row["first_seen"],
        "last_seen": row["last_seen"],
        "hit_count": row["hit_count"],
    }
    return item


def list_endpoints(
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
) -> dict[str, Any]:
    rows, total = database.list_endpoint_groups(
        host=host,
        method=method,
        path_contains=path_contains,
        q=q,
        since=since,
        project_id=project_id,
        page=page,
        page_size=page_size,
        sort=sort,
    )
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": [_enrich_row(dict(row)) for row in rows],
    }


def list_new_endpoints(
    *,
    since: str,
    project_id: int | None = None,
    host: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    result = list_endpoints(
        host=host,
        since=since,
        project_id=project_id,
        page=page,
        page_size=page_size,
        sort="first_seen",
    )
    result["since"] = since
    return result


def describe_endpoint(
    fingerprint: str,
    host: str,
    *,
    project_id: int | None = None,
    include_raw: bool = False,
) -> dict[str, Any] | None:
    group = database.get_endpoint_group(fingerprint, host, project_id=project_id)
    if not group:
        return None

    sample = database.get_endpoint_sample_packet(fingerprint, host, project_id=project_id)
    item = _enrich_row(dict(group))
    item["status_codes"] = {}
    item["content_types"] = []
    item["auth_headers"] = []

    if sample and sample.get("raw_packet"):
        raw = sample["raw_packet"]
        item["status_codes"] = extract_status_codes(raw)
        item["content_types"] = extract_content_types(raw)
        item["auth_headers"] = extract_auth_hints(raw)
        cfg = load_config()
        max_body = min(int(cfg.get("max_body_bytes", 524288)), 2048)
        item["sample"] = {
            "captured_at": sample.get("captured_at"),
            "packet_id": sample.get("id"),
            "redacted_packet": redact_packet_text(raw, max_body_chars=max_body),
        }
        if include_raw:
            item["sample"]["raw_packet"] = raw
    else:
        item["sample"] = None

    return item


def build_sitemap(*, project_id: int | None = None, host: str | None = None) -> dict[str, Any]:
    rows = database.list_endpoint_groups_all(
        project_id=project_id,
        host=host,
    )
    tree: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in rows:
        h = row["host"]
        m = (row["method"] or "GET").upper()
        tree.setdefault(h, {})
        tree[h].setdefault(m, [])
        entry = {
            "path": row["path"],
            "fingerprint": row["unique_key"],
            "key_label": row.get("key_label") or row["unique_key"],
            "hit_count": row["hit_count"],
        }
        paths = tree[h][m]
        if not any(p["path"] == entry["path"] and p["fingerprint"] == entry["fingerprint"] for p in paths):
            paths.append(entry)

    for h in tree:
        for m in tree[h]:
            tree[h][m].sort(key=lambda x: (-x["hit_count"], x["path"]))

    hosts_sorted = sorted(tree.keys())
    return {
        "project_id": project_id,
        "host_filter": host,
        "host_count": len(hosts_sorted),
        "endpoint_count": len(rows),
        "hosts": {h: tree[h] for h in hosts_sorted},
    }


def recon_project(project_id: int, *, since: str | None = None, top: int = 20) -> dict[str, Any] | None:
    detail = projects.get_project_detail(project_id)
    if detail is None:
        return None

    hosts = projects.list_project_hosts(project_id)
    sitemap = build_sitemap(project_id=project_id)
    endpoints = list_endpoints(
        project_id=project_id, page=1, page_size=min(top, 100), sort="hit_count"
    )

    new_endpoints = None
    if since:
        new_endpoints = list_new_endpoints(since=since, project_id=project_id, page=1, page_size=min(top, 100))

    return {
        "project": detail,
        "hosts": hosts,
        "sitemap_summary": {
            "host_count": sitemap["host_count"],
            "endpoint_count": sitemap["endpoint_count"],
            "hosts": list(sitemap["hosts"].keys()),
        },
        "top_endpoints": endpoints["items"][:top],
        "new_endpoints_since": since,
        "new_endpoints": new_endpoints["items"][:top] if new_endpoints else None,
    }
