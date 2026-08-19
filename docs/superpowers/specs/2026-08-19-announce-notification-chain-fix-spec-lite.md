# spec-lite：公告通知系统全链路修复

> 日期：2026-08-19 · 类型：功能修复（五阶段） · 关联调查：公告抓取与通知发送机制

## 用户指令摘要

修复公告通知链路五层问题：① 配置层 Web 端设置与后端不同步（DB 权威化）；② 数据层定时/回填路径通知载荷缺 gb_count 等字段；③ 事件层三个死事件（announcement_fetch_complete/failed/announce_fetch_summary）无调用点；④ 可观测性层静默出口无日志、notifier 吞异常；⑤ 测试层 test_trigger_exists 正则"伪通过"。按五个阶段独立提交。

## 采纳的关键设计决策

1. `notification.enabled` 用户级配置**数据库优先**（user_preferences 表），config.json 兜底；`NotificationManager.__init__` 启动时读 DB 覆盖，API 更新时双写 DB + config.json。
2. 公告分类统计（gb/hb/db/total_standards）统一口径：`COUNT(DISTINCT announce_no)` + `COUNT(*)`，提取公共函数 `query_announcement_stats`，废弃 `SUM(standard_count)`（N² 膨胀）；check_all 与回填归一化路径均注入。
3. 恢复三个死事件触发，对齐重构前（994ba7fb）行为：全站失败→`announcement_fetch_failed`，有适配器明细→`announce_fetch_summary`，手动路径→`announcement_fetch_complete`；`send_event` 新增可选 `bypass_aggregation` 参数。
4. 静默出口日志化：`enabled=False`→DEBUG，无订阅渠道→INFO，通知/缓存异常→`logger.warning`（移除全部 `except: pass`）。
5. e2e `test_trigger_exists` 由正则改为 **AST 精确匹配**（字面量 + events 模块常量解析），消除 `EVENT_[A-Z_]+` 模糊匹配伪通过。

## 识别到的风险点及与现有架构的冲突

1. `NotificationManager.__init__` 新增 DB 查询，测试 Mock（MagicMock fetchone）需类型白名单（str/bool/int/float）过滤，避免 MagicMock 值误判为 True。
2. `query_announcement_stats` 需兼容双后端（pilotstd Database dict 行 / sqlite3 tuple 行），并兜底表缺失。
3. `send_event` 增加可选参数向后兼容，但 bypass 语义与静音时段存在叠加（bypass 只跳过聚合，不跳过静音暂存）。
4. 事件字典/测试元数据（trigger_file）曾引用已删除文件 `_announce_fetch.py`，需同步修正（e2e 表 + skipped_tests 文档）。
5. `_get_announcement_stats`（announce_service）原口径 SUM(standard_count) 有 N² 膨胀，委托公共函数后统计值会变化（更准确），需知会。

## 验证方式

- 阶段一：`tests/test_notification_manager.py::TestUserEnabledFromDb`、`TestUpdateConfigSync`、`TestConfigManagerReload`
- 阶段二：`tests/announce/test_crawler_service.py::TestQueryAnnouncementStats`、`test_group1_announcement_manager.py` 归一化测试
- 阶段三：`tests/announce/test_notifier.py::TestDeadEventsRestored`、`TestSendEvent::test_bypass_aggregation*`
- 阶段四：`TestSendEvent::test_disabled_logs_debug / test_no_channels_logs_info`（caplog）
- 阶段五：`pytest tests/test_notification_e2e.py`（AST 精确匹配 32 事件全部真实通过）
- 全量：`pytest tests/test_notification*.py` 366 passed；`scripts/check_all.sh --fast` 零错误
