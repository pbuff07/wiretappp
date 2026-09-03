#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"

VENV="$ROOT/.venv"
RUN="$ROOT/run"
LOG="$ROOT/logs"
MITM_PID="$RUN/mitm.pid"
PAUSE_FLAG="$RUN/paused.flag"

mkdir -p "$RUN" "$LOG" "$ROOT/data"

alive() {
  local pidfile="$1"
  [[ -f "$pidfile" ]] || return 1
  local pid
  pid="$(tr -d '[:space:]' < "$pidfile" 2>/dev/null || true)"
  [[ -n "${pid:-}" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

ensure_venv() {
  if [[ ! -x "$VENV/bin/python" ]]; then
    echo "[manage] creating virtualenv"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -U pip
    "$VENV/bin/pip" install -r "$ROOT/requirements.txt"
  elif [[ ! -x "$VENV/bin/uvicorn" ]]; then
    "$VENV/bin/pip" install -r "$ROOT/requirements.txt"
  fi
}

ensure_frontend() {
  if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
    echo "[manage] installing frontend dependencies"
    (cd "$ROOT/frontend" && npm install)
  fi
}

ensure_desktop() {
  if [[ ! -x "$ROOT/desktop/node_modules/.bin/electron" ]] || [[ ! -x "$ROOT/desktop/node_modules/.bin/electron-builder" ]]; then
    echo "[manage] installing desktop dependencies (electron mirror enabled)"
    rm -rf "$ROOT/desktop/node_modules"
    (
      cd "$ROOT/desktop"
      export ELECTRON_MIRROR="${ELECTRON_MIRROR:-https://npmmirror.com/mirrors/electron/}"
      export ELECTRON_BUILDER_BINARIES_MIRROR="${ELECTRON_BUILDER_BINARIES_MIRROR:-https://npmmirror.com/mirrors/electron-builder-binaries/}"
      if [[ -n "${https_proxy:-}" ]]; then
        npm config set proxy "$http_proxy" --location=project 2>/dev/null || true
        npm config set https-proxy "$https_proxy" --location=project 2>/dev/null || true
      fi
      npm install
    )
  fi
}

cmd_install() {
  ensure_venv
  ensure_frontend
  ensure_desktop
  build_icons
  cmd_mcp
  echo "[manage] dependencies ready"
}

cmd_mcp() {
  if [[ ! -f "$ROOT/mcp/build.sh" ]]; then
    echo "[manage] skip MCP build (mcp/build.sh not found)"
    return 0
  fi
  bash "$ROOT/mcp/build.sh"
}

cmd_dev() {
  cmd_install
  kill_port_listeners "$(read_api_port)"
  kill_port_listeners 5173
  echo "[manage] launching Electron dev (Vite + API auto-start)"
  (cd "$ROOT/desktop" && npm start)
}

kill_pidfile() {
  local pidfile="$1"
  alive "$pidfile" || return 0
  local pid
  pid="$(tr -d '[:space:]' < "$pidfile")"
  kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
  for _ in {1..25}; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.12
  done
  kill -9 -- "-$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
}

read_api_port() {
  local default_port=18760
  local cfg=""
  if [[ -f "$HOME/.wiretappp/config.yaml" ]]; then
    cfg="$HOME/.wiretappp/config.yaml"
  elif [[ -n "${XDG_CONFIG_HOME:-}" && -f "$XDG_CONFIG_HOME/wiretappp/config.yaml" ]]; then
    cfg="$XDG_CONFIG_HOME/wiretappp/config.yaml"
  elif [[ -f "$ROOT/config.yaml" ]]; then
    cfg="$ROOT/config.yaml"
  fi
  if [[ -n "$cfg" ]]; then
    local match
    match="$(grep -E '^[[:space:]]*api_port:[[:space:]]*' "$cfg" | head -1 | awk '{print $2}' | sed "s/['\"]//g")"
    if [[ -n "$match" ]]; then
      echo "$match"
      return
    fi
  fi
  echo "$default_port"
}

detect_platform() {
  case "$(uname -s)" in
    Darwin) echo "mac" ;;
    Linux) echo "linux" ;;
    MINGW*|MSYS*|CYGWIN*) echo "win" ;;
    *) echo "linux" ;;
  esac
}

detect_arch() {
  case "$(uname -m)" in
    arm64|aarch64) echo "arm64" ;;
    x86_64|amd64) echo "x64" ;;
    *) echo "x64" ;;
  esac
}

normalize_platform() {
  local raw
  raw="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$raw" in
    mac|macos|darwin|osx) echo "mac" ;;
    linux) echo "linux" ;;
    win|windows) echo "win" ;;
    *) echo "" ;;
  esac
}

bundle_python_env() {
  local target_platform="$1"
  local target_arch="$2"
  local host_platform host_arch
  host_platform="$(detect_platform)"
  host_arch="$(detect_arch)"

  local out="$ROOT/desktop/build/python-env"
  rm -rf "$out"
  echo "[manage] bundling Python runtime -> desktop/build/python-env"

  if [[ "$target_platform" != "$host_platform" || "$target_arch" != "$host_arch" ]]; then
    echo "[manage] warn: cross-platform Python bundle unsupported on this host"
    echo "[manage] warn: building Electron shell only; install Python deps manually on target OS"
    mkdir -p "$out"
    return 0
  fi

  python3 -m venv "$out"
  "$out/bin/pip" install -U pip
  "$out/bin/pip" install -r "$ROOT/requirements.txt"
}

