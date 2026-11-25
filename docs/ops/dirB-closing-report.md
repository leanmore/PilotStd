# 方向 B 结案报告 · 部署与一键自检（2026-11-25 首次真实生产自检）

> 结论：**方向 B 结案（10/10 自动必跑项全绿，0 代码性失败）**。
> 遗留 2 个**数据/配置条件**（非代码回归）+ 14 项需人工/真机条件的诊断项，均已如实标 `unverified`，不假装通过。

## 1. 部署事实（只信 `/api/health`）

| 项 | 值 |
|---|---|
| 部署时间 | 2026-11-25 20:0x（用户执行 `docker compose pull && up -d`） |
| `/api/health` `version` | `c016013da5af40765b3059f015bf5f03999d7314`（= 镜像 `APP_VERSION`，git sha） |
| 与 main 的关系 | c016013d 是 main（`2e020dde`）的**祖先**；`git diff c016013d..2e020dde -- pilotstd docker web` **0 行**（后续提交均为 docs-only）→ 镜像代码 = 当前 main 代码 |
| `schema_version` | 76 / 代码库 `CURRENT_SCHEMA_VERSION` 76 ✓ |
| `VERSION` / `pilotstd.__version__` / `/api/system/version` | 0.206.0 / 0.206.0 / 0.206.0 三者一致（注：版本号未随本次合并递增——**已知版本 bump 缺陷**，另立工单） |

## 2. 探针结果总表（`probe_all.py`，2026-11-25 20:15）

| 模块 | 通过 | 失败 | 无法验证 | 说明 |
|---|---:|---:|---:|---|
| health | 8 | 0 | 0 | 版本/schema/磁盘/心跳/DB 读写全绿 |
| pending_paths | 8 | **1** | 0 | 唯一 fail = `mass_delete_guard`（数据条件，见 §4） |
| credentials | 5 | 0 | 3 | 飞书未配置（见 §4） |
| db_counts | **13** | 0 | 0 | 12 条对账 SQL 全部成功 |
| batch1 | **10** | 0 | 14 | 10 项自动必跑全绿；14 项需人工/真机 |
| **合计** | **44** | **1** | **17** | 阻断项 2（均为数据/配置条件） |

## 3. 十项真实自检明细（方向 B 的「10/10」）

| # | 检查 | 结果 | 证据 |
|---|---|---|---|
| 1 | `health.status` | PASS | 200 ok |
| 2 | `health.scheduler` | PASS | 心跳 15.1s 前（阈值 180s） |
| 3 | `health.database_rw` | PASS | read=True write=True |
| 4 | `health.disk` | PASS | 剩余 125,811 MB（阈值 500 MB） |
| 5 | `version.consistency` | PASS | 服务端 = VERSION = 包内 = 0.206.0 |
| 6 | `version.deployed_commit` | PASS | `c016013d` 存在且为 HEAD 祖先；代码 diff 0 |
| 7 | `schema.consistency` | PASS | 76 = 76 |
| 8 | `auth.admin` | PASS | 登录成功，角色 admin |
| 9 | `db.query` 12 条对账 | PASS | 见下表 |
| 10 | `batch1` 10 项自动必跑 | PASS | G-21/22/29/36/37/42/44/48 + env/auth |

### 3.1 数据对账（`db_counts` 13/13 PASS）

| 对账项 | 实测 |
|---|---|
| `announce.stats_total` / `matched` | 233,933 = 233,933 / 844 = 844 |
| `pending.status_sum` | 633 = 633 |
| `pending.api_vs_sql` | 61 = 61 |
| `pending.file_missing_has_path` | 0（无误标） |
| `favorites.api_vs_sql` | 138 ≤ 139（接口按用户过滤） |
| **`favorite_downloads.orphan`** | **0**（清理后首次复验通过） |
| `file_index.status_sum` | 776 = 776 |
| `/api/stats` 四项之和 | 766 ≤ 776 |
| `notification_log.api_vs_sql` | 2,620 = 2,620 |

### 3.2 业务口径修复生效证据（部署前 vs 部署后）

