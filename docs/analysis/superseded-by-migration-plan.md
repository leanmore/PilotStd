# superseded_by 方向纠正迁移方案（待授权）

> 2026-11-19。**不执行**，等老板授权与维护窗口。

## 现状

`announcement_record.superseded_by` 被写入“代替旧号”（如 `GB 30871-2022 -> GB 30871-2014`），语义应反过来：旧标准指向新标准。非空行约 49,306。

## 迁移规则

对每行 `(std, sup)`：
1. 若 `sup` 为空 → 跳过；
2. 若 `sup` 年份 < `std` 年份（方向反）→ 交换：`std.superseded_by` 置空，`sup.superseded_by = std`；
3. 若 `sup` 年份 >= `std` 年份 → 保持（已是正确方向）；
4. 多条旧号（逗号分隔）逐条拆开处理。

## 脚本（计划）

`scripts/migrate_superseded_by_direction.py`：
- 默认 `--dry-run`：只统计将修改行数、样例，不写库；
- `--apply` 才执行，事务内分批（每 500 行）提交；
- 执行前 `sqlite3.announcement_record` 复制为 `announcement_record_bak_20261119`（同库备份）；
- 记录 `migration_log`（若存在）或输出 JSON 清单。

## 回滚

`scripts/rollback_superseded_by_direction.py`：
- 用备份表恢复 `superseded_by` 列（按 `standard_number` 回写）；
- 或按执行 JSON 清单逐条反向交换。

## 预估

- 行数约 4.9 万；SQLite 单事务分批 500 行，预计 **1~3 分钟**（以实测为准）；
- 锁：写事务期间 `announcement_record` 写入阻塞，查询可继续（WAL）；建议低峰执行；
- 风险：中途失败（事务分批需记录进度）、并发公告写入（执行前暂停公告定时任务）、备份表占用空间。

## 授权前检查

1. 生产备份完成并校验；
2. 公告定时任务暂停；
3. 先 dry-run 核对样例（GB 30871-2022 等）；
4. 老板确认后在窗口执行。
