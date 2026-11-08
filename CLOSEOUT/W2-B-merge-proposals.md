# W2-B 合并提案（审阅稿 · 未执行）

> 工单：W2-B-1｜权限：只读（仅在本目录新建文件）
> 时间：2026-11-08 10:29（Asia/Shanghai）｜基线 HEAD `d1d871ea`｜前置状态：19 D + 10 ??（W2-A 结果，无新增）
> 方法：逐组通读「源文件 + 权威版」，对每条候选独有内容做**代码/配置核验**；核验不了的进 `W2-B-uncertainties.md`，不猜。
> 说明：工单写“8 组”，实际列出 **7 组**（G1–G6、G8）；G7（通知设计 9 份）不在本批。本文件按 7 组出提案。

---

## 总览

| 组 | 源文件 | 权威版 | 独有且仍有效 | 建议处置 | 风险 |
|---|---|---|---:|---|---|
| G1 | `docs/architecture.md` | **保留自身**（Handler 决策补充 ADR-002/010） | 7 条 | **不整体合并**；就地标注过时表 + 修 `index.md` 描述 | 中 |
| G2 | `docs/development.md` | `docs/onboarding/07-dev-workflow.md` + `docs/testing/testing-baseline.md` | 5 条 | **部分合并**；首选改为 5 行 stub（保文件名） | 中高 |
| G3 | `docs/governance/PROJECT_GOVERNANCE.md` | `docs/governance/README.md` | 2 条 | **合并**；源文件归档；同步 G-032 | 中 |
| G4 | `analysis/site_classification_partial.md`、`status.json` | `docs/design/site_classification_v1.md`（方案）+ `config/site_capabilities.yaml`（结果 SSOT） | 3 条（证据类） | **不合并结果表**；设计文档加“结果与数据源”，仅可选并入判定证据 | 低 |
| G5 | `docs/query/README.md` | **保留自身**（查询引擎）；`modules/query.md` 仅适配器 | 4 节**留在原地** | **不合并**；两份职责不同，修正 README 过时细节 | 低 |
| G6 | `docs/plans/README.md` | `docs/ROADMAP.md` | 16 条有效计划 | **合并 10 条在办计划进 ROADMAP**；删除 README；6 份通知设计留给 G7 | 中 |
| G8 | `docs/.local/压力测试方案.md` | `docs/guides/人工测试方案.md` | 4 条 | **部分合并**（原则/判据结构）；映射表与数量基线不并入 | 中高 |

**一句话结论**：7 组里只有 G3、G6 是“整份合并后移除源文件”，G2/G8 是“摘录合并 + 源文件转 stub/留档”，G1/G4/G5 经核验**不应合并**（合并会丢独有内容或制造第三份会漂移的数据）。这与第一轮 `合并建议.md` 的“8 组均合并”相比是**下调**，依据见各组 §3。

---

# G1｜`docs/architecture.md`

## 1. 源文件清单

| 文件 | 大小/行数 | 当前角色 |
|---|---:|---|
| `docs/architecture.md` | 22,279 B / 313 行 | `index.md` 称其为“系统架构、数据模型、技术栈”；实际是**混装文档**：Handler 决策 + 公告数据模型 + 通知回调 + 状态契约 + 迁移注记 |

## 2. 权威版

- **保留 `docs/architecture.md` 自身**：`adr/ADR-010-mixin-refactor.md` L16 明确写“Handler 组合模式（2026-07-11）的载体是 `docs/architecture.md`「Handler 组合模式」章节”——它是该决策的**唯一原始载体**，删除会让 ADR-010 的引用悬空。
- Handler 治理部分的权威补充：`docs/adr/ADR-002-handler-governance.md`（策略/模式/门禁）、`docs/adr/ADR-010-mixin-refactor.md`（16→1 收尾）。
- 不建议把整份并入 `docs/architecture/overview.md`（后者 9.6 KB，是“总览”，并入会变成 32 KB 杂物袋，且公告/回调/契约不属于总览层）。

## 3. 独有内容清单（源文件有、权威版没有、且仍有效）

| # | 内容 | 源文件位置 | 核验结果（2026-11-08） |
|---|---|---|---|
| R1 | 公告**双表模型**：`announcement_record` 活跃写入 / `announcements` 仅 v36 一次性写入 | §公告数据模型 → 双表现状（L168-175） | **仍有效**：`pilotstd/announcement/matcher.py:436` 仍 INSERT `announcement_record`；`announcements` 仅 `_migrate_v31_plus.py:299` 有写入 |
| R2 | 公告查询路由：4 个 API 各查哪张表 | 同上 → 查询路由（L177-184） | **仍有效**：`docker/api/announce_detail.py:135` 查 `announcement_record`；`announce.py:323` 仍保留对 `announcements` 的读取 |
| R3 | 公告表已知限制：`announcement_record` 无 `source_url`/`attachment_url`；`announcements` 仅历史快照 | 同上 → 已知限制（L186-190） | **表结构仍有效**：v70 重建列清单（`_migrate_v70_announcement_record_language.py`）无这两列；**“详情页暂无法显示原文链接”是否仍是用户可见限制，不确定**（见 U-01） |
| R4 | 收藏表结构与 **v52/v59/v60** 迁移因果（publish_date 补列、retry 两列补后再删、GET status 端点已删） | §收藏与归档（Phase 4a）（L192-241） | **仍有效**：v52/v59/v60 迁移文件存在；ADR-007 只讲解耦，未讲这三段因果 |
| R5 | 通知回调 **5 端点表**（telegram/dingtalk/feishu/wechat GET+POST）+ 企微 XML 加密与身份反查差异 | §通知渠道回调入站端点（L258-280） | **仍有效**：`docker/api/notification_callback.py` 现有 `GET /api/notification/callback/wechat`、`POST /api/notification/callback/{channel}`；`wechat_crypto.py` 存在 |
| R6 | 状态字段 **API 契约表**（`status` 中文 + `status_key` 英文键 + 过滤入参双读 + 3 端点 + 前端只比 key） | §状态字段 API 契约（L291-305） | **仍有效**：`core/status.py:106/118` 有 `status_key`/`resolve_status_filter`；`docker/api/standards.py` 等已返回 `status_key` |
| R7 | **v68** 通知策略类别层：`event_classes` 新增、与 `events` 双层并存、读侧双读与回退 | §公告数据模型 → v68 注记（L223-228） | **仍有效**：v68 迁移文件存在；该“双读回退=回滚开关”的解释只在此处（其余在已归档设计稿） |

