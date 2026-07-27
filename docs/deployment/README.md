# 部署运维指南

> 最后更新：2026-07-27

## 环境依赖

| 依赖 | 最低版本 | 说明 |
|------|----------|------|
| Python | 3.11 | `str \| None` 联合类型语法 |
| Node.js | 18.x | 前端构建 |
| SQLite | 3.35 | RETURNING 子句支持 |
| 系统库 | — | Windows: 无特殊依赖；Linux: `libsqlite3-dev` |

## 标准部署流程

### 1. 后端部署

```bash
cd /opt/pilotstd
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 验证
python -c "from pilotstd.core.db import Database; print('OK')"
```

### 2. 前端构建

```bash
cd web
npm install
npm run build
# 产出：web/dist/
```

### 3. Docker 部署

```bash
docker build -t pilotstd:latest .
docker run -d \
  -v /data/pilotstd:/app/data \
  -p 9028:9028 \
  --name pilotstd \
  pilotstd:latest
```

### 4. 启动验证

```bash
# 健康检查
curl http://localhost:9028/api/health

# 数据库迁移状态
curl http://localhost:9028/api/system/db-version
# 预期: {"version": 44}
```

## v44 同步部署专项检查清单

| # | 检查项 | 验证命令 | 通过标准 |
|---|--------|----------|----------|
| 1 | 服务代码已部署 | 检查 commit hash | 与发布版本一致 |
| 2 | 三个改造文件已更新 | `grep "favorite_downloads" pilotstd/tasks/favorite_download.py` | 有匹配 |
| 3 | 迁移版本正确 | `curl /api/system/db-version` | `{"version": 44}` |
| 4 | user_favorites 无残留 | SQL 见下方 | 结果为 0 |
| 5 | favorite_downloads 有数据 | `SELECT COUNT(*) FROM favorite_downloads` | > 0（如有历史数据） |
| 6 | 收藏操作正常 | 前端收藏/取消收藏 | 200 OK |
| 7 | 归档下载正常 | 等待下一次 cron 或手动触发 | `favorite_downloads.status` 流转正常 |
| 8 | 日期提醒正常 | 手动触发 `date_reminder` | 无 SQL 错误 |
| 9 | 回滚脚本已就绪 | `ls scripts/rollback_v44.sql` | 文件存在 |

### 部署后验证 SQL

```sql
-- 1. 确认无残留归档状态
SELECT COUNT(*) AS residual_count
FROM user_favorites
WHERE status IN ('downloading', 'archiving', 'done', 'failed', 'abandoned');
-- 预期: 0

-- 2. 确认数据完整迁移
SELECT status, COUNT(*) AS cnt
FROM favorite_downloads
GROUP BY status;

-- 3. 确认迁移版本
SELECT MAX(version) FROM _schema_version;
-- 预期: 44
```

## 常见问题处理

| 问题 | 错误码/日志特征 | 排查步骤 | 解决方案 |
|------|---------------|----------|----------|
| 迁移失败 | `Migration v44 failed` | 1. 检查 SQLite 版本 2. 检查磁盘空间 | 确保 SQLite >= 3.35；回滚后重试 |
| 数据库锁定 | `database is locked` | 检查是否有其他进程持有写锁 | 切换到 WAL 模式；关闭其他连接 |
| 适配器全冷却 | `所有站点均在冷却中` | `SELECT * FROM adapter_state` | `reset_all_cooldowns()` 或等待恢复 |
| 配额耗尽 | `所有站点今日配额已用尽` | `SELECT * FROM daily_quota WHERE query_date=date('now')` | 等待次日 00:00 或调整 daily_limit |
| csres 24h 硬冷却 | `[CSRES_MELTDOWN]` 日志 | `SELECT cooldown_until FROM adapter_state WHERE name='csres'` | 等待冷却到期；无法手动解除 |
| 磁盘空间不足 | `OSError: No space left` | `df -h` | 清理旧备份 `backups/`；扩展磁盘 |
| WAL 文件过大 | WAL 文件 > 100MB | `ls -lh pilotstd.db-wal` | 执行 checkpoint: `PRAGMA wal_checkpoint(TRUNCATE)` |

### 紧急操作

```bash
# 重置所有适配器冷却
python -c "
from pilotstd.query.rotator import SiteRotator
sr = SiteRotator({})
sr.reset_all_cooldowns()
"

# 手动清理通知日志
python -c "
from pilotstd.core.db import Database
from pilotstd.core.config import get_db_path
db = Database(get_db_path())
db.execute('DELETE FROM notification_logs WHERE created_at < datetime(\"now\", \"-30 days\")')
db.close()
"
```
