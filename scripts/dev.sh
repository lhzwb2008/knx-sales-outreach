#!/usr/bin/env bash
# 本地启动陌拜工作台：http://127.0.0.1:8765/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -r requirements.txt
else
  . .venv/bin/activate
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "已创建 .env，如需智能助手请填入 DASHSCOPE_API_KEY"
fi

# 释放残留占用
if lsof -iTCP:8765 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "8765 已被占用，先停止旧进程…"
  if [[ -f server.pid ]]; then
    kill "$(cat server.pid)" 2>/dev/null || true
    sleep 1
  fi
  # 兜底
  lsof -tiTCP:8765 -sTCP:LISTEN | xargs kill 2>/dev/null || true
  sleep 1
fi

echo "启动中 → http://127.0.0.1:8765/"
echo "（热重载：RELOAD=1 ./scripts/dev.sh）"
export RELOAD="${RELOAD:-0}"
exec python run.py