**判定为“过时、不并入”的内容**：

| 内容 | 位置 | 为什么不能照搬 |
|---|---|---|
| 42 Mixin→32 Handler 数量表 | §Handler 组合模式 → 范围（L36-42） | **不准确**：项目自己的体检 `docs/debt/05-audit-2026-10-17.md` C-10 已写“`:38-42` 表 `scan/parser 1→5（_*_handler.py）` 实测 **0** 个”；当前 `ui/core/handlers/` 是 13 个 Handler + 12 个 FlowEngine，`manager/facade/` 9 个 `_*.py`，`query/engine/` 11 个业务模块，`scan/parser/` 无 `_*_handler.py`。数量已不可复算，只能标“2026-07-11 历史快照” |
| “无 Mixin 例外”清单 | §无 Mixin 例外（L44-49） | **与 ADR-010 冲突/表述错误**：ADR-010 明确“唯一保留 `_WindowLifecycleMixin`”；该节却拿 `StandardParser`/`ParserCore` 当“例外”，两者不是 Mixin。当前代码 `grep class .*Mixin` 仅有 `_WindowLifecycleMixin` |
| 验收标准 763 passed / 619 导入 | §验收标准（L51-56） | 时点数据（当前后端 6000+） |

## 4. 拟并入位置

**推荐：不移动、不并入。** 只做两处就地修订（执行轮）：

1. `docs/architecture.md` §范围：把 42→32 表改为一句“历史快照（2026-07-11），当前数量见 ADR-010 与模块文档”，避免读者当现值；
2. `docs/architecture.md` §无 Mixin 例外：改为“唯一保留 `_WindowLifecycleMixin`（Qt 硬约束，见 ADR-010）”。

**备选（仅当老板要求拆分）**：R1–R3 → `docs/reference/announcement-pipeline.md` 新「## 数据模型」；R5 → `docs/architecture/modules/core.md` 新「## 通知回调入站」；R6 → 同文件「## 关键机制 → 状态值字典」补 3 行；R7 → `docs/migrations/README.md`「## 重点迁移详细说明」；R4 → `docs/adr/ADR-007` 附录。**此方案工作量大、拆完源文件仍需保留（ADR-010 引用），不推荐。**

## 5. 拟删除/拟归档副本

**无。** 不删除、不归档 `docs/architecture.md`。

## 6. 需同步更新的引用

| 引用点 | 现状 | 动作 |
|---|---|---|
| `docs/index.md` L33 | `architecture.md` = “系统架构、数据模型、技术栈” | 改为“架构决策与跨模块契约（Handler/公告模型/回调/状态契约）” |
| `docs/DOCUMENTATION_MAP.md` L? `docs/architecture.md` 行 | 内容列是“—” | 补一句准确描述 |
| `AGENTS.md §7.1` 两处（读取触发/回写） | 指向 `docs/architecture.md` | **不改**（保留该文件即继续有效） |
| `.github/PULL_REQUEST_TEMPLATE.md` L41-42 | “API 行为变更 / DB 查询逻辑变更 → architecture.md” | **不改**（继续有效） |
| `docs/adr/README.md` L50、`docs/adr/ADR-010` L16 | 链接/引用 architecture.md | **不改**（继续有效） |
| `docs/debt/01-archive-closed.md` L97 等 | 历史链接 | 不动（归档文本） |

## 7. 合并后需跑的门禁

- `python scripts/check_g_032_doc_health.py`（该脚本 L47 要求 `docs/architecture.md` ≥30 行）
- `python scripts/check_g_037_trigger_alignment.py`（AGENTS §7.1 触发对齐）
- `python scripts/check_docs_drift.py`
- `python -m pytest tests/test_check_docs_drift.py tests/test_check_module_doc_mappings.py -q`

> 不需要 `check_g_031`（本次不动 `pilotstd/core/` 映射）。

## 8. 风险与不确定点

- **风险（中）**：不改，`index.md` 继续把“决策记录”当“系统架构”误导读者；改，需同步 2 处索引描述。
- **风险（高，若走备选拆分）**：R1–R7 分散到 4 个文档后，architecture.md 仍需保留（ADR-010 引用），结果是“内容搬走、空壳留下”，维护成本更高。
- **不确定**：R3 的“详情页无法显示原文链接”是否仍是现状（U-01）；42→32 历史值无法复算（U-02）。

