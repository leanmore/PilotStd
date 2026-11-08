# PilotDoc Closeout 总报告（2026-11-08）

> 工作区：`D:\PilotStd`｜基线 HEAD：`d1d871ea`｜VERSION：`0.178.0`
> 执行批次：W2-A（归档/删除）、W2-B-0 / W2-B-0b（凭证脱敏）、W2-B-2（7 组合并）、W2-C（死链与索引）
> 所有数字来自 `CLOSEOUT/review_log.csv`、实际文件系统、`git status` 与门禁输出；未使用第一轮提案数字。

---

## 一、任务与范围

- 目标：对 PilotStd 工作区做一次收尾策展——判定每份文件对项目后期是否还有用，保留有效知识、归档过程材料、删除已失效/生成物，并留下可追溯记录。
- 纳入判定：**1,961 份**（全盘 70,813，排除依赖/虚拟环境/缓存/构建产物/二进制 68,852）。
- 排除口径：`node_modules`、`.venv`、`__pycache__`、各类缓存、`dist/build/logs`、`.git`、图片/字体等二进制；`.db/.onnx/.pdf` 未擅自排除，按规则进入 Pending / Keep / Archive。
- 约束：W2-A 之后未修改文件内容（仅移动/删除）；W2-B-2/W2-C 只改工单列出的文档与脚本；未 `git add/commit/push`。

## 二、执行摘要

### 2.1 最终处置（按实际文件系统）

| 处置 | 数量 | 说明 |
|---|---:|---|
| **Keep** | **1,632** | 原路径存在且不在归档区；含本轮修改过的 stub/文档 |
| **Archive** | **180** | 已在 `docs/archive`、`docs/.local/archive`、`scripts/archive`、`tests/verify_downloads`，或本轮移入归档区 |
| **Delete** | **144** | 原路径不存在且无归档副本（web 生成物、25 份 DB 备份、凭证、plans/README 等） |
| **Pending** | **5** | `pre_migration_v74_to_v75.bak`、`data/pilotstd.db`、3 个 OCR `.onnx` |
| **合计** | **1,961** | — |

> 第一轮的 `Merge 17` 已全部落地：Keep 13（G1/G5/6 份通知设计/压测方案等）、Archive 3（2 份分类结果 + PROJECT_GOVERNANCE）、Delete 1（plans/README）。因此最终分类不再单列 Merge。
> `data/config.json.bak` 是 ConfigManager 保存时自动重建的运行态备份（原文件 W2-A 已归档），当前计入 Keep。

### 2.2 W2-A（归档/删除）

| 项 | 数量 |
|---|---:|
| 物理移动 | 24（17 新增归档 + 7 过期文档/脚本） |
| 原地归档 | 1（`docs/.local/archive/2026-10-24/docs/MIGRATION.md`） |
| 删除（物理文件） | 146（web 120 + 凭证 1 + DB 备份 25） |
| 删除（review_log 口径） | 140 |
| 保留 | 1（`pre_migration_v74_to_v75.bak`） |
| 失败 | 0 |

### 2.3 W2-B-0 / W2-B-0b（凭证脱敏）

| 文件 | 脱敏内容 | 备注 |
|---|---|---|
| `docs/guides/人工测试方案.md` | L48-49 两个 OCR 值 → `<从环境变量或配置读取>` | 首轮 `***`，B-0b 改明确占位符 |
| `tests/test_config.json` | L17-22 六个 OCR 值 → 环境变量占位符 | 该文件被 `.gitignore` 忽略，不产生 git M |
| `docs/archive/.../2026-06-16-全量压力测试设计.md` | L21 Docker 密码 + L27-32 六个 OCR 值 → `<已脱敏…>` | `docs/archive/` 被忽略；L21 超出工单行号，属同一凭证清理 |

合计：**3 个文件、15 个值**（含 `人工测试方案.md` 两次处理）。原凭证字符串已在这 3 个文件中消失；`tests/test_config.json` 剩余 docker/web/API token 等字段不在本批范围（见 §四）。

### 2.4 W2-B-2（7 组合并）

