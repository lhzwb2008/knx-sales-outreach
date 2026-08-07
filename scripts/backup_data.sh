#!/usr/bin/env bash
# 数据备份：只读复制 data/*.json → 仓库 main 分支根目录 data/ 并 push
# 不加载、不恢复、不依赖主服务进程。失败不影响陌拜工作台。
#
# 环境变量（均可选）:
#   SOURCE_DATA   默认 /opt/knx-outreach/data
#   BACKUP_DIR    默认 /opt/knx-outreach-data-backup（独立 clone，与业务目录分离）
#   BACKUP_REMOTE 默认 git@github.com:lhzwb2008/knx-sales-outreach.git
#   BACKUP_BRANCH 默认 main
set -euo pipefail

SOURCE_DATA="${SOURCE_DATA:-/opt/knx-outreach/data}"
BACKUP_DIR="${BACKUP_DIR:-/opt/knx-outreach-data-backup}"
BACKUP_REMOTE="${BACKUP_REMOTE:-git@github.com:lhzwb2008/knx-sales-outreach.git}"
BACKUP_BRANCH="${BACKUP_BRANCH:-main}"
LOCK_FILE="${LOCK_FILE:-/var/lock/knx-outreach-backup.lock}"

log() { printf '[knx-backup] %s\n' "$*"; }

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log "另一备份正在运行，跳过"
  exit 0
fi

if [[ ! -d "$SOURCE_DATA" ]]; then
  log "源数据目录不存在: $SOURCE_DATA"
  exit 1
fi

export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new}"

ensure_repo() {
  if [[ ! -d "$BACKUP_DIR/.git" ]]; then
    log "首次克隆备份仓库 → $BACKUP_DIR"
    rm -rf "$BACKUP_DIR"
    git clone --branch "$BACKUP_BRANCH" --single-branch "$BACKUP_REMOTE" "$BACKUP_DIR"
  fi
  cd "$BACKUP_DIR"
  git remote set-url origin "$BACKUP_REMOTE"
  git fetch origin "$BACKUP_BRANCH"
  git checkout -B "$BACKUP_BRANCH" "origin/$BACKUP_BRANCH"
  git reset --hard "origin/$BACKUP_BRANCH"
}

sync_data() {
  mkdir -p "$BACKUP_DIR/data"
  # 只同步 JSON，跳过 .seeded / 临时文件
  rsync -a --delete \
    --include='*/' \
    --include='*.json' \
    --exclude='*' \
    "$SOURCE_DATA/" "$BACKUP_DIR/data/"

  # 备份元信息（便于排查，非业务数据）
  python3 - <<'PY' "$SOURCE_DATA" "$BACKUP_DIR/data/_backup_meta.json"
import json, sys, os
from datetime import datetime, timezone
src, out = sys.argv[1], sys.argv[2]
files = sorted(f for f in os.listdir(src) if f.endswith(".json"))
meta = {
    "backed_up_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    "source": src,
    "files": {
        f: os.path.getsize(os.path.join(src, f)) for f in files
    },
}
with open(out, "w", encoding="utf-8") as fh:
    json.dump(meta, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY
}

commit_and_push() {
  cd "$BACKUP_DIR"
  # data/ 在 .gitignore 中，强制纳入 JSON 备份
  git add -f data/*.json data/_backup_meta.json 2>/dev/null || git add -f data/
  if git diff --cached --quiet; then
    log "数据无变更，跳过提交"
    return 0
  fi
  local stamp
  stamp="$(date '+%Y-%m-%d %H:%M:%S %z')"
  git -c user.name="knx-backup" -c user.email="backup@knx-outreach.local" \
    commit -m "backup: ${stamp}"
  # 若期间有代码推送，rebase 后再推，避免覆盖 main
  if ! git push origin "HEAD:$BACKUP_BRANCH"; then
    log "push 失败，尝试 rebase 后重试"
    git pull --rebase origin "$BACKUP_BRANCH"
    git push origin "HEAD:$BACKUP_BRANCH"
  fi
  log "已推送到 origin/$BACKUP_BRANCH（仓库根目录 data/*.json）"
}

ensure_repo
sync_data
commit_and_push
log "完成"
