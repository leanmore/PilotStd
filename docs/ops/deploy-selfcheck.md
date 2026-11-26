# 部署与一键自检指南

> 适用：PilotStd 局域网 Docker 部署（本文示例为 `http://192.168.1.18:9028`）。
> 配套脚本：`scripts/ops/`（全部只读）；配套测试：`tests/ops/`。
> 相关文档：`docs/reference/health-check.md`（健康检查字段与状态码）、
> `docs/debt/00-global-issues.md` 的 G-32 / G-48（`mark_missing` 验收口径）。

**一句话**：部署完成后 5 分钟内跑 `python scripts/ops/probe_all.py --base-url http://192.168.1.18:9028`，
退出码 `0` 才算可以上线；`1` 看下面的阻断项清单；`2` 是连不上，先查网络/容器，不算失败。

---

## 一、5 分钟上手（复制粘贴即可）

```bash
cd D:\PilotStd

# 0) 参数自检（不联网，确认脚本可用）
python scripts/ops/probe_all.py --help

# 1) 一键跑全部（人读输出；这是唯一必跑命令）
python scripts/ops/probe_all.py --base-url http://192.168.1.18:9028

# 2) 需要 CI 消费时（单一 JSON，含每个探测的明细）
python scripts/ops/probe_all.py --base-url http://192.168.1.18:9028 --json > %TEMP%\deploy-selfcheck.json
```

只想跑其中一类时用 `--only`：

```bash
python scripts/ops/probe_all.py --only health
python scripts/ops/probe_all.py --only pending_paths,db_counts
```

单跑某个探测（排查时更常用，输出更细）：

```bash
python scripts/ops/probe_health.py        --base-url http://192.168.1.18:9028
python scripts/ops/probe_pending_paths.py --base-url http://192.168.1.18:9028 --max-items 50
python scripts/ops/probe_credentials.py   --base-url http://192.168.1.18:9028
python scripts/ops/probe_db_counts.py     --base-url http://192.168.1.18:9028
python scripts/ops/probe_batch1.py        --base-url http://192.168.1.18:9028
```

> **部署后第一件事**：跑 `probe_batch1.py`。它把《全站技术债与隐患总清单》批次 1 的
> 22 项「已修复待部署」逐条验证，直接给出「哪些已在生产生效、哪些还要人工看」。
> 可自动化项（端点 / 字段 / SQL）自动判定，人工项（渲染 / 目录 / 真实外发）
> 如实标 `unverified` 并写明原因，**不假装通过**。


**通用参数**（每个脚本都有）：

| 参数 | 作用 | 默认 |
|---|---|---|
| `--base-url` | 被测服务地址 | 先取 `config/docker_creds.json` 的 `base_url`，再退回 `http://192.168.1.18:9028` |
| `--json` | 只输出单一 JSON（CI 消费） | 关闭（人读表格） |
| `--strict` | 诊断项失败也计为阻断 | 关闭 |
| `--timeout` | 单请求超时秒数 | `10` |
| `--creds` | 凭据文件路径 | `config/docker_creds.json` |
| `--only`（仅 `probe_all`） | 只跑指定探测 | 全部 |
| `--max-items`（`probe_all` / `probe_pending_paths`） | pending 路径抽样条数 | `20` |
| `--allow-unconfigured-channels`（`probe_all` / `probe_credentials`） | 「渠道未启用且未配置」记为不适用 | 关闭（默认记为**无法验证**，不假装通过） |

---

## 二、退出码与三档判定

| 退出码 | 含义 | 处理 |
|---|---|---|
| `0` | 全部必跑项通过 | 可以上线 |
| `1` | 有失败项，或**必跑项无法验证** | 看「阻断项清单」，逐条处理 |
| `2` | 环境不可达（连接失败/超时/健康检查非 200·207） | **不算失败**；查网络、容器是否启动、IP 是否正确 |

每条结论的状态：

- `pass`：通过；
- `fail`：明确不通过（阻断）；
- `unverified`：**条件不足，无法验证**——不假装通过，需补齐条件（如缺 admin 凭据、密钥被掩码）；
- `skip`：本环境不适用（不阻断）。

