from __future__ import annotations

import hashlib
import json
from urllib.parse import parse_qsl, urlparse


def _sorted_keys(keys: list[str] | set[str]) -> str:
    return ",".join(sorted({k for k in keys if k}))


def extract_url_keys(url: str, query: str | None = None) -> list[str]:
    if query is None:
        parsed = urlparse(url)
        query = parsed.query
    return [k for k, _ in parse_qsl(query or "", keep_blank_values=True)]


def extract_body_keys(content_type: str | None, body: str | bytes | None) -> list[str]:
    if body is None or body == b"" or body == "":
        return []
    if isinstance(body, bytes):
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            return []
    else:
        text = body
    if not text.strip():
        return []

    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype in {"application/json", "text/json", "application/ld+json"}:
        return _json_keys(text)
    if ctype in {"application/x-www-form-urlencoded", "text/plain"}:
        if ctype == "text/plain" and "=" not in text and "&" not in text:
            return []
        return [k for k, _ in parse_qsl(text, keep_blank_values=True)]
    if "json" in ctype:
        return _json_keys(text)
    if "=" in text and "&" in text:
        return [k for k, _ in parse_qsl(text, keep_blank_values=True)]
    return []


def _json_keys(text: str) -> list[str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        return [str(k) for k in payload.keys()]
    return []


def build_unique_key(
    method: str,
    path: str,
    url_keys: list[str],
    body_keys: list[str],
) -> str:
    """Legacy canonical string used as MD5 input."""
    method_part = (method or "GET").upper().strip()
    path_part = path or "/"
    return (
        f"{method_part} @$ {path_part} @$ "
        f"url_para_{_sorted_keys(url_keys)} @$ "
        f"body_para_{_sorted_keys(body_keys)}"
    )


def format_key_label(
    method: str,
    path: str,
    url_keys: list[str],
    body_keys: list[str],
) -> str:
    method_part = (method or "GET").upper().strip()
    path_part = path or "/"
    url_part = _sorted_keys(url_keys) or "-"
    body_part = _sorted_keys(body_keys) or "-"
    return f"{method_part} {path_part} · url({url_part}) · body({body_part})"


def build_fingerprint(
    method: str,
    path: str,
    url_keys: list[str],
    body_keys: list[str],
) -> tuple[str, str]:
    canonical = build_unique_key(method, path, url_keys, body_keys)
    digest = hashlib.md5(canonical.encode("utf-8")).hexdigest()
    label = format_key_label(method, path, url_keys, body_keys)
    return digest, label


def fingerprint_from_request(
    method: str,
    url: str,
    path: str | None = None,
    query: str | None = None,
    content_type: str | None = None,
    body: str | bytes | None = None,
) -> tuple[str, str]:
    parsed = urlparse(url)
    request_path = path if path is not None else (parsed.path or "/")
    url_keys = extract_url_keys(url, query=query if query is not None else parsed.query)
    body_keys = extract_body_keys(content_type, body)
    return build_fingerprint(method, request_path, url_keys, body_keys)


def unique_key_from_request(
    method: str,
    url: str,
    path: str | None = None,
    query: str | None = None,
    content_type: str | None = None,
    body: str | bytes | None = None,
) -> str:
    digest, _ = fingerprint_from_request(
        method=method,
        url=url,
        path=path,
        query=query,
        content_type=content_type,
        body=body,
    )
    return digest
