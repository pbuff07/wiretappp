from __future__ import annotations

import re
from collections import Counter

STATUS_LINE = re.compile(r"^HTTP/\d(?:\.\d)?\s+(\d{3})\b", re.MULTILINE)
CONTENT_TYPE = re.compile(r"^Content-Type:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
HEADER_LINE = re.compile(r"^([A-Za-z0-9-]+):\s*(.*)$")

AUTH_HEADER_NAMES = frozenset(
    {
        "authorization",
        "cookie",
        "x-api-key",
        "x-auth-token",
        "x-access-token",
        "x-csrf-token",
    }
)


def parse_key_label(label: str) -> tuple[list[str], list[str]]:
    url_names: list[str] = []
    body_names: list[str] = []
    if not label:
        return url_names, body_names
    url_match = re.search(r" · url\(([^)]*)\) · ", label)
    if url_match:
        raw = url_match.group(1).strip()
        if raw and raw != "-":
            url_names = [p.strip() for p in raw.split(",") if p.strip()]
    body_match = re.search(r" · body\(([^)]*)\)\s*$", label)
    if body_match:
        raw = body_match.group(1).strip()
        if raw and raw != "-":
            body_names = [p.strip() for p in raw.split(",") if p.strip()]
    return url_names, body_names


def extract_status_codes(raw_packet: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for match in STATUS_LINE.finditer(raw_packet or ""):
        counts[match.group(1)] += 1
    return dict(counts)


def extract_content_types(raw_packet: str) -> list[str]:
    seen: set[str] = set()
    types: list[str] = []
    for match in CONTENT_TYPE.finditer(raw_packet or ""):
        value = match.group(1).split(";")[0].strip().lower()
        if value and value not in seen:
            seen.add(value)
            types.append(value)
    return types


def extract_auth_hints(raw_packet: str) -> list[str]:
    hints: list[str] = []
    seen: set[str] = set()
    request_part = (raw_packet or "").split("===== RESPONSE =====")[0]
    for line in request_part.splitlines():
        if line.startswith("===== "):
            continue
        match = HEADER_LINE.match(line)
        if not match:
            continue
        name = match.group(1).lower()
        if name in AUTH_HEADER_NAMES and name not in seen:
            seen.add(name)
            hints.append(match.group(1))
    return hints


def split_request_response(raw_packet: str) -> tuple[str, str | None]:
    if "===== RESPONSE =====" not in (raw_packet or ""):
        return raw_packet or "", None
    req, resp = raw_packet.split("===== RESPONSE =====", 1)
    req = req.replace("===== REQUEST =====", "", 1).strip()
    return req.strip(), resp.strip()