等级 `必跑`（`required`）失败或无法验证 → 阻断；`诊断`（`advisory`）失败默认不阻断（`--strict` 才阻断）。

---

## 三、必跑项（阻断上线）与通过判据

### 3.1 版本与 schema 一致性 —— `probe_health.py`

| 检查名 | 通过判据 |
|---|---|
| `health.status` | `GET /api/health` 返回 **200** 且 `status=ok`。**207 degraded 也算不通过**（部署验证要求全绿） |
| `health.disk` | `checks.disk.ok=true`（剩余 ≥ `threshold_mb`，默认 500MB） |
| `health.scheduler` | `checks.scheduler.ok=true`（心跳 ≤180s） |
| `health.database_rw` | `read=true` 且 `write=true` |
| `version.consistency` | `/api/system/version` 的 `version` == 仓库 `VERSION` == `pilotstd.__version__` |
| `schema.consistency` | `/api/health` 的 `schema_version` == `pilotstd/core/db/_constants.py` 的 `CURRENT_SCHEMA_VERSION` |
| `version.deployed_commit`（诊断） | `/api/health` 的 `version` 是 40 位 sha 时，该 commit 在本地仓库存在且是 `HEAD` 的祖先（=镜像里跑的就是这份代码） |

> `health.version` 来自 Dockerfile 的 `ARG APP_VERSION`，本部署注入的是 git sha；
> 语义版本以 `/api/system/version` 与 `VERSION` 为准（`AGENTS.md` §一）。

### 3.2 `mark_missing` 路径映射 / 挂载 / 端点 —— `probe_pending_paths.py`

| 检查名 | 通过判据 |
|---|---|
| `auth.admin` | 凭据文件里的账号能登录且角色为 `admin`（`POST /api/pending/mark-missing` 与 `POST /query` 都要 admin） |
| `mounts.scan_paths` | 能读到 `GET /api/settings` 的 `scan_paths`（`/api/settings` 的 storage 段）（本部署为 `/inbox`、`/standards`） |
| `mounts/inbox`、`mounts/standards` | `GET /api/files?path=...` 返回 200 且能列出条目（404 = 目录未挂载） |
| **pending.rows** | 统计出 pending 总数、带路径条数与已标 `file_missing` 条数（信息项） |
| **pending.path_mapping** | **抽样核对**（抽样范围=**所有带路径的 pending 行**，与 `mark_missing_files` 的 `WHERE status='pending'` 同口径）：每条 `file_path` ①必须落在配置的扫描根下（否则是**路径映射错误**）②在**同一相对路径的其他扫描根**下也找不到（否则是**假 missing**）。两项都为 0 才通过 |
| **pending.file_missing_has_path**（`probe_db_counts`） | `reason=file_missing` 但 `file_path` 为空的行数 = 0（空路径应归为 `no_file`） |
| **`endpoint.mark_missing`** | `OPTIONS /api/pending/mark-missing` 返回 **405 且 `Allow` 含 `POST`** = 端点已部署。404 = 未部署（需更新镜像）；401/403 = 权限不足无法判断 |
| `scheduler.pending_missing_check`（诊断） | `GET /api/scheduler/status` 的 jobs 里有 `pending_missing_check`（每日 03:30，配置键 `pending.mark_missing_cron`） |
| **pending.mass_delete_guard** | 按抽样缺失率外推到全表，推算 `_is_mass_delete_anomaly` **不会**整轮跳过（≥50 行且缺失 ≥90% 会跳过）。一旦会跳过则判**失败**：此时定时任务与端点跑完都不会标记任何行；若挂载与路径映射都已确认正常，脚本会明确标注这是**保护误报**（数据真的缺失） |

> **为什么用 OPTIONS 判端点存在性**：该端点无请求体，**空 body 的 POST 也会真的执行标记**，
> 所以脚本绝不发 POST；`405 + Allow: POST` 已经能证明路由已注册（实测语义，见 §六 排查表）。

### 3.3 通知渠道凭证 —— `probe_credentials.py`

