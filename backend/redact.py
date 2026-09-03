from __future__ import annotations

import re

SENSITIVE_HEADER_NAMES = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-auth-token",
        "x-access-token",
        "x-csrf-token",
        "proxy-authorization",
    }
)

JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
BEARER_PATTERN = re.compile(r"(Bearer\s+)(\S+)", re.IGNORECASE)


def redact_header_value(name: str, value: str) -> str:
    lower = name.lower()
    if lower in SENSITIVE_HEADER_NAMES:
        return "[REDACTED]"
    if lower == "authorization":
        return BEARER_PATTERN.sub(r"\1[REDACTED]", value)
    if JWT_PATTERN.search(value):
        return JWT_PATTERN.sub("[REDACTED_JWT]", value)
    return value


def redact_packet_text(text: str, *, max_body_chars: int = 2048) -> str:
    if not text:
        return ""
    if "===== RESPONSE =====" in text:
        req, resp = text.split("===== RESPONSE =====", 1)
        return _redact_section(req, max_body_chars) + "===== RESPONSE =====\n" + _redact_section(
            resp, max_body_chars, skip_banner=True
        )
    return _redact_section(text, max_body_chars)


def _redact_section(section: str, max_body_chars: int, *, skip_banner: bool = False) -> str:
    lines = section.splitlines()
    if not lines:
        return section

    start = 0
    if not skip_banner and lines[0].startswith("===== "):
        start = 1

    header_lines: list[str] = []
    body_start = start
    for i in range(start, len(lines)):
        if lines[i].strip() == "":
            body_start = i + 1
            break
        if ":" in lines[i]:
            name, _, value = lines[i].partition(":")
            header_lines.append(f"{name}:{redact_header_value(name.strip(), value.strip())}")
        else:
            header_lines.append(lines[i])
    else:
        body_start = len(lines)

    body = "\n".join(lines[body_start:])
    if len(body) > max_body_chars:
        body = body[:max_body_chars] + f"\n\n[truncated {len(body) - max_body_chars} chars]"

    prefix = []
    if not skip_banner and start == 1:
        prefix = [lines[0]]
    out = prefix + header_lines
    if body:
        out.append("")
        out.append(body)
    return "\n".join(out) + "\n"
