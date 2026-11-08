-- =============================================================================
-- announcement_record 脏数据清理脚本
-- =============================================================================
-- 用途：清空公告抓取相关的历史数据，解决统计膨胀问题后重新抓取。
-- 目标数据库：PilotStd SQLite（通常位于 DATA_DIR/pilotstd.db）
--
-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  ⚠️  操作前必读                                                          ║
-- ╠═══════════════════════════════════════════════════════════════════════════╣
-- ║  1. 先备份数据库！                                                       ║
-- ║     cp <DATA_DIR>/pilotstd.db <DATA_DIR>/pilotstd_backup_$(date).db      ║
-- ║  2. 确认公告抓取未在运行（关闭 Web 服务或等待抓取完成）。                 ║
-- ║  3. 统计 Bug 已修复（docker/api/announce.py 的 COUNT(*) 已部署）。       ║
-- ║  4. 执行后需重新运行公告抓取以恢复数据。                                  ║
-- ║  5. 执行后统计卡片数据将归零，属于预期行为，抓取完成后逐步恢复。          ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝
--
-- 执行方式（Docker 环境）：
--   docker exec -it pilotstd sqlite3 /app/data/pilotstd.db < cleanup_announcement_data.sql
--
-- 执行方式（本地环境）：
--   sqlite3 <DATA_DIR>/pilotstd.db < cleanup_announcement_data.sql
-- =============================================================================

-- ── 白名单：允许清空的表 ───────────────────────────────────────────────────

-- 1. announcement_record（公告明细记录 — 核心清洗目标）
--    每条记录对应一个 (公告号, 标准号) 组合。
--    清空后：前端列表为空、统计卡片归零，重新抓取后逐步恢复。
DELETE FROM announcement_record;

-- 2. announcement_match（匹配结果缓存 — 派生数据，可安全清空）
--    存储公告标准号与本地 file_index 的交叉比对结果。
--    为什么可以清空：这是纯缓存/派生数据，不包含原始数据。
--    AnnouncementMatcher.match_and_update() 在每次抓取时会自动重建此表。
--    注：file_index 表不受任何影响，本地标准库完好无损。
DELETE FROM announcement_match;

-- 3. fetch_checkpoint（抓取断点记录）
--    记录每个公告源的 last_fetched_at 和 last_notice_date。
--    清空后：下次抓取从最新日期开始（等同于首次抓取行为），
--    不会遗漏数据，只是会多拉几页已有的公告（INSERT OR IGNORE 自动跳过）。
DELETE FROM fetch_checkpoint;

-- 4. fetch_task（异步抓取任务记录 — 仅公告类型）
--    清空历史任务状态，避免残留的 pending/running 状态误导前端。
DELETE FROM fetch_task WHERE task_type = 'announcement';

-- ── 可选：清理统计缓存（非必须）───────────────────────────────────────────
-- 如果 Web 服务在运行，5 分钟缓存会在到期后自动刷新。
-- 如需立即生效，可重启 Web 服务或手动执行：
--   DELETE FROM standard_info_cache WHERE source = 'announcement';
-- （不推荐手动操作缓存表，重启服务更安全）

-- ── 🔴 以下表严禁触碰 ──────────────────────────────────────────────────────
-- file_index           — 本地标准文件索引，核心业务数据
-- standard_validity    — 标准时效性检查结果
-- adapter_health       — 适配器熔断状态，清空可能导致短时间内被封 IP
-- rotator_state        — 站点轮转计数器，清空会打乱负载均衡
-- daily_quota          — 日配额追踪，清空可能导致超额请求
-- users / api_keys     — 用户认证数据
-- user_layouts / user_preferences — 用户个性化配置
-- =============================================================================

-- 验证清理结果
SELECT 'announcement_record' AS table_name, COUNT(*) AS remaining_rows FROM announcement_record
UNION ALL
SELECT 'announcement_match', COUNT(*) FROM announcement_match
UNION ALL
SELECT 'fetch_checkpoint', COUNT(*) FROM fetch_checkpoint
UNION ALL
SELECT 'fetch_task (announcement)', COUNT(*) FROM fetch_task WHERE task_type = 'announcement';