| 检查名 | 通过判据 |
|---|---|
| `notification.enabled` | 全局开关 `enabled=true` |
| `feishu.credentials` | `app` 形态齐全：`app_id` + `app_secret` + `receive_id`（= 测试群 chat_id）；或 `webhook` 形态有 `webhook_url`。**渠道已启用却缺字段 → fail**；未启用 → unverified（不假装通过） |
| `feishu.chat_id` | app 形态下必须有 `receive_id`（chat_id）；缺失时可用 `GET /api/notification/menu/chats?channel=feishu` 自动发现 |
| `wechat.credentials` | `app` 形态齐全：`corpid` + `agentid` + `corpsecret`；或有群机器人 `webhook_url` 兜底 |
| `telegram.credentials` | `bot_token` + `chat_id` 都有值 |
| `feishu.connectivity` / `wechat.connectivity` / `telegram.connectivity`（诊断） | 只做**令牌换取/getMe**（不发送任何消息）。**密钥被服务端掩码（`***`）时只能标 unverified**，需在容器内自检 |

> 群机器人 `webhook_url` **不探测**：任何请求都会真的往群里发消息。请用管理端「测试发送」人工确认。

### 3.4 统计表对账 —— `probe_db_counts.py`

| 检查名 | 通过判据 |
|---|---|
| `db.query` | 12 条只读 SQL 全部执行成功 |
| **pending.status_sum** | `pending_lookup` 各 `status` 之和 = 总行数 |
| **pending.file_missing_has_path** | `reason=file_missing` 且 `file_path` 为空的行数 = 0 |
| `favorite_downloads.orphan` | `favorite_downloads.favorite_id` 指向不存在收藏的行数 = 0 |
| `announce.stats_total` | `/api/announce/stats` 的 `total.all` = SQL `COUNT(*)` |
| `announce.stats_matched` | `/api/announce/stats` 的 `matched` = SQL `matched=1` 计数 |
| `file_index.status_sum` | `file_index` 各 `status` 之和 = 总行数 |
| **pending.api_vs_sql**（诊断） | `/api/pending` 返回条数 = SQL `status='pending'` 行数 |
| `favorites.api_vs_sql`（诊断） | `/api/favorites` 返回条数 ≤ `user_favorites` 总行数（接口按用户过滤） |
| `announce.fresh_duplicates`（诊断） | `data_state='fresh'` 的 `(source_site, announce_no, standard_number)` 无重复（`stale` 行按设计保留历史版本，允许重复） |
| `file_index.api_stats`（诊断） | `/api/stats` 四项（现行/废止/待确认/即将实施）之和 ≤ `file_index` 总行数 |
| `notification_log.api_vs_sql`（诊断） | `/api/notification/logs` 的 `total` = SQL `COUNT(*)` |

---

## 四、建议跑（诊断，不阻断）

```bash
# 只跑诊断项，且让诊断失败也阻断（上线前更严）
python scripts/ops/probe_all.py --base-url http://192.168.1.18:9028 --strict

# 抽样更多 pending 路径（默认 20 条；想全量核对就调到 pending 总数以上，如 500）
python scripts/ops/probe_pending_paths.py --base-url http://192.168.1.18:9028 --max-items 500

# 只看某个渠道
python scripts/ops/probe_credentials.py --base-url http://192.168.1.18:9028 --channel feishu
```

诊断项包括：`health.services`、`version.deployed_commit`、`scheduler.pending_missing_check`、
各渠道连通性、`channels.enabled`、`favorites.api_vs_sql`、
`announce.fresh_duplicates`、`file_index.api_stats`、`notification_log.api_vs_sql`。

---

## 五、只读保证（可审计）

脚本对外只发三类请求：

1. `GET` / `OPTIONS`——纯读；
2. `POST /api/login`——只创建会话，不改业务数据；
3. `POST /query`——只读 SQL 端点，**发送前强制校验**语句必须以 `SELECT`/`PRAGMA`/`EXPLAIN` 开头、
   单条、且不含 `INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/REPLACE/VACUUM`（`_probe_common._assert_read_only_sql`）。

