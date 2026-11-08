# W2-A 执行报告（第二轮第一批）

> 工单：W2-A｜执行时间：2026-11-08 10:19–10:35（Asia/Shanghai）
> 工作区：`D:\PilotStd`｜基线 HEAD：`d1d871ea`
> 权限边界：只处理工单列出的文件；未修改任何文件内容（`CLOSEOUT/review_log.csv` 仅追加备注）；未执行 `git add / commit / push`；未连接数据库、未访问网络、未启动服务。

---

## 前置检查

| 检查项 | 结果 |
|---|---|
| `git status` | 仅 `?? CLOSEOUT/`（第一轮产物，预期内）；无 tracked 修改、无暂存内容 → 继续执行 |
| `docs/.local` 存在 | 是；已创建 `docs/.local/archive/2026-11-08/` |
| 工单列出的 32 条路径 | 全部存在，缺失 0 |
| 凭证文件 git 跟踪 | `git ls-files` 未命中（未跟踪）→ 允许删除 |
| web 生成物暂存状态 | `git diff --cached` 为空 → 允许删除 |

> 说明：`?? CLOSEOUT/` 是第一轮按要求产出的目录，不属于“意外未提交改动”；已记录后继续。

---

## 第 1 步：移动 17 份新增归档

**结果：17 份全部移动成功，0 失败。**

| # | 源路径 | 目标路径 |
|---:|---|---|
| 1 | `docs/plans/2026-10-29-stage6-record.md` | `docs/.local/archive/2026-11-08/docs/plans/2026-10-29-stage6-record.md` |
| 2 | `docs/plans/batch5-terminology-design.md` | `docs/.local/archive/2026-11-08/docs/plans/batch5-terminology-design.md` |
| 3 | `docs/plans/moviepilot-investigation/02-pilotstd-gap-analysis.md` | `docs/.local/archive/2026-11-08/docs/plans/moviepilot-investigation/02-pilotstd-gap-analysis.md` |
| 4 | `docs/analysis/http-requests-inventory.archived.md` | `docs/.local/archive/2026-11-08/docs/analysis/http-requests-inventory.archived.md` |
| 5 | `docs/analysis/v1_vs_v2_routing_comparison.md` | `docs/.local/archive/2026-11-08/docs/analysis/v1_vs_v2_routing_comparison.md` |
| 6 | `docs/records/2026-10-24-doc-audit.md` | `docs/.local/archive/2026-11-08/docs/records/2026-10-24-doc-audit.md` |
| 7 | `docs/research/2026-11-01-moviepilot-notification-design.md` | `docs/.local/archive/2026-11-08/docs/research/2026-11-01-moviepilot-notification-design.md` |
| 8 | `scripts/audit_openapi_frontend.py` | `scripts/archive/audit_openapi_frontend.py` |
| 9 | `scripts/clean_old_announcements.py` | `scripts/archive/clean_old_announcements.py` |
| 10 | `scripts/cleanup_announcement_data.sql` | `scripts/archive/cleanup_announcement_data.sql` |
| 11 | `scripts/compare_v1_v2_routing.py` | `scripts/archive/compare_v1_v2_routing.py` |
| 12 | `scripts/probe_announcement_html.py` | `scripts/archive/probe_announcement_html.py` |
| 13 | `scripts/probe_cssn_api.py` | `scripts/archive/probe_cssn_api.py` |
| 14 | `scripts/probe_miit_api.py` | `scripts/archive/probe_miit_api.py` |
| 15 | `scripts/probe_ncha_api.py` | `scripts/archive/probe_ncha_api.py` |
| 16 | `scripts/update_docs.archived.py` | `scripts/archive/update_docs.archived.py` |
| 17 | `data/audit_announcement_results.csv` | `docs/.local/archive/2026-11-08/data/audit_announcement_results.csv` |

**计数说明（与工单“28 份”的差异）**：