build_icons() {
  ensure_venv
  if ! "$VENV/bin/python" -c "import PIL" 2>/dev/null; then
    echo "[manage] installing icon build dependency (Pillow)"
    "$VENV/bin/pip" install -q -r "$ROOT/desktop/requirements-icons.txt"
  fi
  echo "[manage] syncing WIRETAPPP logo to app / taskbar / UI"
  "$VENV/bin/python" "$ROOT/desktop/scripts/generate-icons.py"
}

cmd_pack() {
  local platform="" arch="" passthrough=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --platform|-p)
        platform="$(normalize_platform "${2:-}")"
        [[ -n "$platform" ]] || { echo "[manage] unknown platform: $2" >&2; exit 1; }
        shift 2
        ;;
      --arch|-a)
        arch="${2:-}"
        shift 2
        ;;
      --)
        shift
        passthrough+=("$@")
        break
        ;;
      -h|--help)
        cmd_pack_help
        return 0
        ;;
      *)
        passthrough+=("$1")
        shift
        ;;
    esac
  done

  platform="${platform:-$(detect_platform)}"
  arch="${arch:-$(detect_arch)}"

  ensure_frontend
  ensure_desktop
  build_icons

  echo "[manage] building frontend"
  (cd "$ROOT/frontend" && npm run build)

  bundle_python_env "$platform" "$arch"

  local builder_args=(--publish never)
  case "$platform" in
    mac) builder_args+=(--mac) ;;
    linux) builder_args+=(--linux) ;;
    win) builder_args+=(--win) ;;
  esac
  case "$arch" in
    arm64) builder_args+=(--arm64) ;;
    x64|amd64) builder_args+=(--x64) ;;
    *)
      echo "[manage] unsupported arch: $arch (use x64 or arm64)" >&2
      exit 1
      ;;
  esac
  if ((${#passthrough[@]})); then
    builder_args+=("${passthrough[@]}")
  fi

  echo "[manage] packaging WIRETAPPP (${platform}/${arch})"
  (
    cd "$ROOT/desktop"
    export ELECTRON_MIRROR="${ELECTRON_MIRROR:-https://npmmirror.com/mirrors/electron/}"
    export ELECTRON_BUILDER_BINARIES_MIRROR="${ELECTRON_BUILDER_BINARIES_MIRROR:-https://npmmirror.com/mirrors/electron-builder-binaries/}"
    npx electron-builder "${builder_args[@]}"
  )
  echo "[manage] artifacts -> desktop/dist/"
  echo "[manage] user config dir: macOS ~/.wiretappp · Linux \$XDG_CONFIG_HOME/wiretappp · Windows %APPDATA%\\wiretappp"
}

cmd_pack_help() {
  cat <<EOF
Usage: $(basename "$0") pack [options] [-- extra electron-builder args]

  打包 WIRETAPPP 桌面应用（Electron + 内置 Python 后端 + 前端静态资源）

Options:
  -p, --platform <mac|linux|win>   目标平台（默认：当前系统）
  -a, --arch <x64|arm64>           目标架构（默认：当前 CPU）
  -h, --help                       显示帮助

示例:
  ./manage.sh pack
  ./manage.sh pack --platform mac --arch arm64
  ./manage.sh pack --platform win --arch x64

配置与数据目录（打包后）:
  macOS   ~/.wiretappp/config.yaml
  Linux   \$XDG_CONFIG_HOME/wiretappp/config.yaml  (默认 ~/.config/wiretappp)
  Windows %APPDATA%\\wiretappp\\config.yaml

产物输出: desktop/dist/
EOF
}

kill_port_listeners() {
  local port="$1"
  if ! command -v lsof >/dev/null 2>&1; then
    return 0
  fi
  local pids
  pids="$(lsof -ti ":$port" 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi
  echo "[manage] stopping process(es) on port $port: $pids"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  sleep 0.3
  # shellcheck disable=SC2086
  kill -9 $pids 2>/dev/null || true
}

cmd_stop() {
  kill_pidfile "$MITM_PID"
  rm -f "$MITM_PID" "$PAUSE_FLAG"
  kill_port_listeners "$(read_api_port)"
  kill_port_listeners 5173
  echo "[manage] stopped mitm / API / Vite (if any)"
}

usage() {
  cat <<EOF
Usage: $(basename "$0") <command>

  install  安装 Python / 前端 / Electron 依赖，并编译 MCP
  dev      启动 Electron 开发调试（自动拉起 API + Vite）
  pack     打包桌面应用（可选 --platform / --arch）
  mcp      编译 MCP 二进制（mcp/wiretappp-mcp）
  stop     停止 mitm、API（18760）、Vite（5173）

配置目录（优先读取）:
  macOS   ~/.wiretappp/config.yaml
  Linux   \$XDG_CONFIG_HOME/wiretappp/config.yaml
  Windows %APPDATA%\\wiretappp\\config.yaml
EOF
}

case "${1:-}" in
  install) cmd_install ;;
  dev|desktop) cmd_dev ;;
  pack) shift; cmd_pack "$@" ;;
  mcp) cmd_mcp ;;
  stop) cmd_stop ;;
  *)
    usage
    exit 1
    ;;
esac
