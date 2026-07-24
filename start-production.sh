#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
RUNTIME_DIR="$ROOT_DIR/.runtime"
BACKEND_LOG_DIR="$RUNTIME_DIR/logs/server"

if [[ ! -x "$VENV_DIR/bin/uvicorn" || ! -x "$ROOT_DIR/web/node_modules/.bin/vite" ]]; then
  echo "错误：后端依赖尚未安装，请先运行 ./setup-linux.sh" >&2
  exit 1
fi

mkdir -p "$BACKEND_LOG_DIR"
(cd "$ROOT_DIR/web" && corepack pnpm run build)

cleanup() {
  trap - EXIT INT TERM
  [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd "$ROOT_DIR/server"
  exec "$VENV_DIR/bin/uvicorn" app.production:app --host 0.0.0.0 --port 5889
) >>"$BACKEND_LOG_DIR/uvicorn.out.log" 2>>"$BACKEND_LOG_DIR/uvicorn.err.log" &
BACKEND_PID=$!

echo "生产前端：http://127.0.0.1:5889"
echo "后端文档：http://127.0.0.1:5889/docs"
wait "$BACKEND_PID"