---

# G2｜`docs/development.md`

## 1. 源文件清单

| 文件 | 大小/行数 | 当前角色 |
|---|---:|---|
| `docs/development.md` | 9,221 B / 209 行 | 标题 2026-06-30，但正文追加到 2026-11-05；前半是旧版开发指南，后半是 CI/Action/E2E/测试基线 |

## 2. 权威版

- 开发流程：`docs/onboarding/07-dev-workflow.md`（2026-11-07，四环境/测试/门禁/提交）
- 测试基线数字：`docs/testing/testing-baseline.md`
- CI 坑与经验：`docs/ci-lessons.md`

## 3. 独有内容清单

| # | 内容 | 源文件位置 | 核验结果 |
|---|---|---|---|
| U1 | **GitHub Action 版本表**（checkout v5 / setup-python v6 / setup-node v5 / upload v6 / download v7 / build-push v7 / login v4 / buildx v4 / pnpm v5 / gh-release v3）+ “钉首个 node24 主版本”理由 + 升级两步静态校验 | §CI/CD 工作流与 Action 版本（L135-159） | **仍有效**：`.github/workflows/ci.yml` 的 `uses:` 与表中 10 项逐一一致（另 `actions/github-script@v8` 未在本文件表内） |
| U2 | **E2E 报告三处同步**：`playwright.config.ts` 的 `outputFolder`/`outputDir` + CI 上传 `web/playwright-report/`、`web/test-results/` + 本节说明 | 同上（L161-166） | **仍有效**：`web/playwright.config.ts:12-13` 与 `ci.yml:747-752` 一致 |
| U3 | **CI 失败诊断**：`--junitxml=/tmp/backend-report.xml` + “Backend failures summary”把失败用例转 `::error` 注解 | 同上（L127-128） | **仍有效**：`ci.yml:158/177/184` 存在 |
| U4 | **推送网络自适应**：不要把代理写进仓库级 `http.proxy`；用 `HTTPS_PROXY`；排障顺序 `git ls-remote` → 代理 → 重试 | 同上（L130-133） | **仍有效**（经验性，未实测当前网络） |
| U5 | **测试基线快照**：2026-11-04 后端 5974 passed / 10 skipped；2026-11-05 6056 passed；前端 vitest 346 | §测试覆盖状态（L171-185）、§测试基线（L198-209） | **时点数据**；当前是否仍是这些数字**未复跑**（U-05） |

**判定为“过时、不并入”的内容**：

| 内容 | 位置 | 问题 |
|---|---|---|
| 环境搭建 `pilotstd_env` + `requirements.txt` | L6-15 | 与 onboarding/07 的 `.venv` + `requirements-dev.txt` 不一致（后者是现行） |
| 目录结构 v0.54 / “4 个新 mixin” | L17-24 | 与当前 Handler/FlowEngine 架构矛盾 |
| 当前状态 771 PASS | L39 | 严重过期（现 6000+） |
| vulture `--min-confidence=80` | L57 | CI 口径已改为 100（技术债 T-34） |
| Pre-commit 表格（vue-tsc/lint-staged/G-002/G-010/G-011） | L76-87 | **已过时**：现行 `.husky/pre-commit` 只调 `check_all.sh` + 3 项收编检查（SEC-001/G-013/Mixin），不再有这张表 |
| 常用命令 Docker API `--port 8000` | L116 | 与 `docker-compose.yml` 的 9028 不一致 |
| 测试基线“623/104”式旧口径 | — | 已被 U5 覆盖，不再单列 |

## 4. 拟并入位置（精确到标题）

| 内容 | 目标文档 | 目标标题 |
|---|---|---|
| U1 Action 版本 | `docs/onboarding/07-dev-workflow.md` | `## 三、测试命令` → `### CI / 发布 / 备份（2026-11-07 核实）` 之后新增 `### GitHub Action 版本与升级校验` |
| U2 E2E 报告三处同步 | 同上 | 同节新增 `### E2E 报告与失败现场（改 playwright 配置时必看）` |
| U3 CI 失败诊断 | 同上 | 同节新增 `### CI 失败诊断（backend-report.xml）` |
| U4 推送网络 | 同上 | `## 九、常见开发坑` 新增一行，或 `### 推送网络` |
| U5 测试基线 | `docs/testing/testing-baseline.md` | `## 最新基线` 以“2026-11-04 / 11-05（时点）”并列，不覆盖旧值 |

## 5. 拟删除/拟归档副本

- **首选：改为 5 行 stub**（保留文件名与路径，内容为“本文件已并入 onboarding/07 + testing-baseline；CI/Action 内容见 §X；旧版命令已删除”）。
  - 理由：`scripts/_docs_sync_rules.py` 有 2 条规则把 `docs/development.md` 作为 workflow 变更的联动目标；`.github/PULL_REQUEST_TEMPLATE.md`、`docs/governance/gates.md`、`docs/development/documentation-policy.md` 也引用它。改 stub 可避免同时改 5 处规则。
- **次选：删除**，并同步改 4 处引用（见 §6）。两者都需老板选（U-06）。

## 6. 需同步更新的引用