| 口径 | 数量 | 说明 |
|---|---:|---|
| 工单标题 | 28 | 第一轮提案中的“新增归档”含 9 份 `tests/verify_downloads/` 与 2 份已在 `scripts/archive/` 的脚本 |
| 实际物理移动 | **17** | 本步清单 17 份 |
| 未移动但已归档 | 2 | `scripts/archive/README.md`、`scripts/archive/migrate_preferences.py` 本就在目标目录，无需移动 |
| 未移动（工单未列） | 9 | `tests/verify_downloads/` 的 9 份 PDF/HTML 证据；工单未列，按“只处理列出文件”保持原地 |

- `docs/.local/archive/2026-11-08/` 当前 8 个文件（7 文档 + 1 CSV）；
- `scripts/archive/` 当前 11 个文件（原有 2 + 本次 9）。

---

## 第 2 步：归档 7 份过期文件（+1 份原地）

**结果：7 份移动成功，0 失败；`MIGRATION.md` 原地不动。**

| # | 源路径 | 目标路径 |
|---:|---|---|
| 1 | `STATUS.md` | `docs/.local/archive/2026-11-08/STATUS.md` |
| 2 | `data/config.json.bak` | `docs/.local/archive/2026-11-08/data/config.json.bak` |
| 3 | `data/poc_attachment_results.json` | `docs/.local/archive/2026-11-08/data/poc_attachment_results.json` |
| 4 | `data/query_results.json` | `docs/.local/archive/2026-11-08/data/query_results.json` |
| 5 | `scripts/probe_announcement_report.txt` | `docs/.local/archive/2026-11-08/scripts/probe_announcement_report.txt` |
| 6 | `scripts/poc_attachment_parser.py` | `docs/.local/archive/2026-11-08/scripts/poc_attachment_parser.py` |
| 7 | `scripts/reclean_announcement_content.py` | `docs/.local/archive/2026-11-08/scripts/reclean_announcement_content.py` |
| 8 | `docs/.local/archive/2026-10-24/docs/MIGRATION.md` | **原地**（已归档，未移动） |

- `docs/.local/archive/2026-11-08/` 累计 15 个文件。

---

## 第 3 步：删除 web 生成物

**结果：4 个路径全部删除，物理文件 120 份，27.45 MB。**

| 路径 | 物理文件数 | review_log 行数 |
|---|---:|---:|
| `web/coverage/` | 88 | 86 |
| `web/playwright-report/` | 29 | 26 |
| `web/test-results/` | 2 | 1 |
| `web/stats.html` | 1 | 1 |
| **合计** | **120** | **114** |

**差异说明**：120 − 114 = 6 份为第一轮按“二进制/资源”排除规则未纳入 `review_log.csv` 的文件，随目录整体删除；本步工单要求“整目录删除”，故按目录执行。

---

## 第 4 步：删除明文凭证文件

**结果：1 份已删除。**

- 文件：`docs/archive/2026-07-16-historical-plans/pressure_test_config.json`
- 前置：`git ls-files` 未命中（未跟踪）、未暂存。
- 未读取、未解析文件内容；未连接任何服务。
- **凭证轮换仍需老板/运维执行**（不在本工单范围）。

---

## 第 5 步：处置 26 份迁移备份

**结果：删除 25 份，保留 1 份。**

保留：
- `data/backups/pre_migration_v74_to_v75.bak`（2,134,016 B；无 -shm/-wal 边车）

删除（25）：
```text
pre_migration_v65_to_v66.bak
pre_migration_v65_to_v66.bak-shm
pre_migration_v65_to_v66.bak-wal
pre_migration_v66_to_v67.bak
pre_migration_v66_to_v67.bak-shm
pre_migration_v66_to_v67.bak-wal
pre_migration_v67_to_v68.bak
pre_migration_v67_to_v68.bak-shm
pre_migration_v67_to_v68.bak-wal
pre_migration_v68_to_v69.bak
pre_migration_v68_to_v69.bak-shm
pre_migration_v68_to_v69.bak-wal
pre_migration_v69_to_v70.bak
pre_migration_v69_to_v70.bak-shm
pre_migration_v69_to_v70.bak-wal
pre_migration_v70_to_v71.bak
pre_migration_v70_to_v71.bak-shm
pre_migration_v70_to_v71.bak-wal
pre_migration_v71_to_v72.bak
pre_migration_v71_to_v72.bak-shm
pre_migration_v71_to_v72.bak-wal
pre_migration_v72_to_v73.bak
pre_migration_v72_to_v73.bak-shm
pre_migration_v72_to_v73.bak-wal
pre_migration_v73_to_v74.bak
```
- 未打开、未连接任何 `.bak` 数据库文件。
- `data/backups/` 现存 1 个文件。

