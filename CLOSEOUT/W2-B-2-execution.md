# W2-B-2 执行记录

> 工单：W2-B-2｜执行时间：2026-11-08 10:40–10:52（Asia/Shanghai）
> 前置：老板选择 **A**——dsh 先完成 W2-B-0 脱敏，再执行本批。
> 权限：只改本工单列出文件；未 `git add/commit/push`；未联网、未启服务、未连数据库。

---

## 前置 0：W2-B-0（脱敏）

| 项 | 内容 |
|---|---|
| 文件 | `docs/guides/人工测试方案.md` |
| 改动 | L48-49 的 `api_key`/`secret_key` 值 → `***`（2 行，diff `-2/+2`） |
| 验证 | 原 Key 字符串在全文已不存在；`git status` 出现 ` M docs/guides/人工测试方案.md` |

**附带发现（超出本工单，未修改）**：同一批凭证仍在
- `tests/test_config.json` L17-22（未被 git 跟踪，但仍在磁盘）；
- `docs/archive/2026-07-16-historical-plans/2026-06-16-全量压力测试设计.md` L27-31（未跟踪）。

建议另开安全工单清理，并按工单末尾清单轮换。

## 前置检查（A 完成后）

| 检查项 | 实际 | 结果 |
|---|---|---|
| `git status` | 19 D + 10 ?? + **1 M** | ✅ |
| 7 组源文件 | 全部存在 | ✅ |
| `VERSION` | `0.178.0` | ✅ |

---

## 第 1 组 G2：`docs/development.md` 改 stub

| 项 | 内容 |
|---|---|
| 改动文件 | `docs/development.md`（整文件替换为 5 行 stub，diff `6/-207`） |
| 未改 | `_docs_sync_rules.py`、PR 模板、`gates.md`、`documentation-policy.md`（文件名保留，引用继续有效） |
| 门禁 1 | `python scripts/check_docs_drift.py` → **EXIT 0**（0 违规） |
| 门禁 2 | `pytest tests/test_check_docs_drift.py` → **3 passed** |
| 门禁 3 | `pytest tests/test_docs_sync_check.py` → **15 passed** |
| 结论 | ✅ 绿 |

## 第 2 组 G4：站点分类加指针

| 项 | 内容 |
|---|---|
| 改动文件 | `docs/design/site_classification_v1.md`（新增 §6，`+8`）；`config/site_capabilities.yaml`（L3-5 注释，`3/-2`） |
| 移动 | `docs/analysis/site_classification_partial.md`、`site_classification_status.json` → `docs/.local/archive/2026-11-08/docs/analysis/`（原路径已不存在） |
| 未改 | 21 行结果表未抄入 design；两份 analysis 内容未改 |
| 门禁 1 | `check_docs_drift.py` → **EXIT 0** |
| 门禁 2 | `pytest tests/test_check_docs_drift.py` → **3 passed** |
| 门禁 3 | `pytest tests/test_routing_scorer.py tests/unit/query/routing` → **38 passed** |
| 结论 | ✅ 绿 |

## 第 3 组 G5：`docs/query/README.md` 就地修正

| 项 | 内容 |
|---|---|
| 改动 | 头部日期 `2026-07-27→2026-11-07`；行号 `252-294→275`；标题改“6 步兜底；动态评分优先”；补“v1 先走 scorer”一句；正文“7 层”→“6 步兜底”（与标题一致） |
| 未改 | §v2 的 `TODO` 保留（U-14 未决）；`modules/query.md` 未动 |
| 门禁 1 | `check_docs_drift.py` → **EXIT 0** |
| 门禁 2 | `pytest tests/test_check_docs_drift.py` → **3 passed** |
| 结论 | ✅ 绿 |

## 第 4 组 G1：`docs/architecture.md` 就地修正

