#!/usr/bin/env bash
# 部署肯耐珂萨销售陌拜工作台到 101.201.237.149:8877
# 用法: SSHPASS='xxx' ./scripts/deploy.sh
# 也可复用 grape-schedule 的密钥: SSHPASS="$(cat ../grape-schedule/.deploy.secret)" ./scripts/deploy.sh
set -euo pipefail

HOST="${DEPLOY_HOST:-101.201.237.149}"
USER="${DEPLOY_USER:-root}"
REMOTE_DIR="${DEPLOY_DIR:-/opt/knx-outreach}"
PORT="${DEPLOY_PORT:-8877}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ -z "${SSHPASS:-}" ]]; then
  echo "请设置环境变量 SSHPASS=服务器密码"
  exit 1
fi

RSYNC=(sshpass -e rsync -avz -e "ssh -o StrictHostKeyChecking=accept-new")
SSH=(sshpass -e ssh -o StrictHostKeyChecking=accept-new)

# 数据兼容性约定（务必遵守）：
# 1) 永不覆盖远端 data/ 与 .env —— 线上 leads/outreach/wechat_todos 等业务数据在这里
# 2) 启动时 seed_all() 仅在无 .seeded 时写入演示数据；线上已有 .seeded 不会被重置
# 3) 代码改动应对旧 JSON 字段用 .get(默认值)；禁止把「缺字段」当成错误直接 500
# 4) 不要在生产调用 POST /api/seed/reset（会清空并重建演示数据）
# 5) 若变更 JSON 结构（改名/改类型/必填新字段），先做只读兼容或一次性迁移脚本再发布
echo "==> 同步代码到 ${REMOTE_DIR}（保留远端 .env / data / .venv）…"
"${RSYNC[@]}" \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.git' \
  --exclude '.env' \
  --exclude 'data/' \
  --exclude 'data/**' \
  --exclude 'ppt/' \
  --exclude '*.pptx' \
  --exclude '*.ppt' \
  --exclude '*.pdf' \
  --exclude 'HR服务陌拜自动化系统设计.md' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude '._*' \
  --exclude 'server.log' \
  --exclude 'server.pid' \
  --exclude '.cursor' \
  --exclude '.deploy.secret' \
  --exclude '*.tgz' \
  "${ROOT}/" "${USER}@${HOST}:${REMOTE_DIR}/"

echo "==> 远程安装依赖并重启服务…"
"${SSH[@]}" "${USER}@${HOST}" "bash -s" <<EOF
set -e
cd ${REMOTE_DIR}

# 确保监听地址适合公网访问（不覆盖已有密钥等配置）
if [[ -f .env ]]; then
  grep -q '^HOST=' .env && sed -i 's/^HOST=.*/HOST=0.0.0.0/' .env || echo 'HOST=0.0.0.0' >> .env
  grep -q '^PORT=' .env && sed -i "s/^PORT=.*/PORT=${PORT}/" .env || echo "PORT=${PORT}" >> .env
else
  echo "缺少 ${REMOTE_DIR}/.env，请先在服务器上配置密钥"
  exit 1
fi

python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt

# 写入/更新 systemd，避免仅靠手工 nohup
cat > /etc/systemd/system/knx-outreach.service <<UNIT
[Unit]
Description=KNX Sales Outreach Workbench
After=network.target

[Service]
Type=simple
WorkingDirectory=${REMOTE_DIR}
EnvironmentFile=${REMOTE_DIR}/.env
ExecStart=${REMOTE_DIR}/.venv/bin/python -c 'import uvicorn; uvicorn.run("backend.main:app", host="0.0.0.0", port=${PORT}, workers=1)'
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

# 停掉旧的手工进程（若有）
if [[ -f server.pid ]]; then
  old=\$(cat server.pid || true)
  if [[ -n "\$old" ]] && kill -0 "\$old" 2>/dev/null; then
    kill "\$old" 2>/dev/null || true
    sleep 1
  fi
  rm -f server.pid
fi
# 兜底：按端口杀残留
fuser -k ${PORT}/tcp 2>/dev/null || true
sleep 1

systemctl daemon-reload
systemctl enable knx-outreach >/dev/null
systemctl restart knx-outreach
sleep 2
systemctl --no-pager --full status knx-outreach | head -16
curl -sf http://127.0.0.1:${PORT}/api/health
echo
echo "线上: http://${HOST}:${PORT}/"
EOF
