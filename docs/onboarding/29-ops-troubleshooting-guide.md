# 运维介入排查指南（生产 3 项非代码阻塞）

> 生成日期：2026-11-22。适用：生产 `192.168.1.18`（`ghcr.io/leanmore/pilotstd`，健康检查 `:9028/api/health`）。
> 本指南**只读优先**；所有写操作标注了影响面与回滚方式，执行前请先备份。

---

## 一、DB 验证（4 项 SQL）

**前置**：在有 DB 权限的机器上执行。生产库为 SQLite，容器内路径通常为 `/app/data/pilotstd.db`。

```bash
# 进入容器（把 <container> 换成实际容器名，见第二节的 docker ps）
docker exec -it <container> sh -lc 'ls -l /app/data/pilotstd.db'
# 只读方式打开，避免误写
docker exec -it <container> sh -lc 'sqlite3 -readonly /app/data/pilotstd.db'
```

> 若容器内没有 `sqlite3`，可把库**只读**拷出：`docker cp <container>:/app/data/pilotstd.db /tmp/pilotstd.db`，
> 再在宿主机用任意 SQLite 客户端打开（拷出不影响生产）。

### 1.1 U-1：`last_status` 回填（G-13 / U-1）

```sql
-- 期望：数值应显著低于 740（U-1 前基线）；跑过一轮有效性检查后进一步下降
SELECT COUNT(*) AS null_last_status FROM standard_validity WHERE last_status IS NULL;

-- 参考：按状态分布，确认回填是否覆盖
SELECT COALESCE(last_status, '<NULL>') AS st, COUNT(*) AS n
FROM standard_validity
GROUP BY st
ORDER BY n DESC;
```

**判定**：跑一轮检查（`POST /api/validity/run`，或等定时任务）前后各执行一次；
`null_last_status` 应下降。若完全不降，说明 `update_status` 的“状态未变”分支未走到，需查该批标准是否都没触发检查。

### 1.2 G-02：`query_metrics` 是否落表 found/not_found

```sql
-- 期望：出现 found / not_found 两个 metric_key
SELECT metric_key, COUNT(*) AS rows, SUM(metric_value) AS total
FROM query_metrics
GROUP BY metric_key
ORDER BY rows DESC;

-- 最近批次（确认新代码生效）
SELECT batch_id, metric_key, metric_value
FROM query_metrics
ORDER BY id DESC
LIMIT 20;
```

**判定**：`metric_key` 里应包含 `found` 与 `not_found`。若只有 `validate_failed`，说明批次写入代码未部署或该批未走 `_batch.py`。

### 1.3 G-13：`announcement_record` 事件分布（两时点）

```sql
-- ① 全量分布
SELECT event_type, COUNT(*) AS n
FROM announcement_record
GROUP BY event_type
ORDER BY n DESC;

-- ② 最近 100 条窗口分布（用于判定「窗口内 security_alert + task_failure 是否 = 34」）
SELECT event_type, COUNT(*) AS n
FROM (
  SELECT event_type FROM announcement_record ORDER BY id DESC LIMIT 100
)
GROUP BY event_type
ORDER BY n DESC;
```

**判定**：把 ② 里 `security_alert` 与 `task_failure` 相加；若 = 34，则“66/34”口径成立，否则需按实测修正文档。

### 1.4 superseded_by 迁移：现状分布

```sql
-- ① 总行数
SELECT COUNT(*) AS total FROM announcement_record;

-- ② 目标行（superseded_by 指向的标准号）当前值分布
SELECT CASE
         WHEN superseded_by IS NULL OR superseded_by = '' THEN '<EMPTY>'
         ELSE '<HAS_VALUE>'
       END AS bucket, COUNT(*) AS n
FROM announcement_record
WHERE standard_number IN (SELECT standard_number FROM announcement_record WHERE superseded_by IS NOT NULL AND superseded_by <> '')
GROUP BY bucket;

-- ③ 方向抽查：被指向者是否比指向者更新（按发布时间）
SELECT a.standard_number, a.superseded_by, a.publish_date, b.publish_date AS target_date
FROM announcement_record a
JOIN announcement_record b ON b.standard_number = a.superseded_by
WHERE a.superseded_by IS NOT NULL AND a.superseded_by <> ''
LIMIT 50;
```

**判定**：③ 中若大量出现 `target_date < publish_date`（指向更旧的），即为“方向反了”，需按迁移脚本规则处理；
执行迁移前请先备份（脚本自带 `announcement_record_bak_<yyyymmdd>` 备份表）。

---

## 二、飞书（Feishu）凭证配置

**位置**：Web 通知配置页（`/settings` → 通知 → 飞书），或直接写配置 API。

