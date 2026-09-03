#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v go >/dev/null 2>&1; then
  echo "[mcp] error: Go 未安装，无法编译 wiretappp-mcp（需要 Go 1.22+）" >&2
  exit 1
fi

export GOPROXY="${GOPROXY:-https://goproxy.cn,direct}"
echo "[mcp] building wiretappp-mcp ..."
go build -o wiretappp-mcp .

stderr="$(mktemp)"
./wiretappp-mcp 2>"$stderr" & pid=$!
sleep 0.5
if grep -qi 'panic\|missing input schema' "$stderr" 2>/dev/null; then
  cat "$stderr" >&2
  kill "$pid" 2>/dev/null || true
  rm -f "$stderr"
  echo "[mcp] error: wiretappp-mcp 启动自检失败（可能缺少 InputSchema）" >&2
  exit 1
fi
kill "$pid" 2>/dev/null || true
wait "$pid" 2>/dev/null || true
rm -f "$stderr"

echo "[mcp] ok: $ROOT/wiretappp-mcp"