其余写方法在**发请求之前**就抛 `WriteBlockedError`（白名单常量 `WRITE_ALLOWLIST`）。
`tests/ops/test_probe_scripts.py` 有专门用例断言「`mark_missing` 只被 OPTIONS 探测、从未被 POST 执行」。

**凭证安全**：`config/docker_creds.json` 含中文注释，按行正则提取（不整体 `json.loads`）；
所有输出经 `mask_secret()` 脱敏为 `ab***`；密码/令牌/secret **绝不**出现在报告与 JSON 里。

---

## 六、常见失败排查表

| 现象 | 含义 | 处理 |
|---|---|---|
| 退出码 **2** + `环境不可达：... ConnectionError/Timeout` | 网络或容器不可用 | 确认容器在跑、IP/端口正确、本机与 `192.168.1.18` 同网段；再 `curl http://192.168.1.18:9028/api/health` |
| `health.status` = **207 degraded** | 磁盘 <500MB 或调度器心跳 >180s | 看 `checks.disk.free_mb` / `checks.scheduler.age_seconds`；清磁盘或查调度线程 |
| `health.status` = **500 down** | 数据库读写失败 | 容器日志查 `database is locked`；确认数据目录可写 |
| `health.status` = **403** | 生产环境外网访问被拒（仅允许 RFC1918） | 从内网发起探测；这是预期防护 |
| `schema.consistency` 失败 | 服务端 schema < 代码库 | 镜像未执行最新迁移：重启容器触发迁移，或确认镜像版本 |
| `version.consistency` 失败 | `/api/system/version` ≠ `VERSION` | 镜像与代码不同源：重新构建并注入正确 `APP_VERSION` |
| `endpoint.mark_missing` = **404** | 端点未部署（旧镜像） | 更新镜像（代码已实现，见 G-48）；不要以为是代码问题 |
| `endpoint.mark_missing` = **401/403** | 权限不足，无法判断 | 用 admin 账号；检查 `config/docker_creds.json` 的 `username`/`password` |
| `endpoint.mark_missing` = **405 但 Allow 只有 GET** | 命中的是 SPA 回退路由 | 同上：端点未部署，更新镜像 |
| `auth.admin` = unverified | 登录失败或角色非 admin | 确认凭据未过期；`POST /api/login` 返回的 `role` 必须是 `admin` |
| **pending.path_mapping** 报**映射错误** | pending 的 `file_path` 不在 `/api/settings` 的 `scan_paths`（storage 段）下 | 核对扫描根配置与历史路径来源；**不要**直接跑 mark_missing |
| **pending.path_mapping** 报**假 missing** | 文件其实还在（另一扫描根下有同名） | 先修路径映射/镜像逻辑，再谈标记 |
| `mounts/inbox` = **404** | `/inbox` 未挂载或目录不存在 | 检查 `docker-compose.yml` 的 volumes 与宿主机目录权限 |
| **pending.mass_delete_guard** 提示「会整轮跳过」 | 缺失 ≥50 行且 ≥90%，`mark_missing_files` 保护性跳过，跑完什么都不会变 | 先看 `mounts/*` 与 **pending.path_mapping**：都通过说明是**保护误报**（数据真的缺失），需维护窗口内人工处理（如 `mark_missing_files(db, protect=False)`），或先清理这批 pending；任一不通过则先修挂载/路径映射 |
| `feishu.credentials` = unverified（未启用） | 飞书没配、也没启用 | 要启用就补 `app_id`/`app_secret`/`receive_id`；不用就加 `--allow-unconfigured-channels` |
| 各渠道 `*.connectivity` = unverified（`***`） | 服务端回显掩码，拿不到明文密钥 | 在容器内自检，或临时用明文凭证单跑；**不要**把明文写进仓库 |
| `favorite_downloads.orphan` > 0 | 下载表有孤儿行 | 只读排查：`SELECT * FROM favorite_downloads d LEFT JOIN user_favorites f ON f.id=d.favorite_id WHERE f.id IS NULL`；修复属数据治理，需窗口 |

---

## 七、脚本与测试清单

