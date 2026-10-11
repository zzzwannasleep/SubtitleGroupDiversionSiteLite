#!/bin/sh
# qb_clean.sh —— qBittorrent 合集/分集清理（Linux/macOS 版，依赖 curl + jq）
#
# 用法一（推荐，全自动）：把下面这条命令粘到
#   qBittorrent → 设置 → 下载 → 「Torrent 完成时运行外部程序」：
#     /完整路径/qb_clean.sh "%I"
#   合集下载完成的那一刻，自动删掉 QB 里命名相同的分集任务。
#
# 用法二（手动全量清理）：
#   ./qb_clean.sh             # 先看报告，不删除
#   ./qb_clean.sh --apply     # 确认报告后真正删除
#
# 可选：KEEP_FILES=1 ./qb_clean.sh   只删任务、保留硬盘文件
# 依赖：curl、jq（Ubuntu/Debian: sudo apt install curl jq；Alpine: apk add curl jq）
# 匹配规则与站点同源（tools/qb_clean.jq），保守优先：宁可漏删、不可错删。

# ↓↓↓ 把这三行改成你的 qBittorrent 配置（设置 → Web UI 里开启），或用同名环境变量覆盖 ↓↓↓
QB_URL="${QB_URL:-http://127.0.0.1:8080}"
QB_USER="${QB_USER:-admin}"
QB_PASS="${QB_PASS:-请改成你的密码}"
KEEP_FILES="${KEEP_FILES:-0}"

HASH=""
APPLY=0
for a in "$@"; do
  case "$a" in
    --apply|-apply) APPLY=1 ;;
    *) [ -z "$HASH" ] && HASH="$(printf '%s' "$a" | tr 'A-Z' 'a-z')" ;;
  esac
done

if [ -z "$QB_PASS" ] || [ "$QB_PASS" = "请改成你的密码" ]; then
  echo "RESULT: error password-not-configured deleted=0"
  echo "请先编辑 qb_clean.sh 顶部的 QB_URL / QB_USER / QB_PASS 三行配置"
  exit 1
fi

command -v curl >/dev/null 2>&1 || { echo "缺少 curl：Ubuntu/Debian 执行 sudo apt install curl"; exit 1; }
command -v jq   >/dev/null 2>&1 || { echo "缺少 jq：Ubuntu/Debian 执行 sudo apt install jq"; exit 1; }

JQF="$(dirname "$0")/qb_clean.jq"
[ -f "$JQF" ] || { echo "找不到 $JQF"; exit 1; }

JAR="$(mktemp)"; TSV="$(mktemp)"; ITEMS="$(mktemp)"; OUT="$(mktemp)"
trap 'rm -f "$JAR" "$TSV" "$ITEMS" "$OUT"' EXIT

R=$(curl -sS -c "$JAR" --data-urlencode "username=$QB_USER" --data-urlencode "password=$QB_PASS" "$QB_URL/api/v2/auth/login" 2>&1) \
  || { echo "QB 登录失败：$R"; echo "RESULT: error login-failed deleted=0"; exit 1; }
case "$R" in
  Ok.*) : ;;
  *) echo "QB 登录失败：$R"; echo "RESULT: error login-failed deleted=0"; exit 1 ;;
esac

INFO=$(curl -sS -b "$JAR" "$QB_URL/api/v2/torrents/info" 2>/dev/null)
[ -n "$INFO" ] || { echo "RESULT: error info-failed deleted=0"; exit 1; }

# 逐个任务取文件数，组装 NDJSON（标题命中合集关键词的免一次请求）
printf '%s' "$INFO" | jq -r '.[] | [.hash, .name] | @tsv' > "$TSV"
while IFS="$(printf '\t')" read -r H NM; do
  [ -n "$H" ] || continue
  if printf '%s' "$NM" | jq -e 'ascii_downcase | test("合集|全集|合订|全一卷|全季|完全版|complete|batch|anthology")' >/dev/null 2>&1; then
    FC=-1
  else
    FC=$(curl -sS -b "$JAR" "$QB_URL/api/v2/torrents/files?hash=$H" 2>/dev/null | jq 'length')
    case "$FC" in ''|*[!0-9]*) FC=0 ;; esac
  fi
  jq -cn --arg h "$H" --arg n "$NM" --argjson fc "$FC" '{hash:$h, name:$n, fc:$fc}'
done < "$TSV" > "$ITEMS"

# 匹配 + 事件判定（core 在 qb_clean.jq，与站点/Windows 版同源）
jq -cn --arg h "$HASH" --slurpfile I "$ITEMS" '{hash:$h, items:$I[0]}' | jq -c -f "$JQF" > "$OUT"
PLAN=$(cat "$OUT")
[ -n "$PLAN" ] || { echo "RESULT: error plan-failed deleted=0"; exit 1; }

MODE=$(printf '%s' "$PLAN" | jq -r '.iscol')
COLS_N=$(printf '%s' "$PLAN" | jq '.collections | length')
DELN=$(printf '%s' "$PLAN" | jq '.deletions | length')

echo "合集 $COLS_N 个："
printf '%s' "$PLAN" | jq -r '.collections[] | "  [合集] \(.)"'
echo ""
echo "待删分集 $DELN 个："
printf '%s' "$PLAN" | jq -r '.deletions[] | "  [分集] \(.title)  <- 匹配合集：\(.matched)"'

# 事件模式：只有合集完成才动手；手动模式需 --apply
if [ -n "$HASH" ]; then
  if [ "$MODE" != "collection" ]; then
    echo "RESULT: $MODE deleted=0"
    exit 0
  fi
elif [ "$APPLY" != "1" ]; then
  echo ""
  echo "以上为报告，未删除任何东西。确认无误后加 --apply 执行。"
  echo "RESULT: collections=$COLS_N deletions=$DELN deleted=0"
  exit 0
fi

HASHES=$(printf '%s' "$PLAN" | jq -r '[.deletions[].hash] | join("|")')
if [ -z "$HASHES" ]; then
  echo "RESULT: collections=$COLS_N deletions=$DELN deleted=0"
  exit 0
fi

DF=true
[ "$KEEP_FILES" = "1" ] && DF=false
curl -sS -b "$JAR" --data-urlencode "hashes=$HASHES" --data-urlencode "deleteFiles=$DF" \
  "$QB_URL/api/v2/torrents/delete" >/dev/null
if [ "$KEEP_FILES" = "1" ]; then
  echo "已删除 $DELN 个分集任务（保留硬盘文件）"
else
  echo "已删除 $DELN 个分集任务（含硬盘文件）"
fi
echo "RESULT: collections=$COLS_N deletions=$DELN deleted=$DELN"