| 配置键 | 说明 | 是否必填 |
|---|---|---|
| `feishu.app_id` | 企业自建应用 App ID（`cli_` 开头） | ✅ |
| `feishu.app_secret` | 应用 App Secret | ✅ |
| `feishu.receive_id` | 消息接收者 ID（群 `chat_id` 或用户 `open_id`） | ✅ |
| `feishu.receive_id_type` | 取值 `chat_id` / `open_id` / `user_id` / `union_id` | ✅ |
| `feishu.enabled` | 是否启用该渠道 | ✅ |
| `feishu.webhook_url` | 群机器人 webhook（与 app 二选一，菜单功能需 app） | 可选 |

**菜单（群菜单）额外需要**：`chat_id`（通过 `GET /api/notification/menu/chats?channel=feishu` 发现，
该接口在凭证未配置时返回 `400 feishu credentials are not configured`）。

**验证步骤**（配置后）：

```bash
# 1) 渠道状态应为 enabled
curl -s -b cookies.txt http://192.168.1.18:9028/api/notification/menu/status
# 2) 会话发现（应返回 chats 列表而非 400）
curl -s -b cookies.txt 'http://192.168.1.18:9028/api/notification/menu/chats?channel=feishu'
# 3) 测试消息（仅测试，不群发）
curl -s -b cookies.txt -X POST -H 'Content-Type: application/json' \
     -d '{"channel":"feishu"}' http://192.168.1.18:9028/api/notification/test
```

> **注意**：写接口需要 CSRF 双提交（Cookie `csrf_token` + 请求头 `X-CSRF-Token` 同值），
> 用浏览器登录态最省事；脚本调用需先 `POST /api/login`（表单）再带上两个 Cookie。

---

## 三、`mark_missing` 挂载异常排查

**现象**：`POST /api/pending/mark-missing` 返回 `{"checked":61,"missing":61,"updated":0,"skipped":true}` ——
61/61 全部判定缺失，触发挂载异常保护（≥90% 且 ≥50 行）整轮跳过。

**根因方向**：数据库里存的是容器内路径 `/inbox/...`，但宿主机目录没有挂到容器的 `/inbox`。

### 3.1 查容器与挂载

```bash
# 容器名与镜像
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'

# 挂载关系（重点看 Source → Destination）
docker inspect <container> --format '{{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}} (rw={{.RW}}){{"\n"}}{{end}}'

# 或 compose 视角
docker compose -f <compose文件> config | sed -n '/volumes:/,/^[a-z]/p'
```

### 3.2 比对路径

```bash
# ① 容器内 /inbox 是否存在、有多少文件
docker exec <container> sh -lc 'ls -ld /inbox; ls /inbox | head; find /inbox -type f | wc -l'

# ② 数据库里记录的路径样例
docker exec <container> sh -lc "sqlite3 -readonly /app/data/pilotstd.db \
  \"SELECT file_path FROM pending_record WHERE file_path <> '' LIMIT 5;\""

# ③ 逐个验证存在性（把上一步的路径粘进来）
docker exec <container> sh -lc 'test -f "/inbox/AQ 安全生产/SH 石油化工/SHB 6-1999 ....pdf" && echo EXISTS || echo MISSING'
```

**判定**：
- ① 为空或不存在 → 挂载缺失/路径错位，**修 `docker-compose.yml` 的 `volumes`**（例：
  `- /data/pilotstd/inbox:/inbox:rw`），重启容器；
- ① 有文件但 ③ 报 MISSING → 文件名/目录层级不一致（编码、空格、大小写），需比对实际路径与库内路径；
- 库内路径前缀不是 `/inbox`（如 `/app/inbox`）→ 改代码侧 `INBOX_ROOT` 配置或统一挂载点。

### 3.3 修复后验证

```bash
# 修好后重跑：updated 应 > 0 且 skipped=false（或 missing 比例明显下降）
curl -s -b cookies.txt -X POST -H "X-CSRF-Token: $CSRF" \
     http://192.168.1.18:9028/api/pending/mark-missing
```

> **不要**为了绕过保护而关闭 `protect`：保护逻辑本身是对的，全缺失一定是挂载问题。

---

## 四、回滚与安全

| 操作 | 影响 | 回滚 |
|---|---|---|
| 修改 `docker-compose.yml` 的 volumes | 容器重启、路径可见性变化 | 还原 compose 文件后 `docker compose up -d` |
| 迁移脚本 `--apply` | 写 `announcement_record` | 脚本自带备份表 `announcement_record_bak_<yyyymmdd>`，按脚本 rollback 参数还原 |
| 飞书凭证 | 仅影响通知渠道 | 清空对应键并保存 |

**禁止**：直接 `UPDATE` 生产库、`docker exec` 改容器内代码、为测试重启服务（除非在维护窗口内且已确认）。