| 文件 | 职责 |
|---|---|
| `scripts/ops/_probe_common.py` | 凭据读取（按行 + GB18030 容错）、只读 HTTP 客户端（写方法拦截）、结果汇总、退出码、`--json` |
| `scripts/ops/probe_health.py` | 版本 / schema / 服务健康 |
| `scripts/ops/probe_pending_paths.py` | `mark_missing` 路径映射 + `/inbox` 挂载 + 端点存在性（OPTIONS）+ 调度任务 |
| `scripts/ops/probe_credentials.py` | 飞书/企微/Telegram 凭证齐全性 + 连通性（不发消息） |
| `scripts/ops/probe_db_counts.py` | 统计表对账（12 条只读 SQL + 接口口径交叉核对） |
| `scripts/ops/probe_all.py` | 一键跑全部并汇总（不可达时短路，退出码 2） |
| `tests/ops/test_probe_scripts.py` | 每个 probe 的「通过 / 检测到问题 / 环境不可达」三路径 + 只读性反证 |

本地验证：

```bash
python -m pytest tests/ops -q
python scripts/ops/probe_all.py --help
```

---

## 七-A、批次 1 人工验收清单（11 项）

见 [batch1-manual-checklist.md](batch1-manual-checklist.md)：
probe_batch1.py 自动验证 10 项后，剩余 11 项需人工在浏览器/真实环境确认，
逐项给出「怎么做 → 看什么 → 判据」。全部完成后批次 1 的 22 项即可闭合。

## 七-B、数据迁移（需授权，**写库**）��

见 [batch2-data-migration.md](batch2-data-migration.md)：
G-28 / G-33 / G-35 的「演练 → 取证 → 授权 → 全量 → 回滚」完整流程。
**这不是只读探测**，必须在维护窗口内由负责人授权后执行。

## 八、已知无法在探测侧验证的点（如实说明）

| 点 | 原因 | 需要的条件 |
|---|---|---|
| 渠道**真实连通**（飞书/企微/Telegram） | 服务端回显密钥为掩码 `***`，探测侧拿不到明文 | 容器内自检，或提供明文凭证单独跑 |
| 群机器人 `webhook_url` 连通性 | 任何请求都会真的往群里发消息 | 用管理端「测试发送」人工确认 |
| `mark_missing` **实际执行效果** | 执行即写库（`UPDATE pending_lookup`），属生产写操作 | 维护窗口内由管理员触发，之后用 `probe_pending_paths.py` 复核 `reason` 变化 |
| pending 路径**全量**核对 | 逐条列目录开销大（默认抽样 20 条，父目录有缓存） | `--max-items 500`（或更大）全量核对 |
| `announcement_record` 历史重复 | `stale` 行按设计保留历史版本，重复是预期 | 只看 `data_state='fresh'`（脚本已如此判定） |

---

## 九、本仓库当前实测记录（2026-11-23，`http://192.168.1.18:9028`）

`python scripts/ops/probe_all.py --base-url http://192.168.1.18:9028` → **退出码 1**（3 条阻断项）。
其余 33 项通过，均为真实输出，可作为「探测确实能发现问题」的样例：