| 引用点 | 内容 | 动作 |
|---|---|---|
| `scripts/_docs_sync_rules.py` L43、L58 | `targets: [("docs/development.md", ...)]` | 改指 `docs/onboarding/07-dev-workflow.md`（若删除） |
| `.github/PULL_REQUEST_TEMPLATE.md` L43 | 工具链变更 → development.md 或 ci-lessons.md | 改指 onboarding/07 |
| `docs/governance/gates.md` L197 | 同上 | 改指 onboarding/07 |
| `docs/development/documentation-policy.md` L110 | 新增测试策略 → development.md | 改指 testing-baseline / onboarding/07 |
| `docs/architecture/governance-summary.md` L187 | “development.md 重建”历史行 | 加注“已并入 onboarding/07” |
| `docs/DOCUMENTATION_MAP.md` L54 | development.md 行 | 删除或改 stub 描述 |

## 7. 合并后需跑的门禁

- `python scripts/check_docs_drift.py`
- `python -m pytest tests/test_check_docs_drift.py tests/test_docs_sync_check.py -q`（后者覆盖 docs_sync 规则）
- `python scripts/check_g_032_doc_health.py`（若改 stub，确认不在其清单内；当前不在）
- `python scripts/check_g_037_trigger_alignment.py`（若 AGENTS 触发表未改动，可跑确认无新增断链）
- 若改 `_docs_sync_rules.py`：`python -m pytest tests/test_docs_sync_check.py -q`

> `tests/test_docs_drift.py` 不存在（工单所列）；实际为 `tests/test_check_docs_drift.py`（U-23）。

## 8. 风险与不确定点

- **风险（中高）**：整份并入会把 2026-06 的旧命令/旧 mixin/771 PASS 一并带进 onboarding/07；必须逐段取舍。
- **风险（中）**：删除会打断 docs-sync 两条规则与 PR 模板，需同批改代码脚本。
- **不确定**：U5 数字是否仍为当前（U-05）；stub vs 删除（U-06）。

---

# G3｜`docs/governance/PROJECT_GOVERNANCE.md`

## 1. 源文件清单

| 文件 | 大小/行数 | 当前角色 |
|---|---:|---|
| `docs/governance/PROJECT_GOVERNANCE.md` | 4,108 B / 113 行 | v1.0（2026-06-29）治理总纲；**不在** `governance/README.md` 的文档索引里（孤儿） |

## 2. 权威版

`docs/governance/README.md`（2026-11-07，治理文档中心）
辅助：`docs/governance/governance-principles.md`（元原则）、`docs/governance/capabilities_registry.md`、`docs/governance/gates.md`。

## 3. 独有内容清单

| # | 内容 | 源文件位置 | 核验结果 |
|---|---|---|---|
| U1 | “能力登记簿 ↔ 门禁 ↔ 架构”三件套联动图 + 4 条核心原则（能力必须有门禁守护、门禁必须守护能力、分层约束放置、三端共享） | §一 治理体系概览（L11-33） | **原则 1/2/4 仍有效**；原则 3 依赖的四层架构文档已归档（`architecture_layers.md` 不在 `docs/`），需改写 |
| U2 | 3 条治理流程：新增能力 / 新增门禁 / 重构迁移（步骤图） | §二 治理流程（L37-83） | **流程骨架仍有效**；引用需更新：`extract_capabilities.sh` 存在、`.husky/pre-commit` 与 `ci.yml repo-compliance` 仍是现行入口 |
| — | 文档索引表 | §三（L87-95） | 已过时：GATE_INDEX 路径、architecture_layers 均已迁移；且与 README 索引重复 |
| — | 治理角色表（决策者/参谋/执行者 Claude Code/CI） | §四（L98-105） | **已过时**：当前执行者是 dsh/DeepSeek，个人项目无“参谋/执行者”分工，不宜并入 |
| — | 版本历史 | §五（L109-113） | 无复用价值 |

## 4. 拟并入位置

| 内容 | 目标标题 |
|---|---|
| U1 原则 1/2/4 + 三件套关系（原则 3 改写为“能力放置以模块文档/架构总览为准”） | `docs/governance/README.md` → 在 `# 能力遗产治理框架` 下新增 `## 治理体系原则（并入自 PROJECT_GOVERNANCE）` |
| U2 三条流程（路径改为 gates.md / check_all.sh / ci.yml） | 同文件新增 `## 治理操作流程（新增能力 / 新增门禁 / 重构迁移）` |

## 5. 拟删除/拟归档副本

- 合并完成后：`docs/governance/PROJECT_GOVERNANCE.md` → `docs/.local/archive/2026-11-08/docs/governance/PROJECT_GOVERNANCE.md`（按归档协议保留原文）。
- 同步从 `scripts/check_g_032_doc_health.py` L44 的期望清单移除该文件（否则 G-032 会因文件消失而 FAIL）。

## 6. 需同步更新的引用

| 引用点 | 动作 |
|---|---|
| `docs/DOCUMENTATION_MAP.md` L24 | 删除该行 |
| `scripts/check_g_032_doc_health.py` L44 | 删除 `("docs/governance/PROJECT_GOVERNANCE.md", 60, "治理文档")` |
| `docs/governance/README.md` 文档索引 | 无需加回（合并内容已在正文） |
| 其他文档 | 全库无引用（已核） |

## 7. 合并后需跑的门禁

- `python scripts/check_g_032_doc_health.py`（必须，因其清单变更）
- `python scripts/check_docs_drift.py`
- `python -m pytest tests/test_check_docs_drift.py -q`
- `python scripts/check_g_037_trigger_alignment.py`（确认 AGENTS 触发表未受影响）

