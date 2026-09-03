from __future__ import annotations

import socket


def list_lan_addresses() -> list[str]:
    addrs: set[str] = set()
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        addrs.add(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                addrs.add(ip)
    except OSError:
        pass

    return sorted(addrs)


def api_urls(host: str, port: int) -> dict[str, list[str] | str]:
    local = f"http://127.0.0.1:{port}"
    lan = [f"http://{ip}:{port}" for ip in list_lan_addresses()]
    return {
        "local_url": local,
        "lan_urls": lan,
        "bind_host": host,
        "port": port,
    }