| 组 | 结果 |
|---|---|
| G2 `development.md` | 全文替换为 5 行 stub，保留文件名维持 4 处引用 |
| G4 站点分类 | design 新增 §6；config 注释改“已归档 + 现行见本文件”；2 份 analysis 归档 |
| G5 `query/README.md` | 日期、行号、6 步兜底标题、scorer 说明修正；保留 v2 TODO |
| G1 `architecture.md` | 范围表加“历史快照”注；无 Mixin 例外改为 `_WindowLifecycleMixin`；index/MAP 描述修正 |
| G6 `plans/README.md` | 10 条在办计划并入 ROADMAP S7；删除 README；MAP 删行 |
| G8 压力测试方案 | 人工测试方案新增 §六（4 小节）；`stress_driver.py` 3 处注释改指向 §六 |
| G3 `PROJECT_GOVERNANCE.md` | 2 节并入 governance/README；原文归档；G-032 清单删项 |

### 2.5 W2-C（死链与索引）

| 动作 | 数量 |
|---|---:|
| `DOCUMENTATION_MAP.md` 删除归档行 | 3（site_classification_partial、batch5、moviepilot-02） |
| `DOCUMENTATION_MAP.md` 更新行 | 1（development.md → 已迁移） |
| `implementation-digest.md` 旧路径改写 | 1 |
| `gates.md` 路径修正 | 2 处（`scripts/update_docs.archived.py` → `scripts/archive/...`） |
| **合计** | **7 处** |

> `PROJECT_GOVERNANCE.md` 与 `plans/README.md` 的 MAP 行已在 W2-B-2 删除；两份 site_classification 的 status.json 本无 MAP 行。

## 三、关键决策记录

### 3.1 已拍板的 5 项

1. **删除口径**：采用 A——可重生成物与凭证直接删，文档类移入 `.local/archive`；`DECISIONS.md` D-39“删除数保持 0”被本次工单显式覆盖（仅限生成物/凭证）。
2. **DB 备份**：保留最新 `pre_migration_v74_to_v75.bak`，删除其余 25 份（含 sidecar）。
3. **凭证**：删除 `pressure_test_config.json`；3 个文件脱敏；**轮换由老板在云控制台/Docker 执行**（未联网）。
4. **通知设计**：G7 的 9 份不合并、不移动，留待后续批次。
5. **执行范围**：允许为实现合并而改 `scripts/check_g_032_doc_health.py`、`docs/governance/gates.md`、`tests/stress_driver.py` 注释。

### 3.2 三组从“合并”下调为“不合并/就地修”

| 组 | 第一轮 | 最终 | 理由 |
|---|---|---|---|
| G1 | Merge | 保留 + 就地修 | 文件是 ADR-010 指定的 Handler 决策载体；且公告双表/回调端点/状态契约/v68 四类内容只在此处，合并会丢知识 |
| G4 | Merge（2 份） | 不合并结果表 | `config/site_capabilities.yaml` 是 router_v2 运行时 SSOT；把 21 行表抄进 design 会形成第三份会漂移的数据 |
| G5 | Merge | 保留两份 | `modules/query.md` 只讲适配器；四节（ADAPTER_TYPE_MAP/决策树/v2/分桶）只在 `query/README.md`，职责不同 |

## 四、遗留项

1. **凭证轮换（老板后期 Docker/云控制台）**：百度 OCR、腾讯/阿里云、Docker 密码；本批只做文件脱敏，未连接任何服务。
2. **`tests/test_config.json` 其余敏感字段**：`docker.password`、`web_admin.password`、`web_api.api_token`、`query.announcement_api_key` 仍是明文（文件被 gitignore，但仍在磁盘）；不在本批 L17-22 范围，建议下一批处理。
3. **G7 通知设计 9 份**：未合并、未移动；`DECISIONS.md` 已记录结论，设计原文仍在 `docs/plans/` 与 `.local/archive`。
4. **代码债对账**：未启动（原计划的“代码类逐文件对账”未进入本批）。
5. **G-032 的 3 条 warning（均为环境性/宽限期）**：
   - `STATUS.md` 不存在 ×2（本地生成文件；W2-A 已归档，CI 检出时缺失属正常）；
   - `docs/testing/known-issues.md` 20 天未更新（14 天上限，宽限期内）。
   - 原第 4 条“`gates.md` 引用不存在的 `scripts/update_docs.archived.py`”**已修，不再出现**。