## 8. 风险与不确定点

- **风险（中）**：G-032 清单与文件强绑定，忘记改脚本会让门禁红；流程步骤里的路径需逐条改写，不能原样搬。
- **不确定**：原则 3（四层架构）是删、是改写、还是保留为历史（U-08）；治理角色表是否直接丢弃（U-09）。

---

# G4｜站点分类两份 analysis

## 1. 源文件清单

| 文件 | 大小 | 内容 |
|---|---:|---|
| `docs/analysis/site_classification_partial.md` | 4,409 B | 结果 v1.1：试查询 2 行 + 21 站 10 字段表 + 统计 + 与 v1.0 变化 6 行 |
| `docs/analysis/site_classification_status.json` | 5,223 B | 同结果的机器可读版 + schema 元数据（`classification_doc` 指向 design） |

## 2. 权威版

- **方案**：`docs/design/site_classification_v1.md`（分类体系/判定规则/10 字段格式）
- **结果（运行时 SSOT）**：`config/site_capabilities.yaml`（schema 2.0，21 站，被 `pilotstd/query/routing/router_v2.py:340` 加载）

## 3. 独有内容清单

| # | 内容 | 源文件位置 | 核验结果 |
|---|---|---|---|
| E1 | **ISO 试查询证据**：gongbiaoku 返回无关国标 → 国际能力未通过；njbz365 正确返回 ISO/IEC → 已验证 | partial §试查询结果（L7-12） | **仍有效**；YAML 只存 `is_international` 布尔，不存证据 |
| E2 | **v1.0→v1.1 归类变化 6 行**（std_gov/csres/cssn/hbba/gongbiaoku/njbz365 及原因） | partial §与 v1.0 的归类变化（L46-57） | **历史依据**；解释“为什么 hbba 从特色变综合”等，YAML 不存 |
| E3 | **21 站 `judgment_basis`**（每站一句判定理由） | partial §分类汇总表（L14-40 最后一列） | **仍有效**（新增站点时可复用）；YAML 的 `notes` 只覆盖部分 |
| — | 21 站结果表本体 + 统计（4/17/0） | partial L14-46、status.json | **重复**：已在 `config/site_capabilities.yaml`（21 站、schema 2.0）中运行化；再抄进 design 会形成第三份会漂移的数据 |
| — | `schema_version`/`analysis_date` 元数据 | status.json | 无运行消费方，仅溯源 |

## 4. 拟并入位置

**结论：不合并“结果表”**。理由：`config/site_capabilities.yaml` 是 router_v2 的运行时输入，更新频率高于文档；把 21 行表抄进 design 后，任何一次站点能力调整都会让文档与 YAML 不一致，而 design 的职责是“怎么分类”，不是“现在分成什么”。

- **必须做**：`docs/design/site_classification_v1.md` 新增 `## 6. 结果与数据源`：
  - 现行结果见 `config/site_capabilities.yaml`（schema 2.0，21 站）；
  - 分类结果来源：`docs/analysis/site_classification_partial.md`（v1.1，2026-08-17），已归档；
  - 判定证据（试查询 + v1.0→v1.1 变化）见附录 A（若采纳）。
- **可选**：同文件新增 `## 附录 A：2026-08-17 判定证据`，只并入 E1/E2/E3（不并入 21 行主表）。是否值得由老板定（U-11）。

## 5. 拟删除/拟归档副本

- 两份 analysis → `docs/.local/archive/2026-11-08/docs/analysis/`（按归档协议，保留原文）。
- 归档后：`config/site_capabilities.yaml` 头部注释的“数据来源”仍指向旧路径，需改为“已归档 + 现行见本文件”（见 §6）。

## 6. 需同步更新的引用

| 引用点 | 动作 |
|---|---|
| `config/site_capabilities.yaml` L3-4 注释 | 改为“分类方案见 docs/design/...；2026-08-17 结果已归档至 docs/.local/archive/2026-11-08/...” |
| `docs/DOCUMENTATION_MAP.md` 两行（partial/status） | 删除或标“已归档” |
| `docs/reference/implementation-digest.md` L75、L134 | 改为“来源已归档”，或保留历史引用并注明 |
| `docs/design/site_classification_v1.md` | 新增 §6（见上） |

## 7. 合并后需跑的门禁

- `python scripts/check_docs_drift.py`
- `python -m pytest tests/test_check_docs_drift.py -q`
- 若改 `config/site_capabilities.yaml` 注释：`python -m pytest tests/test_routing_scorer.py tests/unit/query/routing -q`（YAML 解析回归）
- `python scripts/check_g_037_trigger_alignment.py`（确认未触碰触发表）

## 8. 风险与不确定点

- **风险（低）**：不合并结果表，唯一损失是“21 行结果不再在文档里一眼可见”；可用一行命令从 YAML 生成。
- **不确定**：E1/E2/E3 是否值得作为附录保留（U-11）；design 的 §6 是唯一新增内容，是否接受“文档只留方案+指针”（U-10）。

---

# G5｜`docs/query/README.md`

## 1. 源文件清单

| 文件 | 大小/行数 | 内容 |
|---|---:|---|
| `docs/query/README.md` | 9,503 B / 233 行 | 查询**引擎**：路由、渐进搜索、分桶、配额、断点续传、Metrics |

