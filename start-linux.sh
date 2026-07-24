#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
BACKEND_LOG_DIR="$ROOT_DIR/.runtime/logs/server"
FRONTEND_LOG_DIR="$ROOT_DIR/.runtime/logs/web"

if [[ ! -x "$VENV_DIR/bin/uvicorn" || ! -x "$ROOT_DIR/web/node_modules/.bin/vite" ]]; then
  echo "错误：开发依赖尚未安装，请先运行 ./setup-linux.sh" >&2
  exit 1
fi

mkdir -p "$BACKEND_LOG_DIR" "$FRONTEND_LOG_DIR"

cleanup() {
  trap - EXIT INT TERM
  [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd "$ROOT_DIR/server"
  exec "$VENV_DIR/bin/uvicorn" app.main:app --reload --host 127.0.0.1 --port 8000
) > >(tee -a "$BACKEND_LOG_DIR/uvicorn.out.log") \
  2> >(tee -a "$BACKEND_LOG_DIR/uvicorn.err.log" >&2) &
BACKEND_PID=$!

(
  cd "$ROOT_DIR/web"
  exec corepack pnpm run dev --host 0.0.0.0 --port 5889
) > >(tee -a "$FRONTEND_LOG_DIR/vite.out.log") \
  2> >(tee -a "$FRONTEND_LOG_DIR/vite.err.log" >&2) &
FRONTEND_PID=$!

echo "前端：http://127.0.0.1:5889"
echo "后端文档：http://127.0.0.1:8000/docs"
echo "按 Ctrl+C 停止全部服务。"

wait -n "$BACKEND_PID" "$FRONTEND_PID"
