from __future__ import annotations

import sys
import traceback
from pathlib import Path
from urllib.parse import urlsplit

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.config import load_config
from backend.database import insert_packet
from backend.paths import PAUSE_FLAG
from backend.static_filter import is_static_path
from backend.timeutil import (
    format_http_message,
    format_raw_packet,
    message_body,
    now_cst_iso,
    storage_headers,
)
from backend.unique_key import fingerprint_from_request


def _log(message: str) -> None:
    try:
        path = _ROOT / "logs" / "capture.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(message.rstrip() + "\n")
    except Exception:
        return


def is_paused() -> bool:
    return PAUSE_FLAG.exists()


def _decode(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _header_map(headers) -> list[tuple[str, str]]:
    fields = getattr(headers, "fields", None)
    if fields is not None:
        return [(_decode(k), _decode(v)) for k, v in fields]
    return [(_decode(k), _decode(v)) for k, v in headers.items()]


def _should_skip(flow) -> bool:
    req = flow.request
    if req.method.upper() == "CONNECT":
        return True
    cfg = load_config()
    host = (req.host or "").lower()
    if host in {"127.0.0.1", "localhost", "::1"} and req.port == int(cfg["api_port"]):
        return True
    path = urlsplit(req.path).path or req.path.split("?", 1)[0]
    if is_static_path(path, cfg["static_suffixes"]):
        return True
    return False


def capture_flow(flow) -> None:
    if is_paused() or _should_skip(flow):
        return

    cfg = load_config()
    req = flow.request
    max_body = int(cfg["max_body_bytes"])
    req_body, _ = message_body(req, max_body)
    content_type = _decode(req.headers.get("content-type", "") or "")
    path = urlsplit(req.path).path or "/"
    unique_key, key_label = fingerprint_from_request(
        method=req.method,
        url=req.pretty_url,
        path=path,
        query=urlsplit(req.path).query or urlsplit(req.pretty_url).query,
        content_type=content_type,
        body=req_body,
    )
    host_header = _decode(req.headers.get("host", "") or "").strip()
    host = (host_header or req.pretty_host or req.host or "").lower()
    http_version = req.http_version or "HTTP/1.1"
    request_line = f"{req.method} {req.path} {http_version}"
    req_headers = _header_map(req.headers)
    request_text = format_http_message(
        request_line,
        storage_headers(req_headers, req_body),
        req_body,
    )

    response_text = None
    if flow.response is not None:
        resp = flow.response
        resp_body, _ = message_body(resp, max_body)
        reason = resp.reason or ""
        status_line = f"{resp.http_version or http_version} {resp.status_code} {reason}".rstrip()
        resp_headers = _header_map(resp.headers)
        response_text = format_http_message(
            status_line,
            storage_headers(resp_headers, resp_body),
            resp_body,
        )

    insert_packet(
        captured_at=now_cst_iso(),
        host=host,
        unique_key=unique_key,
        method=req.method.upper(),
        path=path,
        raw_packet=format_raw_packet(request_text, response_text),
        key_label=key_label,
    )
    _log(f"stored {host} {key_label} [{unique_key}]")


class CaptureAddon:
    def load(self, _loader) -> None:
        _log("capture addon loaded")

    def running(self) -> None:
        _log("capture addon running")

    def response(self, flow) -> None:
        try:
            capture_flow(flow)
        except Exception:
            _log(traceback.format_exc())

    def error(self, flow) -> None:
        try:
            if flow.response is None:
                capture_flow(flow)
        except Exception:
            _log(traceback.format_exc())


addons = [CaptureAddon()]
_log("capture_addon module imported")