## 2. 权威版

- **查询引擎**：`docs/query/README.md` **自身**（目前唯一引擎文档）
- **适配器层**：`docs/architecture/modules/query.md`（标题即“查询适配器 Query Adapters”，只覆盖 `pilotstd/query/adapters/`）

## 3. 独有内容清单

**结论：四节内容全部只在 `docs/query/README.md`，`modules/query.md` 一节都没有**；因此不是“合并”，而是“保留”。

| # | 内容 | 源位置 | modules/query.md 是否有 | 核验 |
|---|---|---|---|---|
| Q1 | `ADAPTER_TYPE_MAP` 完整路由链（gb/industry/db/iso…）+ 权重 | §路由策略（L7-19） | **无** | 存在；但源码行号已变：doc 写 `search_strategy.py:252-294`，实际 L275 起 |
| Q2 | 路由决策树（6 步：CODE_ROUTES→DB 正则→classify→FOREIGN→len≤4→兜底） | §路由决策树（L21-41） | **无** | 图是 6 步，但标题/正文称“7 层”，**自相矛盾**；且 `_routing.py` 现在**先走 scorer 动态路由**再回退此树，文档未写 |
| Q3 | v2 三级漏斗 + IntentParser + RouteChain（2026-11-07 默认） | §v2 路由（L43-59） | **无** | 与 `router_v2.py:386-391`（默认 v2）一致；但节内仍是 `<!-- TODO -->` |
| Q4 | 分桶/小桶/溢出/配额/断点续传/Metrics | §分桶（L76-121）、§配额（L123-161）、§断点续传（L163-207）、§Metrics（L221-233） | **无** | 结构仍成立；个别行号可能漂移 |
| — | 22 适配器摘要 | §22 个适配器（L209-219） | modules/query 有更全的 22 行清单 | 重复，且 README 只列 5 个性能指标 |

**过时/需修正点（不构成合并）**：`ADAPTER_TYPE_MAP` 行号；`7 层` vs 6 步；未写 scorer 动态路由；头部“最后更新 2026-07-27”与 v2 段（2026-11-07）矛盾；`batch_state` 行号 `migrations.py:427-439` 可能漂移。

## 4. 拟并入位置

**无（不合并）**。执行轮只需就地修正 `docs/query/README.md`：
- 头部日期改 2026-11-07；
- Q1 行号改 `search_strategy.py:275`；
- Q2 标题改“路由决策树（6 步兜底；动态评分优先）”并补一句 scorer；
- 删除/保留 TODO 由老板定（U-14）。

## 5. 拟删除/拟归档副本

**无。** 两份文档都保留；`modules/query.md` 继续作为适配器文档。

## 6. 需同步更新的引用

| 引用点 | 动作 |
|---|---|
| `docs/architecture/modules/query.md` L146 | 链接 `../../query/README.md` 正确，**不改** |
| `docs/adapters/README.md` L101 | “更新 docs/query/README.md 路由配置说明”正确，**不改** |
| `docs/DOCUMENTATION_MAP.md` L61 | 更新日期列（2026-08-20 → 2026-11-07） |
| `docs/index.md` | 未引用 query/README，**不改** |

## 7. 合并后需跑的门禁

- `python scripts/check_docs_drift.py`
- `python -m pytest tests/test_check_docs_drift.py -q`
- `python scripts/check_g_032_doc_health.py`（若清单含 query/README；当前不含，可跳过）

## 8. 风险与不确定点

- **风险（低）**：若强行把四节并入 `modules/query.md`，会把“适配器文档”变成“引擎+适配器混合文档”，并丢失 README 作为引擎入口的可发现性。
- **不确定**：`7 层`是否为笔误（实际 6 步）（U-12）；v2 TODO 是否本轮补（U-14）；scorer 动态路由是否仍属 v1 路径（v2 默认后是否还走 `_resolve_base_route`）**需代码 owner 确认**（U-13）。

---

# G6｜`docs/plans/README.md`

## 1. 源文件清单

| 文件 | 大小/行数 | 内容 |
|---|---:|---|
| `docs/plans/README.md` | 6,312 B / 46 行 | “只放 Active 计划”的索引：17 条计划链接（6 有效 + 11 失效）+ 2 条关联文档（1 失效）+ 生命周期 |

## 2. 权威版

`docs/ROADMAP.md`（唯一排期/在办清单）。但 **ROADMAP 自身已过期**：头部 `当前版本 v0.151.2`（实际 0.178.0）、S5 里程碑 2026-11-01 已过、未收录 2026-10-28 之后的 10 份部署/验证计划。

## 3. 独有内容清单

### 3.1 12 条失效链接（逐条标注现在在哪）