| 结论 | 事实 | 说明 |
|---|---|---|
| `health.*` 8 项全 PASS | `/api/health` 200 ok；`version=0.206.0`、`schema_version=76`；磁盘 125491.9 MB；心跳 18.6s | 镜像 `a1090067` 是 `HEAD` 的祖先，schema 与 `CURRENT_SCHEMA_VERSION=76` 一致 |
| **pending.path_mapping** PASS | pending 61 条（全部带路径），抽样 20 条全部**真缺失** | `/inbox`、`/standards` 均可列目录，扫描根配置为这两个 |
| `endpoint.mark_missing` PASS | `OPTIONS /api/pending/mark-missing` 返回 405 `Allow: POST` | 端点已部署，且**未执行任何标记** |
| ****pending.mass_delete_guard** FAIL** | pending 61 条路径**全部不存在**（61/61，缺失率 100%） | 触发 `_is_mass_delete_anomaly`（≥50 行且 ≥90%）→ `mark_missing_files` 会整轮跳过。挂载与路径映射都已独立核对通过，故这是**保护误报**：需要维护窗口内 `protect=False` 处理，或先清理这批 pending |
| **`feishu.credentials` UNVERIFIED** | 飞书 `app_id`/`app_secret`/`receive_id` 全空且 `enabled=false` | 渠道未启用，缺凭证不阻断但**不判通过**；要启用需补齐（G-37 的 `GET /api/notification/menu/chats?channel=feishu` 可自动发现 chat_id） |
| **`favorite_downloads.orphan` FAIL** | 3 条孤儿行（id 137/138/139 → `favorite_id` 指向已不存在的收藏；`user_id` 18/19/21 在 `users` 表中不存在） | 遗留数据；属数据治理，需维护窗口，**不要**在验证时顺手删 |
| `wechat/telegram.credentials` PASS、`*.connectivity` UNVERIFIED | 凭证齐全；密钥被服务端掩码 `***` | 连通性需容器内自检（见 §八） |
| 对账 12 项 | pending 633=633；announce 233933=233933、matched 844=844；file_index 776=776；notification_log 2600=2600 | 口径全部自洽 |

> 提醒：`endpoint.mark_missing` 在**未登录**时会返回 401/403（无法判断），未登录时任何未知
> `/api/*` 路径也会因 SPA 回退返回 `405 Allow: GET`——所以判「已部署」只认 `405 + Allow 含 POST`。

### 2026-11-25 生产实测追加

**① `favorite_downloads.orphan` → 已清理（0）**

| 阶段 | 事实 |
|---|---|
| 清理前 | 3 条孤儿行（id **137/138/139**，`favorite_id` 指向不存在的收藏，`user_id` 18/19/21 也不存在）；表总数 142 |
| 删除条件 | `id IN (137,138,139) AND favorite_id NOT IN (SELECT id FROM user_favorites)`（WHERE 限定 + 二次校验孤儿条件） |
| 删除后 | 剩余孤儿行 **0**；表总数 142 → **139**（减 3，符合预期） |
| 回滚 | 删除前整行快照已保存（记录见本轮交付），按快照 INSERT 即可恢复 |
| 影响 | 仅这 3 条无效下载记录；未触及 `user_favorites` / 文件索引 |

**② `superseded_by` 方向纠正（G-28/33/35）→ dry-run 完成，待规则拍板**

- 生产只读实测：`announcement_record` **233,933** 行，`superseded_by` 非空 **30,890** 行，
  **待改动 24,969 行 / 将清除倒退值 26,191 条**；
- **关键风险**：distinct 目标旧标准号 25,757 个中，**15,493 个（60.2%）在表内不存在**
  → 按现行规则直跑将丢失 **15,755 条「被替代」关系**（15,163 行受影响）；
- 详细口径、样本与三个可选规则见 `docs/plans/2026-11-25-c3-dryrun-superseded.md`；
- **结论：`--apply` 需在规则确认后执行**（推荐方案 A：目标行存在才清除，零丢失）。

## 十、v0.207.0 部署后专项验收（2026-11-26 新增）

> 本版本一次性合入了批次 9/10/11/12/13 与发布机制修复。部署后按本清单逐项复验（只读）。

### 10.1 版本与发布（必需）

| 检查 | 期望 |
|---|---|
| `GET /api/health` 的 `version` | 镜像 sha（本次为 `4a4f9659…`） |
| `GET /api/system/version` 的 `version` | **`0.207.0`**（不再是 0.206.0） |
| 远端 tag | `v0.207.0` 指向 main 提交（非孤儿） |

### 10.2 批次 9 通知（P0）

| 检查 | 期望 |
|---|---|
| TG 带 link 事件（7 个）真实发送 | 无 `can't parse entities` 400、不整条丢失 |
| 企微卡片（`web_base_url` 已配置） | 返回 `errcode=0`；不降级为文本 |
| 卡片被拒时的降级 | `msgtype=markdown`（不是把 markdown 源码当 text 发） |
| 聚合通知 | 日志 `event_type` 为真实事件名；首行不是裸级别前缀 |

### 10.3 批次 10 编号识别（P1）

