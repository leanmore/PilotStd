# 06 · 运行、部署与排障

> 本文件回答：怎么启动、数据在哪、日志在哪、坏了先看什么。  
> 原则：**开发/验证环境可以动手；生产环境只读排查，不直接改代码/UPDATE/重启做测试。**

---

## 一、三种运行形态

| 形态 | 启动 | 适用 | 入口 |
|---|---|---|---|
| **Docker Web** | `docker compose up -d`，访问 `http://<host>:9028` | 局域网多人 | FastAPI + Vue |
| **Win 桌面** | exe 或 `python main.py` | 单机 | PyQt6 |
| **CLI** | `python main.py --cli ...` | 批量/自动化/排障 | argparse |

---

## 二、Docker Web 部署

### 1. compose 关键点

`docker-compose.yml` 的核心：

```yaml
services:
  pilotstd:
    image: ghcr.io/leanmore/pilotstd:latest
    container_name: pilotstd
    ports:
      - "9028:9028"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./inbox:/inbox
      - ./standards:/standards
      - ./.env:/app/.env
      - ./output:/app/output
      - ./config:/app/config
    environment:
      - TZ=Asia/Shanghai
      - STANDARD_ROOT=/standards
      - PILOTSTD_MODEL_DIR=/app/data/models/ocr
```

### 镜像构建（`docker/Dockerfile`）

- 多阶段构建：builder 装依赖 → runtime 复制 `/install`；
- 运行用户：非 root `appuser`，entrypoint 用 `gosu` 降权；
- 健康检查：`HEALTHCHECK` 调 `/api/health`；
- 前端：镜像内必须有 `web/dist/index.html`，否则构建失败；
- `APP_VERSION` 由构建参数注入，部署版本以 `/api/health` 为准。

### 2. 目录/卷

| 容器路径 | 用途 |
|---|---|
| `/app/data` | SQLite、`config.json`、`.fernet_key`、备份、模型 |
| `/app/logs` | `app.log` 及轮转 |
| `/inbox` | 监控/投放目录 |
| `/standards` | 标准库根目录 |
| `/app/output` | 导出/生成文件 |
| `/app/config` | 配置文件 |

### 3. 首次启动

- 超级用户：环境变量 `SUPERUSER` / `SUPERUSER_PASSWORD`；
- 未设置密码时，启动日志中会输出自动生成的密码；
- 不要把 `SUPERUSER` 设为 `admin`（入口会拒绝）；
- 登录用 `POST /api/login`，拿 session cookie；静态 token 不是当前主路径。

### 4. 健康检查

```bash
curl -s http://<host>:9028/api/health
```

关键字段：

- `status`：`ok` / 异常；
- `version` / `schema_version` / `services.database` / `monitor_service` / `parser`；
- `checks.disk`：剩余空间；
- `checks.scheduler`：心跳时间/年龄；
- `checks.database_rw`：读写。

### 5. 日志

```text
logs/app.log
logs/app.log.1
logs/app.log.2
...
```

常用关键字：

```text
[MONITOR]       监控
扫描完成        解析结果
解析失败        未识别文件
查询完成        查询结果
归档进度/归档完成
移动成功/移动失败
SQL执行失败
notification / Telegram / wechat
```

---

## 三、Win 桌面

### 1. 启动

- 发布版：`PilotStd.exe`；
- 源码：`pip install -r desktop/requirements-win.txt`，`python main.py`。

### 2. 数据位置

- 源码运行：项目 `data/`（`pilotstd.db`、`config.json`、`.fernet_key`）；
- 打包运行：通常是 exe 同目录/用户数据目录（以实际配置为准）；
- 标准库/Inbox 路径由配置决定。

### 3. 可选 watcher

`watchdog.enabled` 默认 false。开启后：

- `FileWatcher` 只更新 `file_index`；
- **不归档、不查询、不下载**；
- 与 Docker 的 `monitor._on_file` 不是同一个东西。

---

## 四、CLI

### 1. 入口

```bash
python main.py --cli <command> ...
```

### 2. 常用命令

```bash
# 扫描
python main.py --cli scan /path/to/inbox

# 查询
python main.py --cli query -f numbers.txt

# 下载（从文件读标准号，跳过查询队列）
python main.py --cli download -f numbers.txt

# 规范化预览（不移动）
python main.py --cli normalize /path/to/file.pdf

# 归档
python main.py --cli organize --source /path/to/inbox

# 一键：扫描→查询→下载→归档
python main.py --cli auto /path/to/inbox

# 移动/过期/时效
python main.py --cli move /path/to/file.pdf --dry-run
python main.py --cli expire /path/to/file.pdf
python main.py --cli validity --force

# 任务/待确认/公告
python main.py --cli task --limit 20
python main.py --cli pending
python main.py --cli announce --since 2026-01-01
```

