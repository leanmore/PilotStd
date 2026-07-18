#!/bin/bash
# 全量重跑公告解析 + 验证
# 在 Docker 容器内执行：docker exec -it <容器名> bash /app/scripts/reparse_all.sh
# 或直接在容器终端内：bash /app/scripts/reparse_all.sh

set -e

API_BASE="http://localhost:9028"
DB_PATH="${DATA_DIR:-/app/data}/pilotstd.db"

echo "============================================"
echo "PilotStd 全量公告重解析 + 验证"
echo "DB: $DB_PATH"
echo "API: $API_BASE"
echo "============================================"

# ── 获取所有公告编号 ──
echo ""
echo "[1/3] 获取公告列表..."
ANNO_LIST=$(curl -s "$API_BASE/api/announce/results" | \
  python3 -c "import sys,json; [print(r['announce_no']) for r in json.load(sys.stdin).get('results',[])]")

TOTAL=$(echo "$ANNO_LIST" | wc -l)
echo "共 $TOTAL 条公告"

# ── 逐个触发解析 ──
echo ""
echo "[2/3] 开始重解析..."
DONE=0
while IFS= read -r anno_no; do
  [ -z "$anno_no" ] && continue
  DONE=$((DONE + 1))
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_BASE/api/announcements/${anno_no}/parse")
  echo "  [$DONE/$TOTAL] $anno_no -> HTTP $HTTP_CODE"
  sleep 1
done <<< "$ANNO_LIST"

echo ""
echo "[3/3] 验证结果..."
echo ""

sqlite3 "$DB_PATH" <<SQL
.mode column
.headers on

.print '=== 日期字段填充情况 ==='
SELECT 'publish_date' AS 字段, COUNT(*) AS 有值记录数
FROM announcement_record WHERE publish_date IS NOT NULL AND publish_date != ''
UNION ALL
SELECT 'implement_date', COUNT(*)
FROM announcement_record WHERE implement_date IS NOT NULL AND implement_date != ''
UNION ALL
SELECT 'expiry_date', COUNT(*)
FROM announcement_record WHERE expiry_date IS NOT NULL AND expiry_date != '';

.print ''
.print '=== row_index 分布（>0 表示序号已写入）==='
SELECT row_index, COUNT(*) AS 记录数
FROM announcement_record WHERE row_index > 0;

.print ''
.print '=== status 分布 ==='
SELECT status, COUNT(*) AS 记录数
FROM announcement_record GROUP BY status;

.print ''
.print '=== 总记录数 ==='
SELECT COUNT(*) AS 总记录数 FROM announcement_record;
SQL

echo ""
echo "============================================"
echo "完成。"
echo "============================================"