| # | README 链接 | 现在位置 |
|---:|---|---|
| 1 | `batch2-security-audit-design.md` | `docs/.local/archive/2026-10-24/docs/plans/batch2-security-audit-design.md` |
| 2 | `batch5-terminology-design.md` | `docs/.local/archive/2026-11-08/docs/plans/batch5-terminology-design.md`（W2-A 移入） |
| 3 | `moviepilot-investigation/01-moviepilot-notification-report.md` | `docs/.local/archive/2026-10-24/docs/plans/moviepilot-investigation/…` |
| 4 | `moviepilot-investigation/02-pilotstd-gap-analysis.md` | `docs/.local/archive/2026-11-08/docs/plans/moviepilot-investigation/…`（W2-A 移入） |
| 5 | `moviepilot-investigation/03-user-needs-and-aggregation-recheck.md` | `docs/.local/archive/2026-10-24/docs/plans/moviepilot-investigation/…` |
| 6 | `dual-end-investigation/01-architecture-recon.md` | `docs/.local/archive/2026-10-24/docs/plans/dual-end-investigation/…` |
| 7 | `dual-end-investigation/02-cli-and-signal-path.md` | `docs/.local/archive/2026-10-24/docs/plans/dual-end-investigation/…` |
| 8 | `notification-system-design/01-channel-capabilities.md` | `docs/.local/archive/2026-10-24/docs/plans/notification-system-design/…` |
| 9 | `notification-system-design/03-impl-design-D.md` | 同上 |
| 10 | `notification-system-design/04-refactor-P.md` | 同上 |
| 11 | `notification-system-design/05-refactor-decision.md` | 同上 |
| 12 | `../history/decisions-summary.md`（关联文档） | `docs/.local/archive/2026-10-24/docs/history/decisions-summary.md` |

### 3.2 仍有效的计划条目

| 类型 | 条目 | 现状 |
|---|---|---|
| 链接有效（6） | `notification-redesign/00-README.md`、`notification-refactor-design.md`、`notification-system-design/00-framework.md`、`02-framework-update.md`、`06-spec-and-phasing.md`、`07-impl-design-A.md` | 均在 `docs/plans/`；属**已完成/待批设计**，不是“在办执行计划” |
| README 未列、但真实在办（10） | `2026-10-28-production-deployment-decision.md`、`2026-10-29-a27-p1-design.md`、`2026-10-29-a28-switch-inventory.md`、`2026-10-29-multiuser-inventory.md`、`2026-10-29-stage-completion-summary.md`、`2026-10-29-suspended-items-plan.md`、`2026-10-30-a28-phase2-plan.md`、`2026-10-31-a21-migration-plan.md`、`2026-10-31-home-verification-checklist.md`、`2026-11-01-a21-step3-plan.md` | 部署/验证/迁移依据，当前仍有效（`2026-10-29-stage6-record.md` 已由 W2-A 归档） |

## 4. 拟并入位置

| 内容 | 目标 | 目标标题 |
|---|---|---|
| 10 条在办计划（标题/主题/状态） | `docs/ROADMAP.md` | `## 二、已排期` 新增 `### S7 部署与验证（2026-10-28～11-08）`，逐行列 10 条 |
| 6 条通知设计 | **不并入 ROADMAP**（它们是设计稿，不是排期） | 留给 G7：并入 `architecture/notification-system.md` 或归档 |
| 12 条失效链接 | **不并入** | 删除；如需溯源，指向 `.local/archive`（可选，不加进 ROADMAP） |

## 5. 拟删除/拟归档副本

- 合并后 **删除** `docs/plans/README.md`（它是索引，不是计划本体）。
- 6 份仍有效的通知设计文件**不动**（等 G7 决定）。
- 10 份在办计划**原地保留**。

## 6. 需同步更新的引用

| 引用点 | 动作 |
|---|---|
| `docs/DOCUMENTATION_MAP.md` L128 | 删除 `docs/plans/README.md` 行 |
| `docs/ROADMAP.md` | 新增 S7；同时刷新头部版本（`v0.151.2` → 当前 `0.178.0`）与“当前阶段”日期（U-15） |
| `docs/index.md` | 未引用 plans/README，不改 |
| 其他 | 全库仅 DOCUMENTATION_MAP 一处引用（已核） |

## 7. 合并后需跑的门禁

- `python scripts/check_docs_drift.py`
- `python -m pytest tests/test_check_docs_drift.py -q`
- `python scripts/check_g_032_doc_health.py`（确认 MAP 行删除未影响清单）
- `python scripts/check_g_037_trigger_alignment.py`（确认 index/AGENTS 未断）

## 8. 风险与不确定点

- **风险（中）**：ROADMAP 本身过期，直接并入会“新计划挂旧版本/旧日期”；必须先刷新头部与 S5/S6 状态。
- **不确定**：6 份通知设计归 G7 还是本轮一并归档（U-16）；ROADMAP 是否允许本批改版本号（U-15）；`history/decisions-summary` 链接删除还是改指归档（U-17）。

---

# G8｜`docs/.local/压力测试方案.md`

## 1. 源文件清单

| 文件 | 大小 | 内容 |
|---|---:|---|
| `docs/.local/压力测试方案.md` | 50,337 B / 900+ 行 | 全量压测 v10.0（2026-07-01）：冷/热启动、能力映射、CLI/Docker/WinUI 步骤、判据、报告模板 |

## 2. 权威版

`docs/guides/人工测试方案.md`（v3.1，2026-06-09，2026-10-24 仍被引用）：人工 GUI 全流程 + 压力指标 P1–Pn。

## 3. 独有内容清单

