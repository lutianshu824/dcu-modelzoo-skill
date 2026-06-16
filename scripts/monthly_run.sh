#!/bin/zsh
# 每月自动跑：检查 ModelZoo 更新 + 刷新 snapshot/清单，报告写入输出目录。
# 输出目录由 DCU_MODELZOO_OUT_DIR 决定（可在 config.env 里设，便携）。
# macOS launchd 写受 TCC 保护目录（如 ~/Documents）需授予 Full Disk Access。
DIR="${0:A:h}"                                   # 脚本所在目录（scripts/）
SKILL="${DIR:h}"                                  # 技能根目录
[ -f "$SKILL/config.env" ] && source "$SKILL/config.env"
OUT_DIR="${DCU_MODELZOO_OUT_DIR:-$SKILL/output}"
export DCU_MODELZOO_OUT_DIR="$OUT_DIR"
LOGDIR="$OUT_DIR/_更新日志"
FALLBACK="$SKILL/reports"
STAMP=$(date +%Y-%m)
PY="$(command -v python3 || echo /usr/bin/python3)"

REPORT=$("$PY" "$DIR/check_update.py" --apply 2>&1)

if mkdir -p "$LOGDIR" 2>/dev/null && printf '# ModelZoo 月度更新 %s\n\n%s\n' "$STAMP" "$REPORT" > "$LOGDIR/ModelZoo更新-$STAMP.md" 2>/dev/null; then
  DEST="$LOGDIR/ModelZoo更新-$STAMP.md"
else
  mkdir -p "$FALLBACK"
  printf '# ModelZoo 月度更新 %s\n\n⚠️ 写入输出目录失败（macOS 可能需 Full Disk Access），报告暂存此处。\n\n%s\n' "$STAMP" "$REPORT" > "$FALLBACK/ModelZoo更新-$STAMP.md"
  DEST="$FALLBACK/ModelZoo更新-$STAMP.md  (回退)"
fi
echo "[$(date)] modelzoo monthly done -> $DEST" >> "$SKILL/run.log"