---

## 第 6 步：更新 review_log.csv 备注

**结果：165 行追加 `[W2-A 已执行: 移动/归档/删除]`；未新增行、未删除行、未改判定列。**

| 类别 | 行数 |
|---|---:|
| 移动（第 1 步） | 17 |
| 归档（第 2 步，含 MIGRATION 原地） | 8 |
| 删除（第 3 步 web，review_log 口径） | 114 |
| 删除（第 4 步凭证） | 1 |
| 删除（第 5 步备份） | 25 |
| **合计** | **165** |

> `MIGRATION.md` 标记为 `[W2-A 已执行: 归档（原地）]`；保留的 `pre_migration_v74_to_v75.bak` 未打标（未移动/未删除）。

---

## 第 7 步：本报告

- 路径：`CLOSEOUT/W2-A-execution.md`（本文件）。

---

## 总计

| 指标 | 数量 |
|---|---:|
| 物理移动 | **24**（第 1 步 17 + 第 2 步 7） |
| 原地归档 | 1（MIGRATION.md） |
| 删除（物理文件） | **146**（web 120 + 凭证 1 + 备份 25） |
| 删除（`review_log` 口径） | 140（web 114 + 凭证 1 + 备份 25） |
| 保留 | 1（`pre_migration_v74_to_v75.bak`） |
| `review_log` 打标行 | 165 |
| 失败项 | 0 |
| 未执行项 | 9 份 `tests/verify_downloads/`（工单未列）+ 2 份已在 `scripts/archive/` 的脚本（无需移动） |

---

## 最终 git status

```text
 D docs/analysis/http-requests-inventory.archived.md
 D docs/analysis/v1_vs_v2_routing_comparison.md
 D docs/plans/2026-10-29-stage6-record.md
 D docs/plans/batch5-terminology-design.md
 D docs/plans/moviepilot-investigation/02-pilotstd-gap-analysis.md
 D docs/records/2026-10-24-doc-audit.md
 D docs/research/2026-11-01-moviepilot-notification-design.md
 D scripts/audit_openapi_frontend.py
 D scripts/clean_old_announcements.py
 D scripts/cleanup_announcement_data.sql
 D scripts/compare_v1_v2_routing.py
 D scripts/poc_attachment_parser.py
 D scripts/probe_announcement_html.py
 D scripts/probe_announcement_report.txt
 D scripts/probe_cssn_api.py
 D scripts/probe_miit_api.py
 D scripts/probe_ncha_api.py
 D scripts/reclean_announcement_content.py
 D scripts/update_docs.archived.py
?? CLOSEOUT/
?? scripts/archive/audit_openapi_frontend.py
?? scripts/archive/clean_old_announcements.py
?? scripts/archive/cleanup_announcement_data.sql
?? scripts/archive/compare_v1_v2_routing.py
?? scripts/archive/probe_announcement_html.py
?? scripts/archive/probe_cssn_api.py
?? scripts/archive/probe_miit_api.py
?? scripts/archive/probe_ncha_api.py
?? scripts/archive/update_docs.archived.py
```

- 19 条 tracked 删除 + 10 条 untracked（`CLOSEOUT/` + 9 个移入 `scripts/archive/` 的脚本）；
- `docs/.local/` 已被 gitignore，移动不进入 git 状态；
- 无暂存内容；未执行 `git add / commit / push`。