6. **其他索引死链**：`DOCUMENTATION_MAP.md` 仍列 W2-A 移走的 `http-requests-inventory.archived.md`、`v1_vs_v2_routing_comparison.md`、`records/2026-10-24-doc-audit.md`、`research/2026-11-01-...md`；不在 W2-C 清单，未改。
7. **`docs/query/README.md` 的 v2 TODO**：按工单保留（U-14 未决）。
8. **`data/config.json.bak` 被运行时重建**：`ConfigManager.save()` 的 R15 备份逻辑在门禁/测试期间重新生成；如不希望保留，可下次运行前删除。

## 五、验证方式

| 门禁 | 结果 |
|---|---|
| `python scripts/check_docs_drift.py` | **EXIT 0**，0 违规（121 路由 / 43 配置 / 120 表名 / 44 事件） |
| `pytest tests/test_check_docs_drift.py -q` | **3 passed** |
| `python scripts/check_g_032_doc_health.py` | **EXIT 0**，3 warnings（见 §四.5） |
| `python scripts/check_g_037_trigger_alignment.py` | **EXIT 0**，读取侧 15 项对齐、回写侧 4 份一致 |
| W2-B-2 各组附加门禁 | G4 routing **38 passed**；G1 module-doc **11 passed**；G2 docs-sync **15 passed**；G8 `py_compile` 0 |
| 凭证残留 grep | 3 个目标文件中 6 组原 Key 前缀 **0 命中** |

## 六、变更清单

### 6.1 git status 分类

- **M（14）**：`config/site_capabilities.yaml`、`docs/DOCUMENTATION_MAP.md`、`docs/ROADMAP.md`、`docs/architecture.md`、`docs/design/site_classification_v1.md`、`docs/development.md`、`docs/governance/README.md`、`docs/governance/gates.md`、`docs/guides/人工测试方案.md`、`docs/index.md`、`docs/query/README.md`、`docs/reference/implementation-digest.md`、`scripts/check_g_032_doc_health.py`、`tests/stress_driver.py`
- **D（23）**：W2-A 的 19 个（7 docs + 9 scripts + 3 根/数据）+ W2-B-2 的 4 个（2 份 site_classification、PROJECT_GOVERNANCE、plans/README）
- **??（10）**：`CLOSEOUT/` + `scripts/archive/` 下 9 个 W2-A 移入脚本
- **不计入 git**：`tests/test_config.json`（`.gitignore`）、`docs/archive/**`（`.gitignore`）

### 6.2 总增删

- `git diff --stat`：**37 files changed, +155 / −4,130**（含 W2-A 的 19 个删除 −3,641）。
- 未跟踪/忽略的两处脱敏文件不在 diff 内。

## 七、下一步建议

1. **G7 通知设计**：按 `W2-B-merge-proposals.md` G7 执行“先归档 + 建索引，再合并”；当前 9 份仍在 `docs/plans/`。
2. **代码债对账**：启动代码类逐文件核对（引用/测试/一致性），本轮仅做静态信号。
3. **凭证轮换**：优先百度 OCR（3 个文件中出现）与 Docker 密码；轮换后验证旧 Key 已禁用。
4. **清理剩余敏感字段**：`tests/test_config.json` 的 docker/web/API token 字段。
5. **提交与推送**：当前 37 个 tracked 变更 + 10 个 untracked 尚未 add/commit；建议按 W2-A / W2-B / W2-C 分 3 个逻辑提交，并先跑一次 `check_all.sh --fast --guards --local`。

---

*本报告由 PilotDoc Closeout 流程生成；明细见 `CLOSEOUT/review_log.csv`（1,961 行，含“人工终判”列，已填 188 行）。*