| 检查 | 期望 |
|---|---|
| `ASME PTC 4-2013` / `ASME CSD-1-2024` | 解析出 `num_prefix=PTC/CSD`，路由 `asme`（不落 `ahbz/njbz365`） |
| `API SPEC 6D-2021` / `API TR 938-C` / `API 579-1/ASME FFS-1` | 后缀/part 保留，路由 `api_webstore` |
| 离线冒烟 | `python scripts/smoke_adapters.py` 输出与 A2 报告一致 |

### 10.4 批次 11 状态口径（P0）

| 检查 | 期望 |
|---|---|
| `GET /api/standards/status?status=未生效` | 返回 **30 条**（= 即将实施 20 + C3 清洗并入 10；不是 776 全表） |
| 同上，与 `?status=即将实施` / `upcoming` | **结果集完全一致** |
| 非法值（如 `?status=faq`） | **400**（不再静默返回全表） |
| `GET /api/stats` | `expired=174 / upcoming=30 / current=572`（C3 清洗后未生效已并入即将实施） |

### 10.5 批次 12 数据治理（已执行，复验）

| 检查 | 期望 |
|---|---|
| `file_index` 状态分布 | 无 `未生效` 行（已清洗为 `即将实施` 30 条） |
| `superseded_by` 方向 | 「方向倒退且目标存在」的残留值 = 0 |
| `favorite_downloads` 孤儿行 | 0 |
| `notification_log` 归属 | `user_id=1` 仅剩真实用户动作（14 条 `user_activity`） |
| `pending` 文件缺失 | `mark-missing(protect=false)` 已执行（checked 61 / updated 28 / forced） |

### 10.6 探针基线（部署后应达到）

```bash
python scripts/ops/probe_all.py --base-url http://192.168.1.18:9028
python scripts/ops/probe_batch1.py --base-url http://192.168.1.18:9028
```

期望：`health 8/8`、`db_counts 13/13`、`batch1 10 通过/0 失败`；
`pending` 的 `mass_delete_guard` 检查因已完成标记不再作为阻断（如仍报 fail，按 §七-B 数据治理处理）。

### 10.7 一键验收脚本

```bash
python scripts/ops/probe_v0207.py --base-url http://192.168.1.18:9028
```

该脚本**只读**，自动核对 §10.1-10.5 的 11 项（版本 sha / system_version=0.207.0 /
未生效与即将实施结果集相等且非全表 / 非法值 400 / file_index 无未生效 / 收藏无孤儿 /
A-40 归零 / stats expired≥170 / 四桶守恒），退出码 0 = 全绿。

### 10.8 v0.207.1 实测结果（2026-11-26 18:35，生产 `http://192.168.1.18:9028`）

| 探测 | 结果 | 说明 |
|---|---|---|
| `probe_v0207.py` | **11 / 11 通过**，退出码 0 | `health.version=e6107c3e…`、`system_version=0.207.1`、四桶守恒、A-40/C3 复验全绿 |
| `probe_all.py --allow-unconfigured-channels` | **45 通过 / 0 失败 / 17 无法验证**，退出码 0 | `health 8/8`、`pending_paths 9/9`、`db_counts 13/13`、`batch1 10 通过/0 失败` |
| `probe_batch1.py` | **10 通过 / 0 失败 / 14 无法验证**，退出码 0 | 14 项为渲染/目录/真实外发类，需人工 |
| 企微真发（T-40 配合） | `POST /api/notification/test-event` → `{"ok":true}`；`notification_log id=4663 status=success error_msg=""` | 平台侧 `errcode=0`；卡片/降级形态由真机确认 |

**重要修正（本次实测发现并已修）**：批次 12 维护窗口后，缺失行已全部标 `file_missing`，
`mark_missing` 的挂载保护仍会「整轮跳过」但**已无待更新行**（幂等 no-op）。
`probe_pending_paths` 原判据把它当阻断（fail），现改为：**全部已标记 → PASS**；
仅当「仍有未标记缺失行」时跳过才判 fail。回归 `tests/ops/test_probe_scripts.py`（30 例）。
