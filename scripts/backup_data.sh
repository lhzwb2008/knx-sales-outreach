#!/usr/bin/env bash
# 本地数据备份：只读复制 data/*.json → 服务器本地目录（不推 Git）
# 不加载、不恢复、不依赖主服务进程。失败不影响陌拜工作台。
#
# 环境变量（均可选）:
#   SOURCE_DATA   默认 /opt/knx-outreach/data
#   BACKUP_ROOT   默认 /var/backups/knx-outreach
#   KEEP_COUNT    保留最近 N 份快照，默认 48（约两天每小时）
set -euo pipefail

SOURCE_DATA="${SOURCE_DATA:-/opt/knx-outreach/data}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/knx-outreach}"
KEEP_COUNT="${KEEP_COUNT:-48}"
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

stamp="$(date '+%Y%m%d-%H%M%S')"
dest="${BACKUP_ROOT}/${stamp}"
mkdir -p "$dest"

rsync -a --delete \
  --exclude='._*' \
  --include='*/' \
  --include='*.json' \
  --exclude='*' \
  "$SOURCE_DATA/" "$dest/"

python3 - <<'PY' "$SOURCE_DATA" "$dest/_backup_meta.json"
import json, sys, os
from datetime import datetime, timezone
src, out = sys.argv[1], sys.argv[2]
files = sorted(f for f in os.listdir(src) if f.endswith(".json"))
meta = {
    "backed_up_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    "source": src,
    "files": {f: os.path.getsize(os.path.join(src, f)) for f in files},
}
with open(out, "w", encoding="utf-8") as fh:
    json.dump(meta, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY

ln -sfn "$dest" "${BACKUP_ROOT}/latest"

# 只保留最近 KEEP_COUNT 份带时间戳的目录
mapfile -t snaps < <(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort -r)
if ((${#snaps[@]} > KEEP_COUNT)); then
  for old in "${snaps[@]:KEEP_COUNT}"; do
    rm -rf "${BACKUP_ROOT}/${old}"
    log "已清理旧快照: $old"
  done
fi

log "已备份到 $dest（latest → 该目录；保留最近 ${KEEP_COUNT} 份）"
log "完成"
