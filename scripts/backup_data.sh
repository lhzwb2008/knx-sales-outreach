#!/usr/bin/env bash
# 独立数据备份：只读复制 data/*.json → 当前仓库 data-backup 分支并 push
# 不加载、不恢复、不依赖主服务进程。失败不影响陌拜工作台。
#
# 环境变量（均可选）:
#   SOURCE_DATA   默认 /opt/knx-outreach/data
#   BACKUP_DIR    默认 /opt/knx-outreach-data-backup（独立 clone，与业务目录分离）
#   BACKUP_REMOTE 默认 git@github.com:lhzwb2008/knx-sales-outreach.git
#   BACKUP_BRANCH 默认 data-backup
set -euo pipefail

SOURCE_DATA="${SOURCE_DATA:-/opt/knx-outreach/data}"
BACKUP_DIR="${BACKUP_DIR:-/opt/knx-outreach-data-backup}"
BACKUP_REMOTE="${BACKUP_REMOTE:-git@github.com:lhzwb2008/knx-sales-outreach.git}"
BACKUP_BRANCH="${BACKUP_BRANCH:-data-backup}"
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
    git clone --branch main --single-branch "$BACKUP_REMOTE" "$BACKUP_DIR"
  fi
  cd "$BACKUP_DIR"
  git remote set-url origin "$BACKUP_REMOTE"
  git fetch origin --prune

  if git show-ref --verify --quiet "refs/remotes/origin/$BACKUP_BRANCH"; then
    git checkout -B "$BACKUP_BRANCH" "origin/$BACKUP_BRANCH"
  elif git show-ref --verify --quiet "refs/heads/$BACKUP_BRANCH"; then
    git checkout "$BACKUP_BRANCH"
  else
    log "创建 orphan 分支 $BACKUP_BRANCH（仅保留备份数据）"
    git checkout --orphan "$BACKUP_BRANCH"
    git rm -rf . >/dev/null 2>&1 || true
    # 清理未跟踪残留
    find . -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +
    mkdir -p data
    cat > README.md <<'EOF'
# KNX 智拓 · 业务数据备份

此分支由服务器定时任务自动推送，**仅作备份，不自动回载**。

- 内容：`data/*.json`（leads / outreach / profiles 等）
- 来源：生产机 `/opt/knx-outreach/data`
- 不含：`.env`、密钥、上传的二进制大文件

如需人工恢复：把对应 JSON 拷回服务器 `data/` 后重启服务即可。
EOF
    git add README.md
    git -c user.name="knx-backup" -c user.email="backup@knx-outreach.local" \
      commit -m "chore: init data-backup branch"
  fi
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
  # data/ 在主仓 .gitignore 中，备份分支强制纳入
  git add -f data/*.json data/_backup_meta.json 2>/dev/null || git add -f data/
  if git diff --cached --quiet; then
    log "数据无变更，跳过提交"
    return 0
  fi
  local stamp
  stamp="$(date '+%Y-%m-%d %H:%M:%S %z')"
  git -c user.name="knx-backup" -c user.email="backup@knx-outreach.local" \
    commit -m "backup: ${stamp}"
  git push -u origin "HEAD:$BACKUP_BRANCH"
  log "已推送到 origin/$BACKUP_BRANCH"
}

ensure_repo
sync_data
commit_and_push
log "完成"