> 具体参数以 `pilotstd/cli/commands/__init__.py` 为准。

---

## 五、配置与数据路径

### 1. 配置文件

- Docker：`/app/data/config.json`；
- 源码/桌面：`data/config.json`（或用户目录）；
- 配置是点分隔 JSON；写入是“临时文件 + `os.replace`”原子替换；
- 保留 `config.json.bak` 写前备份。

### 2. 关键配置

| 键 | 作用 |
|---|---|
| `storage.root_dir` | 标准库根目录 |
| `storage.expire_folder` | “过期作废”目录名 |
| `storage.inbox_dir` / `watch_path` | Inbox |
| `scan.extensions` | 扫描扩展名 |
| `scan.skip_folders` | 跳过目录（含“过期作废”） |
| `query.use_cache` | 查询缓存 |
| `validity.auto_move_expired` | 是否允许 L2 后自动搬“过期作废” |
| `notification.aggregate_*` | 通知聚合窗口/上限 |
| `tasks.*_cron` | 定时任务 |

### 3. 数据库

- SQLite：`data/pilotstd.db`（WAL 模式，有 `-wal`/`-shm`）；
- 迁移：`pilotstd/core/db/migrations.py`，启动时按版本执行；
- 备份：`data/backups/`，或 `/api/backup/create`。

---

## 六、通知渠道

| 渠道 | 配置 | 备注 |
|---|---|---|
| 企业微信 | `notification.channels.wechat.*` | 支持 webhook / 应用卡片/文本 |
| Telegram | `notification.channels.telegram.*` | 429 限流常见 |
| 钉钉 | `notification.channels.dingtalk.*` | 模板卡片 |
| 飞书 | `notification.channels.feishu.*` | webhook |

排查：

1. 看 `notification_log`（event/channel/status/error_msg）；
2. 看渠道配置是否启用；
3. 看聚合窗口是否还没到；
4. 看静音时段；
5. 看 Telegram 429 / 企微 `errcode`。

---

## 七、备份与恢复

### 创建备份

- Web：`POST /api/backup/create`（**admin-only**，写审计）；
- 或直接复制 `data/pilotstd.db`（先停写/用 SQLite backup API 更稳）；
- 备份目录：`data/backups/`；
- **没有恢复 API**：恢复必须停服务后手工替换数据库文件，先备份当前 `data/`。

### 恢复

1. 停服务；
2. 备份当前 `data/`；
3. 用备份文件替换 `pilotstd.db`；
4. 启动，检查迁移版本/健康。

**不要**在生产上直接 `UPDATE` 数据来“修状态”；先备份，再走迁移/脚本。

---

## 八、排障矩阵

| 现象 | 先看 | 常见原因 |
|---|---|---|
| 文件没归档 | `/inbox` 是否还有文件；`[MONITOR] 未识别到标准号`；`file_index` 是否有记录 | 解析失败 / 目标已存在 / 监控未启动 |
| 解析失败 | `解析失败: ... error=no_match`；文件名 | 没有标准号 / 格式不支持 |
| 归档到错误目录 | `logical_code`、`get_folder_name`、`mover.normalize_filename` | 代号误判 / 空代号 / Word 重解析 |
| 状态不对 | `effect_status`、`file_index.status`、`standard_validity.status` | 查询结果与历史表不一致 |
| 没进“过期作废” | `effect_status` 是否废止；`validity.auto_move_expired` | 没有 L2 证据 / 开关关闭 |
| 通知没收到 | `notification_log`、渠道配置、静音/聚合 | 渠道失败 / 被聚合 / 静音 |
| 通知太多 | 是否有逐条通知；聚合键是否每次新批次 | 批次键不共享 / 零计数也发 |
| `database is locked` | 并发写、长事务、WAL | 写竞争；看 `Database` 重试 |
| `UNIQUE constraint failed` | `standard_validity` / `file_index` | SELECT+INSERT 竞争 |
| 服务不健康 | `/api/health`、磁盘、调度器心跳 | 磁盘满 / DB 不可写 / 调度器停 |

---

## 九、生产环境纪律

按 `AGENTS.md`：

- **禁止**直接修改容器内代码；
- **禁止**直接 `UPDATE` 生产数据库；
- **禁止**为测试重启生产服务；
- 所有修复先在开发/验证环境确认，再建议部署；
- 部署版本以 `/api/health` 返回的 `version` 为准，不看本地 tag。

---

## 十、自检

1. Docker 的核心卷有哪些？分别存什么？
2. `/api/health` 看哪几个字段？
3. Win 的 watcher 和 Docker 的 monitor 有什么区别？
4. 文件没归档，排查顺序是什么？
5. `notification_log` 里 `failed` 说明什么？
6. 生产环境为什么不能直接 UPDATE？

参考答案见 [`10-assessment.md`](10-assessment.md)。
