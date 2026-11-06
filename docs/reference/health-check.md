# 健康检查（Health Check）

> 适用版本：v0.170.5+。端点：`GET /api/health`（无鉴权；生产环境仅允许内网 RFC1918 访问）。

## 一、状态码

| HTTP | status | 含义 | 典型原因 |
|---|---|---|---|
| 200 | `ok` | 全部检查通过 | 数据库可读写、磁盘 ≥500MB、调度器心跳 ≤180s |
| 207 | `degraded` | 服务可用但降级 | 磁盘 <500MB；`scheduler_lock` 心跳缺失或超过 180s |
| 500 | `down` | 核心不可用 | 数据库 SELECT 失败，或 TEMP 表写入失败 |
| 403 | — | 生产环境外网访问被拒 | 客户端 IP 不在 10/8、172.16/12、192.168/16、127/8 |

## 二、响应字段

```json
{
  "status": "ok",
  "timestamp": "2026-11-06T19:30:00+08:00",
  "version": "0.170.5",
  "services": {"database": true, "monitor_service": true, "parser": true},
  "checks": {
    "disk": {"free_mb": 12345.6, "threshold_mb": 500.0, "ok": true},
    "scheduler": {"heartbeat_at": "2026-11-06T19:29:55+08:00", "age_seconds": 5.0, "ok": true},
    "database_rw": {"read": true, "write": true}
  }
}
```

### 指标说明

| 指标 | 来源 | 判定 |
|---|---|---|
| `checks.disk.free_mb` | 数据目录所在磁盘 `shutil.disk_usage` | <`threshold_mb`（500MB）→ `degraded` |
| `checks.scheduler.heartbeat_at` | `scheduler_lock.heartbeat_at` | 缺失或 `age_seconds`>180 → `degraded` |
| `checks.database_rw.read` | `SELECT 1` | 失败 → `down`/500 |
| `checks.database_rw.write` | `CREATE TEMP TABLE` + INSERT + DELETE | 失败 → `down`/500（不触碰业务表） |
| `services.monitor_service/parser` | 管理器初始化状态 | 仅展示，不改变状态码 |

`timestamp` 为带时区偏移的 ISO 8601（由 `pilotstd.core.time_utils.iso_now()` 生成）。

## 三、使用方式

```bash
# 普通探测（2xx 均视为存活；207 表示降级）
curl -fsS http://127.0.0.1:9028/api/health

# 严格模式：207 也视为失败（编排系统按需）
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9028/api/health
```

Docker `HEALTHCHECK` 使用 `curl -fsS`，因此 200/207 都判为 healthy；500 才重启/标记 unhealthy。

## 四、与监控联动

- `degraded` 持续出现时，优先看：磁盘清理（`/api/clean-empty`）、调度器线程/锁（`scheduler_lock`）、日志中的 `database is locked`。
- 调度器心跳超时不会自动重启调度器，需要人工检查容器内调度线程；心跳恢复后自动回到 `ok`。