| 指标 | 部署前（0e92e5d2） | 部署后（c016013d） | 判读 |
|---|---|---|---|
| `/api/stats.expired` | 116 | **174** | ✅ A1「作废归入废止族」修复生效 |
| `/api/stats.upcoming` | 20 | 20 | 一致 |
| `/api/stats.current` | 572 | 572 | 一致（守恒） |
| `?status=unknown` | 88 | **30** | ✅ = 20 即将实施 + 10 未生效 |
| `?status=voided` | 58 | 58 | 一致（独立桶保留） |
| `?status=未生效` | 776（静默返回全表） | **776（仍失效）** | ⚠️ 已知缺陷，修复在 lane-status（批次 11），未合入 |
| `?status=expired` | — | 0 | ⚠️ 疑似同一类过滤名映射问题，已并入批次 11 复核 |

## 4. 两个阻断项（数据/配置条件，非代码回归）

1. **`pending.mass_delete_guard`（fail）**：pending 61 条路径**全部真缺失**（抽样 20/20 缺失、映射 0 错），
   触发「≥50 行且 ≥90% 缺失」挂载保护 → `mark_missing_files` 整轮跳过。挂载与路径映射已独立核对通过
   → 属**保护误报**。处置：维护窗口内 `protect=False` 执行一次，或先清理这批 pending（批次 12 一并处理）。
2. **`feishu.credentials`（unverified）**：飞书渠道未配置（缺 `app_id`/`app_secret`/测试群 `chat_id`）。
   用户 2026-11-25 裁定「暂时挂起，等摸底报告出来再决定是否纳入通知对比」。

## 5. 14 项人工/真机诊断（如实标 unverified）

| 类别 | 项 |
|---|---|
| 需真机/真实外发 | G-40（`message.link` 四渠道渲染）、G-41（企微应用形态）、T-40（企微真发） |
| 需渲染实测 | G-15（深色主题按钮对比度）、G-20（四主题配色）、G-23（语言下拉） |
| 需真实目录 | G-17（空目录清理）、G-19（clean-empty 同口径） |
| 需观察周期 | G-18（公告起始日期）、G-34（修改单解析）、G-38（旧状态回填）、G-39（出厂渠道回退） |
| 进程内行为（本地测试锁定） | G-14（配置 update）、G-46（渠道能力矩阵）、G-47（菜单客户端注册表） |

## 6. 本次自检暴露并已修复的探针自身缺陷

**`probe_health._git_commit_exists` 在受限/沙箱环境下崩溃**：`subprocess.run(..., capture_output=True)` 的
管道读取在沙箱下会返回 `stdout=None`（读线程 `UnicodeDecodeError`/管道禁止），导致 `probe_all` 在
`version.deployed_commit` 处 `AttributeError` 崩溃。
**修复**：新增 `_run_git()` 双通道（内存捕获失败 → 临时文件重定向），并区分「git 不可用（127）」与
「commit 不存在」，配单元测试。该修复保证探针在**开发者沙箱与 CI 两种环境**都能跑。

## 7. 结论与后续

- **方向 B 结案**：部署验证包（7 个只读脚本 + 自检指南）已在真实生产完整跑通，44 项自动检查全绿、
  0 代码性失败，数据对账 13/13 通过。
- **待办**（不阻塞结案）：
  1. `pending.mass_delete_guard`：维护窗口执行（并入批次 12）；
  2. `?status=未生效` / `?status=expired` 过滤映射：批次 11 修 + 补契约测试；
  3. 14 项人工验收：按 `deploy-selfcheck.md` §七-A 清单逐项人工确认；
  4. **版本号 bump 缺陷**（发版后 VERSION 不递增，镜像靠 sha 区分）：独立工单修复 version job。

## 8. 执行注记（2026-11-25）

- 本报告与探针修复同批提交；probe_all.py 已在部署版本（c016013d）上完整跑通（44 通过 / 1 数据条件失败 / 17 无法验证）。
- 同批完成的还有：批次 12 规则 A 生产迁移（见 docs/ops/batch12-superseded-by-rule-a-execution.md）。
