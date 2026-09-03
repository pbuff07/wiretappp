from __future__ import annotations


def normalize_domain_pattern(raw: str) -> str:
    text = raw.strip().lower()
    for prefix in ("https://", "http://"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    text = text.split("/")[0].split(":")[0]
    return text.rstrip(".")


def host_matches_pattern(host: str, pattern: str) -> bool:
    host = host.lower().strip().rstrip(".")
    pattern = normalize_domain_pattern(pattern)
    if not host or not pattern:
        return False
    if pattern.startswith("*."):
        base = pattern[2:]
        return host == base or host.endswith("." + base)
    labels = pattern.split(".")
    if len(labels) == 2:
        return host == pattern or host.endswith("." + pattern)
    return host == pattern


def host_matches_any(host: str, patterns: list[str]) -> bool:
    return any(host_matches_pattern(host, p) for p in patterns)


def host_match_sql(patterns: list[str]) -> tuple[str, list[str]]:
    if not patterns:
        return "1=0", []
    parts: list[str] = []
    args: list[str] = []
    for raw in patterns:
        pattern = normalize_domain_pattern(raw)
        if not pattern:
            continue
        if pattern.startswith("*."):
            base = pattern[2:]
            parts.append("(host = ? OR host LIKE ?)")
            args.extend([base, f"%.{base}"])
        elif len(pattern.split(".")) == 2:
            parts.append("(host = ? OR host LIKE ?)")
            args.extend([pattern, f"%.{pattern}"])
        else:
            parts.append("host = ?")
            args.append(pattern)
    if not parts:
        return "1=0", []
    return "(" + " OR ".join(parts) + ")", args