| 项 | 内容 |
|---|---|
| 改动 | `docs/architecture.md`：§范围表前加“历史快照（2026-07-11），勿当现值”；§无 Mixin 例外改为“唯一保留 `_WindowLifecycleMixin`（见 ADR-010）”（`3/-4`） |
| 同步 | `docs/index.md` L33 描述改为“架构决策与跨模块契约（Handler/公告模型/回调/状态契约）”（`1/-1`）；`docs/DOCUMENTATION_MAP.md` 的 architecture 行补描述（可选，已做） |
| 未做 | 未移动、未拆分、未删除 `architecture.md` |
| 门禁 1 | `check_g_032_doc_health.py` → **EXIT 0**（通过，4 条既有警告，见文末） |
| 门禁 2 | `check_g_037_trigger_alignment.py` → **EXIT 0**（15 项对齐） |
| 门禁 3 | `check_docs_drift.py` → **EXIT 0** |
| 门禁 4 | `pytest tests/test_check_docs_drift.py tests/test_check_module_doc_mappings.py` → **11 passed** |
| 结论 | ✅ 绿 |

## 第 5 组 G6：`plans/README.md` 合并进 ROADMAP

| 项 | 内容 |
|---|---|
| 改动 | `docs/ROADMAP.md`：新增 `### S7 部署与验证（2026-10-28～11-08）` 10 行；头部版本 `v0.151.2→v0.178.0`、阶段日期 2026-11-08；S5 加状态核对、M5/M6 加核对注；§五 加变更行（`24/-2`） |
| 删除 | `docs/plans/README.md`（46 行）已删除；两处失效链接不再存在 |
| 同步 | `docs/DOCUMENTATION_MAP.md` 删除 plans/README 行 |
| 未动 | 6 份通知设计、10 份在办计划均原地不动 |
| 门禁 1 | `check_docs_drift.py` → **EXIT 0** |
| 门禁 2 | `pytest tests/test_check_docs_drift.py` → **3 passed** |
| 门禁 3 | `check_g_032_doc_health.py` → **EXIT 0**（4 warnings） |
| 门禁 4 | `check_g_037_trigger_alignment.py` → **EXIT 0** |
| 结论 | ✅ 绿 |

## 第 6 组 G8：压力测试方案摘录合并

| 项 | 内容 |
|---|---|
| 改动 | `docs/guides/人工测试方案.md`：新增 §六（6.1 冷/热策略、6.2 分步执行、6.3 PASS 判据结构、6.4 已知限制），L12 改为“源码级全量判据见 §六”（`37/-3`） |
| 未搬 | 能力映射表、623/104、46 端点等过时数字均未搬入 |
| 注释修正 | `tests/stress_driver.py` L6/L8/L2158 三处旧的 `docs/压力测试方案.md`/`本机源码全量…` 指向改为 `docs/guides/人工测试方案.md §六`（`3/-3`，仅注释） |
| 验证 | `python -m py_compile tests/stress_driver.py` → **EXIT 0**；`grep` 旧路径 → 0 命中；`tests/test_stress_runner.py` 不存在（该文件是 deprecated shim，未改逻辑） |
| 门禁 1 | `check_docs_drift.py` → **EXIT 0** |
| 门禁 2 | `pytest tests/test_check_docs_drift.py` → **3 passed** |
| 门禁 3 | `check_g_032_doc_health.py` → **EXIT 0**（4 warnings） |
| 门禁 4 | `check_g_037_trigger_alignment.py` → **EXIT 0** |
| 结论 | ✅ 绿 |

## 第 7 组 G3：`PROJECT_GOVERNANCE.md` 合并进 `governance/README.md`

| 项 | 内容 |
|---|---|
| 改动 | `docs/governance/README.md` 新增“治理体系原则（并入自 PROJECT_GOVERNANCE）”（原则 1/2/4 原文，原则 3 改写）与“治理操作流程（新增能力/新增门禁/重构迁移）”（`+59`） |
| 移动 | `docs/governance/PROJECT_GOVERNANCE.md` → `docs/.local/archive/2026-11-08/docs/governance/PROJECT_GOVERNANCE.md`（原路径已不存在，113 行） |
| 同步 | `scripts/check_g_032_doc_health.py` 删除该文件的期望项（`0/-1`）；`docs/DOCUMENTATION_MAP.md` 删除该行 |
| 未并入 | 治理角色表（过时）、版本历史（无复用价值）、§三 文档索引（重复） |
| 门禁 1 | `check_g_032_doc_health.py` → **EXIT 0**（不再检查 PROJECT_GOVERNANCE，4 warnings） |
| 门禁 2 | `check_docs_drift.py` → **EXIT 0** |
| 门禁 3 | `pytest tests/test_check_docs_drift.py` → **3 passed** |
| 门禁 4 | `check_g_037_trigger_alignment.py` → **EXIT 0** |
| 结论 | ✅ 绿 |

