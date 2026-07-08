-- =============================================================================
-- 公告抓取数据库诊断与修复脚本
-- =============================================================================
-- 用途：诊断 Bug 1/2 造成的数据异常（全量入库、统计膨胀），并提供修复。
-- 目标数据库：PilotStd SQLite（容器内路径 /app/data/pilotstd.db）
--
-- 执行方式（Docker 环境，任选一种）：
--   方式A — 整文件执行（诊断+修复）：
--     docker exec -it pilotstd sqlite3 /app/data/pilotstd.db < diagnose_announce.sql
--   方式B — 交互式逐步执行：
--     docker exec -it pilotstd sqlite3 /app/data/pilotstd.db
--     然后逐段粘贴下方 SQL
--   方式C — 仅诊断不修复：
--     docker exec -it pilotstd sqlite3 /app/data/pilotstd.db
--     只执行步骤1和步骤2的 SELECT 语句
--
-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  ⚠️  执行修复前先备份！                                                    ║
-- ║  cp /app/data/pilotstd.db /app/data/pilotstd_backup_$(date +%Y%m%d).db     ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝
-- =============================================================================

-- =============================================================================
-- 步骤1：诊断 — 检查 fetched_at 日期分布
-- 如果大量数据集中在同一天 → 确认是全量抓取导致
-- =============================================================================
SELECT '=== 步骤1：fetched_at 日期分布（Top 10）===' AS '';
SELECT date(fetched_at) AS fetch_date,
       COUNT(*) AS row_count,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM announcement_record), 1) AS pct
FROM announcement_record
GROUP BY date(fetched_at)
ORDER BY row_count DESC
LIMIT 10;

-- =============================================================================
-- 步骤2：诊断 — 检查是否存在重复记录
-- UNIQUE(source_site, pid, standard_number) 本应阻止重复，
-- 但若数据分批抓取或约束失效，仍可能出现
-- =============================================================================
SELECT '=== 步骤2：重复记录检查 ===' AS '';
SELECT source_site, pid, standard_number, COUNT(*) AS dup_count
FROM announcement_record
GROUP BY source_site, pid, standard_number
HAVING COUNT(*) > 1
ORDER BY dup_count DESC
LIMIT 20;

-- =============================================================================
-- 步骤3：诊断 — 与统计卡片对照
-- 这三个数字对应前端"标准总数 / 已匹配 / 今日新增"
-- 如果 total_all = new_all → 确认所有数据都是今天入库的
-- =============================================================================
SELECT '=== 步骤3：统计卡片对照 ===' AS '';
SELECT '标准总数' AS label, COUNT(*) AS value FROM announcement_record
UNION ALL
SELECT '已匹配', COUNT(*) FROM announcement_record WHERE matched = 1
UNION ALL
SELECT '今日新增', COUNT(*) FROM announcement_record WHERE date(fetched_at) = date('now', 'localtime');

-- =============================================================================
-- 步骤4：诊断 — 按公告源拆分今日新增
-- =============================================================================
SELECT '=== 步骤4：今日新增按源拆分 ===' AS '';
SELECT source_site,
       COUNT(*) AS cnt,
       MIN(publish_date) AS earliest_pub,
       MAX(publish_date) AS latest_pub
FROM announcement_record
WHERE date(fetched_at) = date('now', 'localtime')
GROUP BY source_site;

-- =============================================================================
-- 步骤5：修复 — 删除异常全量抓取的数据（仅当步骤1确认是单日集中入库时执行）
-- =============================================================================
SELECT '=== 步骤5：确认后执行修复 ===' AS '';
SELECT '⚠️  以上诊断结果确认需要清理后，取消下方 DELETE 语句的注释再执行' AS '';

-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  修复策略：清空公告数据 → 重建 → 下次定时或手动抓取从最新日期开始         ║
-- ║  不会丢失任何公告数据：                                                        ║
-- ║  - 适配器熔断状态保留（adapter_health 不动）                             ║
-- ║  - 下次抓取会自动从 SAMR API 获取最新公告                                ║
-- ║  - INSERT OR IGNORE 自动跳过已存在的记录                                 ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

-- -- 清空公告抓取记录
-- DELETE FROM announcement_record;
--
-- -- 清空匹配结果缓存（纯派生数据，抓取时会自动重建）
-- DELETE FROM announcement_match;
--
-- -- 重置抓取断点（下次从最新日期开始增量抓取）
-- DELETE FROM fetch_checkpoint;
--
-- -- 清空历史异步任务
-- DELETE FROM fetch_task WHERE task_type = 'announcement';

-- =============================================================================
-- 步骤6：修复后验证
-- =============================================================================
-- SELECT 'announcement_record' AS tbl, COUNT(*) AS n FROM announcement_record
-- UNION ALL
-- SELECT 'announcement_match', COUNT(*) FROM announcement_match
-- UNION ALL
-- SELECT 'fetch_checkpoint', COUNT(*) FROM fetch_checkpoint
-- UNION ALL
-- SELECT 'fetch_task(announce)', COUNT(*) FROM fetch_task WHERE task_type = 'announcement';
