# 部署运维指南

> 最后更新：2026-09-26

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

**方式 A（推荐，现行流程）：拉 GHCR 镜像 + compose**

`docker-compose.yml` 已指向发布镜像 `ghcr.io/leanmore/pilotstd:latest`，CI 每次推送 main 会构建新镜像：

```bash
docker compose pull && docker compose up -d
```

镜像内已含前端产物，无需本地构建前端。首次拉取需在宿主机登录 GHCR（`read:packages` 权限的 PAT）。

**方式 B：容器内自更新（管理员）**

容器挂载了 `/var/run/docker.sock` 时，可调用 `POST /api/system/update`：
拉取 `latest` → 比对 digest → 有变化则用 compose 重建容器并重启（`docker/api/system.py:152`）。
**该端点不会自动定时触发**——现场不会自己变新版本，必须有人调用或手工 `compose pull`。
若未设置 `COMPOSE_FILE`，则只完成拉取、返回"需要 compose 配置才能重建容器"。

**方式 C（离线/自建）：本地构建镜像**

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
# 服务与版本（image/tag 反映实际运行的发布件）
curl -s http://localhost:9028/api/health
curl -s http://localhost:9028/api/system/version
# 预期：{"version": "0.<minor>.<patch>", "tag": "v<...>", "image": "ghcr.io/leanmore/pilotstd:v<...>"}

# 数据库结构版本（无专门端点，用管理员 SQL 端点）
curl -s -X POST http://localhost:9028/query \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -b "pilotstd_token=$TOKEN; csrf_token=$CSRF" \
  -d '{"sql":"SELECT MAX(version) AS v FROM _schema_version"}'
# 预期：等于 pilotstd/core/db/_constants.py 的 CURRENT_SCHEMA_VERSION（当前 59）
```

> 历史说明：本文档 2026-07-27 版写的 `curl /api/system/db-version → {"version": 44}` **不存在该端点**，
> 已按实际接口更正（实测 `/api/system` 下只有 `version` / `health` / `resources`）。

## v44 同步部署专项检查清单（历史清单，2026-07-27 时点）

> 该清单是 v44 迁移当次的专项检查，**已完成**，保留作审计轨迹。
> 表中"预期 44"需按当时环境读取；当前 `CURRENT_SCHEMA_VERSION = 59`。
> 第 9 项引用的 `scripts/rollback_v44.sql` **当前已不存在**（2026-09-26 实测），回滚需另备方案。

| # | 检查项 | 验证命令 | 通过标准 |
|---|--------|----------|----------|
| 1 | 服务代码已部署 | 检查 commit hash | 与发布版本一致 |
| 2 | 三个改造文件已更新 | `grep "favorite_downloads" pilotstd/tasks/favorite_download.py` | 有匹配 |
| 3 | 迁移版本正确 | `SELECT MAX(version) FROM _schema_version`（经 `POST /query`） | v44 时点为 44；当前 59 |
| 4 | user_favorites 无残留 | SQL 见下方 | 结果为 0 |
| 5 | favorite_downloads 有数据 | `SELECT COUNT(*) FROM favorite_downloads` | > 0（如有历史数据） |
| 6 | 收藏操作正常 | 前端收藏/取消收藏 | 200 OK |
| 7 | 归档下载正常 | 等待下一次 cron 或手动触发 | `favorite_downloads.status` 流转正常 |
| 8 | 日期提醒正常 | 手动触发 `date_reminder` | 无 SQL 错误 |
| 9 | 回滚脚本已就绪 | `ls scripts/rollback_v44.sql` | ❌ 文件已不存在（2026-09-26 实测） |

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

# 手动清理通知日志（表名 notification_log，时间列 sent_at）
python -c "
from pilotstd.core.db import Database
from pilotstd.core.config import get_db_path
db = Database(get_db_path())
db.execute('DELETE FROM notification_log WHERE sent_at < datetime(\"now\", \"-30 days\")')
db.close()
"
```