---

## 全量门禁汇总

| 组 | 门禁 | 结果 |
|---|---|---|
| G2 | docs_drift / test_check_docs_drift / test_docs_sync_check | ✅ 0 / 3 passed / 15 passed |
| G4 | docs_drift / test_check_docs_drift / routing（38） | ✅ 0 / 3 / 38 passed |
| G5 | docs_drift / test_check_docs_drift | ✅ 0 / 3 passed |
| G1 | g032 / g037 / docs_drift / 2 tests | ✅ 0 / 0 / 0 / 11 passed |
| G6 | docs_drift / test / g032 / g037 | ✅ 0 / 3 / 0 / 0 |
| G8 | docs_drift / test / g032 / g037 / py_compile | ✅ 0 / 3 / 0 / 0 / 0 |
| G3 | g032 / docs_drift / test / g037 | ✅ 0 / 0 / 3 / 0 |

**G-032 的 4 条 warning（既有/环境性，未处理）**：
1. `STATUS.md 不存在`（W2-A 已归档；本地生成文件，CI 检出时缺失属正常）
2. 同上（重复计数）
3. `docs/testing/known-issues.md` 20 天未更新（宽限期内）
4. `docs/governance/gates.md` 引用 `scripts/update_docs.archived.py`（该文件 W2-A 已移入 `scripts/archive/`；属 W2-A 遗留的断链，不在本批文件清单内，未修）

---

## 本批 diff 统计（仅 W2-B-2 涉及文件）

| 类型 | 文件数 | 增 | 删 |
|---|---:|---:|---:|
| 修改（M） | 12 | 151 | 230 |
| 删除/归档（D） | 4 | 0 | 252 |
| **合计** | **16** | **151** | **482** |

> 另有 W2-B-0 的 `人工测试方案.md` 2 行（已计入上表 M 的 37/+3 中）。
> `git diff --stat` 全量显示 35 files / +151 / −4123，其中 −3641 为 W2-A 的 19 个删除。

## 最终 git status（摘要）

- **M（12）**：`config/site_capabilities.yaml`、`docs/DOCUMENTATION_MAP.md`、`docs/ROADMAP.md`、`docs/architecture.md`、`docs/design/site_classification_v1.md`、`docs/development.md`、`docs/governance/README.md`、`docs/guides/人工测试方案.md`、`docs/index.md`、`docs/query/README.md`、`scripts/check_g_032_doc_health.py`、`tests/stress_driver.py`
- **D（23）**：W2-A 的 19 个 + 本批 4 个（`docs/analysis/site_classification_partial.md`、`docs/analysis/site_classification_status.json`、`docs/governance/PROJECT_GOVERNANCE.md`、`docs/plans/README.md`）
- **??（10）**：`CLOSEOUT/` + `scripts/archive/` 下 9 个 W2-A 移入的脚本
- 未出现清单外文件；未 `git add/commit/push`。

## 遗留 / 需老板处理

1. **凭证轮换**（云控制台 + Docker）：按工单末尾清单执行；本批只脱敏了 `人工测试方案.md`。
2. **另两处明文凭证**：`tests/test_config.json`、`docs/archive/.../2026-06-16-全量压力测试设计.md`（均未跟踪），建议清理。
3. **G-032 warning 4**：`gates.md` 仍引用 `scripts/update_docs.archived.py`（W2-A 已移走），可另开小修。
4. **G5 的 U-14**（v2 TODO）按工单保留未动。
5. **索引死链（既有/未授权）**：`docs/DOCUMENTATION_MAP.md` 仍列 `docs/analysis/site_classification_partial.md`（本批已归档）及 W2-A 移走的 `batch5-terminology-design.md`、`moviepilot-investigation/02-...`；`docs/reference/implementation-digest.md` 仍指向 analysis 旧路径。均不在本批“动作”清单，未改，建议下一批统一清理。



