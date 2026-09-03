from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

TZ_CST = timezone(timedelta(hours=8))


def now_cst() -> datetime:
    return datetime.now(TZ_CST)


def now_cst_iso() -> str:
    return now_cst().isoformat(timespec="seconds")


def parse_query_time(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    else:
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_CST)
    return dt.astimezone(TZ_CST).isoformat(timespec="seconds")


def decode_body(raw: bytes | None, max_bytes: int) -> tuple[str, bool]:
    if not raw:
        return "", False
    truncated = len(raw) > max_bytes
    chunk = raw[:max_bytes]
    try:
        text = chunk.decode("utf-8")
    except UnicodeDecodeError:
        text = chunk.decode("utf-8", errors="replace")
    if truncated:
        text += f"\n\n[truncated {len(raw) - max_bytes} bytes]"
    return text, truncated


def message_body(message, max_bytes: int) -> tuple[str, bool]:
    """Return decoded message body (gzip/br 等已解压)."""
    data = getattr(message, "content", None)
    if data is None:
        data = getattr(message, "raw_content", None) or b""
    return decode_body(data, max_bytes)


def storage_headers(
    headers: list[tuple[str, str]],
    body: str,
) -> list[tuple[str, str]]:
    """存储展示用头：去掉压缩相关字段，修正 Content-Length。"""
    drop = {"content-encoding", "transfer-encoding"}
    kept: list[tuple[str, str]] = []
    for name, value in headers:
        if name.lower() in drop:
            continue
        if name.lower() == "content-length":
            continue
        kept.append((name, value))
    if body:
        kept.append(("Content-Length", str(len(body.encode("utf-8")))))
    return kept


def format_http_message(
    start_line: str,
    headers: list[tuple[str, str]] | Any,
    body: str,
) -> str:
    lines = [start_line]
    for name, value in headers:
        lines.append(f"{name}: {value}")
    lines.append("")
    if body:
        lines.append(body)
    return "\r\n".join(lines)


def format_raw_packet(request_text: str, response_text: str | None) -> str:
    parts = ["===== REQUEST =====", request_text.rstrip()]
    if response_text:
        parts.extend(["", "===== RESPONSE =====", response_text.rstrip()])
    return "\n".join(parts) + "\n"