| # | 内容 | 源文件位置 | 核验结果 |
|---|---|---|---|
| P1 | **冷/热启动策略**：CLI 冷启（独立进程、冷缓存、初始化开销）+ WinUI 热启（常驻、热缓存、稳态并发）+ 互补关系表 | §测试设计原则（L7-43） | **概念仍有效**；CLI 入口 `python -m pilotstd.cli.commands` 仍存在（`__main__.py`），WinUI 细节（8-worker、QTimer）需按现行 FlowEngine 改写 |
| P2 | **分步执行原则**：每步前置检查、三步串行 CLI→Docker→WinUI、各步边界 | §核心数据 → 分步执行原则（L58-67） | **仍有效**（方法论） |
| P3 | **PASS 判据结构**：流程状态 FULL_PASS、凭证预检、适配器统计报告非空、日志解析失败率 <5% | §第四步 → 代码质量门禁/文档同步/测试通过率/汇总指标（L653-688） | **结构仍有效**；其中数字/清单过时（见下） |
| P4 | **已知限制 5 条**：自更新不可测、CLI 不触发定时任务、公告实时数据不可回放、OCR 依赖第三方、WinUI 乙轮依赖 Docker | §7 已知限制（L727-738） | **大部分仍有效**；OCR 现已支持本地 provider（`ocr.provider=local`），该条需改写 |
| — | 能力-场景映射 3 表（CLI/WinUI/Web） | §0（L81-137） | **大量路径过时**：`query/engine.py`、`manager/facade.py`、`ui/main_window.py`、`ui/controllers/auto_run_mixin.py`、`announcement/ocr.py`、`organizer/expire_handler.py` 均已是包/改名/不存在（实测 6 处 N） |
| — | 测试通过率基线 623/104、Docker 端点 46/≥42、`check_docs_sync.sh` | L668-688、L926+ | **过时**：当前后端 6000+、前端 346；端点数量已变；`scripts/check_docs_sync.sh` 已删除（技术债 T-14） |
| — | CLI 1.1–1.9/Docker/WinUI 详细步骤 | L345-651 | 细节依赖旧模块路径，**不宜原样搬** |

## 4. 拟并入位置

| 内容 | 目标 | 目标标题 |
|---|---|---|
| P1 冷/热策略（改写为“设计原则”，不写死 worker 数） | `docs/guides/人工测试方案.md` | 新增 `## 六、全量压测判据（自 v10 并入）` → `### 6.1 冷/热启动策略` |
| P2 分步执行原则 | 同上 | `### 6.2 分步执行与前置检查` |
| P3 PASS 判据结构（去掉旧数字） | 同上 | `### 6.3 全量 PASS 判据（结构）` |
| P4 已知限制（OCR 条改写为“本地/云端两种 provider”） | 同上 | `### 6.4 已知限制` |

## 5. 拟删除/拟归档副本

- 源文件本来就在 `docs/.local/`（本地归档区），**保持原地，不重复搬运、不删除**。
- 若要更清晰，可在 `.local/archive/2026-11-08/docs/` 下建软索引？**不建议**（同一文件两处引用会混乱）。

## 6. 需同步更新的引用

| 引用点 | 动作 |
|---|---|
| `docs/guides/人工测试方案.md` L12 | 现引用 `本机源码全量压力测试方案.md`（不存在）→ 改为“源码级全量判据见 §六” |
| `tests/stress_driver.py` L6/L8/L2158 | 注释仍指向 `docs/压力测试方案.md v8.0`（旧路径）→ 改为 `.local/archive/.../压力测试方案.md` 或“见 §六” |
| `docs/DOCUMENTATION_MAP.md` | 该文件不在 MAP（在 .local），无需改 |

## 7. 合并后需跑的门禁

- `python scripts/check_docs_drift.py`
- `python -m pytest tests/test_check_docs_drift.py -q`
- `python scripts/check_g_032_doc_health.py`（人工测试方案不在清单；可跑确认）
- `python scripts/check_g_037_trigger_alignment.py`

## 8. 风险与不确定点

- **风险（中高）**：把 v10 数字（623/104、46 端点）原文搬入会让新文档立刻失真；只搬“结构”是安全线。
- **风险（高，安全）**：**权威版 `docs/guides/人工测试方案.md` L48-49 仍含明文百度 OCR `api_key`/`secret_key`，且该文件被 git 跟踪**。本工单只读，未修改；建议老板轮换并脱敏（见 U-22）。
- **不确定**：P1 的 WinUI 细节改写程度（U-19）；P4 的 OCR 限制是否仍保留（U-20）；压力测试方案是否整体仍有执行价值（U-21）。

---

## 附：与第一轮 `合并建议.md` 的差异（供老板对照）

| 组 | 第一轮结论 | 本轮核验后 | 变化原因 |
|---|---|---|---|
| G1 | Merge（1 份） | **不整体合并**，保留 + 标注 | 发现 4 类独有且仍有效内容（公告双表/回调/状态契约/v68），且 ADR-010 指定其为 Handler 决策载体 |
| G2 | Merge（1 份） | **部分合并**，5 条有效 | 发现后半段有 2026-10/11 的 Action/E2E 内容，非“整份旧版” |
| G3 | Merge（1 份） | **合并**（同） | 但需改 G-032 清单；角色表不并入 |
| G4 | Merge（2 份） | **不合并结果表**，只加指针/可选证据 | YAML 已是运行时 SSOT |
| G5 | Merge（1 份） | **不合并**，两份职责不同 | `modules/query.md` 是适配器文档，不是引擎文档 |
| G6 | Merge（1 份） | **合并 10 条在办计划**，删 README | 失效链接 12 条；6 份设计稿归 G7 |
| G8 | Merge（1 份） | **部分合并**（原则/判据结构） | 映射表/数字基线过时 |





