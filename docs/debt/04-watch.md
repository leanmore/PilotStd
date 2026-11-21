# 技术债 · 已修复 / 需观察

> 本文件是 `docs/technical-debt.md` 四分类之一：**需观察**——已处置但需盯住是否复发，或受外部依赖限制只能等事件触发。
> 每条必须有：**状态**、**触发条件（什么情况下要重新动手）**、**复核方式（怎么一眼看出是否复发）**。
> 与 [02-accepted.md](02-accepted.md) 的区别：这里"还能再动"，那里"已决定不动"。
> **最后核实：2026-10-16**（含实测与时间戳）。回主档：[technical-debt.md](../technical-debt.md)

---

## 一、已闭环、但保留了周期复核（4 条）

| # | 条目 | 状态 | 闭环依据（实测） | 复核方式 |
|---|---|---|---|---|
| **W-1** | `frontend-e2e` 的 `playwright-report` 从未产出（每轮告警） | **已闭环**（2026-10-07 修复；2026-10-16 补 CI 侧实证） | 修复前 `ce3c35d7`（run `37631376455`，`2026-10-07T13:47:52Z` 触发）有 1 条 `[warning] No files were found with the provided path: web/playwright-report/`；修复后 `ef469672`（run `37634507535`，`2026-10-07T14:10:34Z`，即 **v0.138.3**）与 `bc490c28`（run `38909620285`，`2026-10-16T13:40:07Z`）**注解数 = 0** | **首选**：`gh api repos/{owner}/{repo}/check-runs/<check_run_id>/annotations`（`frontend-e2e` 应 0 条）。**次选**：产物列表含 `playwright-report`——⚠️ 该产物 `retention-days: 7`，实测 2026-10-07 产出的产物在 2026-10-16 已过期（同批 `e2e-coverage-report`/`gui-coverage-merged` 为 30 天）⇒ **超过 7 天再查必为假阴性** |
| **W-2** | G-044 `aliases` 别名提示 6 → 0 | **已闭环**（2026-10-07） | `python scripts/check_terminology.py --report` 实测：**提示项 0、阻断 0、346/346 通过、豁免 33**（含"别名按语境豁免 **6 个键**"，与文档一致） | `python scripts/check_terminology.py --report` 应 **0 条 aliases 提示、0 阻断** |
| **W-3** | `check_schema_consistency` 的"测试建生产同名表"约束无提示 | **已关闭**（2026-10-05，R16 P2 落地） | 处置为在该脚本 `MISSING>0` 分支新增"中性表名 + RENAME"提示 | 再出现同类阻断时确认提示是否出现 |
| **W-4** | `tests/` 受控测试不在本地门禁路径 | **已关闭**（2026-10-05，R16 P0 落地） | `scripts/check_all.sh:427` 定义 `run_gate_selftests`，`:465`/`:472` 调用（原记录的"流程补强②未实施"已被此取代） | 改门禁脚本/基线时本地应能自动跑到受控测试 |

## 二、观察中（受外部依赖或成本限制，等事件触发）

| # | 条目 | 状态 | 触发条件（何时重新动手） | 复核方式 |
|---|---|---|---|---|
| **V-2** | **T-21** 本地 `vitest run` 偶发「全绿但 exit=1」 | `观察中` | 再次出现 | 立即 `node node_modules/vitest/vitest.mjs run *> log.txt 2>&1` 存全量输出。**2026-10-16 复跑：42 files / 324 passed、exit=0**（仍未复现） |
| **V-3** | **T-35** 配置文件跨进程写锁 | `观察中`（**已决定不引入文件锁**） | 实测到一次并发写丢配置 | 比对 `config.json` 与 `config.json.bak` 的键差异；届时优先"原子写 + 重试 + 写后校验"或 SQLite 配置后端 |
| **V-6** | **T-31** 自动 `chore: bump version` 提交不触发 CI | `观察中` | 出现一次"版本号/CHANGELOG 不一致"事故 | 查 `pilotstd/__init__.py` 与 `CHANGELOG.md` 顶部版本；兜底是 `G-009`（`ci.yml:205`） |
| **V-7** | **平台侧告警**：`ubuntu-latest → Ubuntu 26` 预告 | `观察中`（**残留项有日期**） | **2026-10-19 起**验证仍用 `ubuntu-latest` 的作业（可用 `ubuntu-24.04` 钉住规避） | `gh api repos/{owner}/{repo}/check-runs/<id>/annotations` ⇒ **2026-10-16 实测：`warning=0 / notice=9`**（原文记"24 warning"是**升级前**旧数，已更正；Node20 弃用告警已随批次 A 的 43 处 action 升级清零） |
| **V-8** | `#33` `TaskView.vue` 逼近 G-010 警告线（有效行 399 / 线 400） | `观察中` | 任何编辑 `web/src/views/TaskView.vue` 的提交 | `python scripts/check_g_010_code_size.py`；**2026-10-16 实测**：该文件**未进 >400 名单**（仅 `_migrate_v16_v49.py` 438 与 `event_spec_data.py` 417），且其最后改动为 `5592b71c`（`2026-09-27T10:57:22+08:00`）⇒ 399 行的记载仍成立 |
| **V-9** | `event_spec_data.py`（417 有效行）1b 拆分豁免 | `观察中` | ① 突破 500 阻断档；② 新增变动频繁的业务族 | `python scripts/check_g_010_code_size.py`（2026-10-16 实测 417） |
| **V-10** | `HomeView.vue` 的 grid-layout-plus workaround | `观察中` | 升级 `grid-layout-plus`（`web/package.json:22`） | 删 `layout.value = [...layout.value]` 克隆 → 浏览器实测锁定/解锁后拖拽是否仍生效 |
| **V-11** | G-044 术语覆盖缺口（B-1）：三语严格相等仅覆盖登记键（40/346） | `观察中` | ① 通知文案新增/变更批次；② 术语表扩容专项立项 | `python scripts/check_terminology.py --report` 的"未覆盖说明"行 |
| **V-13** | 工具链**版本漂移**：本地 `ruff 0.15.17` vs 归档配置里钉的 `v0.11.6` | `观察中`（2026-10-16 新增；2026-10-17 入口收口后该钉版**不再被执行**，仅存档） | 本地 `ruff format --check` 报"would reformat"而复现 | `python -m ruff --version` 与 `docs/archive/pre-commit-config.archived.yaml` 中 `ruff-pre-commit` 的 `rev` 比对；**不要按它重排**——那份配置的 31 个 hook 从未执行，现行口径是 CI 的 `ruff check`（G-038）与本地 `ruff check`；实测 `engine.py` 2 处属此类 |
| **V-14** | L1 mypy 口径：`--follow-imports=skip` 下 `download/session.py:38` 的 `[override]` 不报 | `观察中`（2026-10-05 已定性） | 若将来改为 mypy 默认 `follow-imports` | `python -m mypy pilotstd/ docker/ --follow-imports=skip --ignore-missing-imports` ⇒ **2026-10-16 实测 442 文件 0 error** |
| **V-16** | `src/components/TaskManager.vue` 分支覆盖仅 **27.9%**（行 51.85%），失败/重试分支无测试 | `观察中`（2026-11-14 起，P2-08 调查产出） | 随其**下次功能变更**（或 SettingsTabSystem 改动）时补失败分支用例；不在 TaskView 链路，故不进 P2-08 第二批 | `npx vitest run --coverage --coverage.include=src/components/TaskManager.vue --coverage.reporter=json-summary` 看 lines/branches；分支回到 ≥60% 即摘除 |
| **V-17** | G-012 注释密度对**新建脚本**反复红（2026-11-14 两次：0.9%、2.0%），被迫为过门禁补低价值注释 | `观察中`（2026-11-14 起） | 下次改 G-012 时评估：① 新文件是否给一轮过渡期；② 是否改按"公共函数是否有 docstring"而非"行注释密度"；在此之前新脚本按现规则补 3~5 行有效注释 | `python scripts/check_g_012_comment_density.py` 看是否再有新脚本因 DENSITY 红；若同类红第 3 次出现即提规则修改 |
| **V-18** | **`query_metrics` 无法区分 `chain_exhausted` 原因**：冷却/配额/无结果三类计数器在 0 时不落库，`query_metrics` 只剩 `chain_exhausted` 总数（2026-11-13 批量实测仅有 3 个键），归因只能靠日志 | `观察中`（2026-11-15 起，P3-16 实测暴露） | 修 P3-16 时一起改：空链/配额耗尽/无结果分别落 `quota_exhausted`/`no_result` 键（0 也可落或至少记 1 条聚合行），让指标能独立归因；当前先靠 `[NG] tried=`、`[LO]`、`[QUOTA]` 日志行 | 下次 P3-16 相关批次后查 `query_metrics` 是否能区分三类；若仍只有 `chain_exhausted` 总数则升级为待修 |
| **V-19** | **G-055 的 `no-literal` 177 条口径收紧风险**：`0/auto/none/transparent` 等现按策略排除并计入基线（分组 `no-literal`）；若收紧"可映射"定义（例如把 `0` 也当作应走 `--space-0`），会一次性产生大量 `[STALE]` 噪音，掩盖真实清理 | 观察中（2026-11-21 起） | 触发：有人提出把 `0`/`auto`/`none` 纳入令牌管辖，或改动 `scripts/check_design_tokens.py` 的 C 组映射 | 复核：`python scripts/check_design_tokens.py` 的 `[STALE]` 行数；一次涌现 >20 行即说明口径已变，应先重生成基线（`--suggest-baseline`）并人工评审，不得脚本自动改 |

## 三、R15 观察期（2026-10-01 起约一周，**2026-10-16 补收口**）

| 观察点 | 结论 | 依据 |
|---|---|---|
| ① 容器重启后是否掉线（JWT 持久化） | **未见掉线记录**；但未取得部署侧"重启后免登录"的实测证据 ⇒ 保持观察 | `docker/auth.py` / `docker/entrypoint.sh` 共 8 处 `jwt_secret|JWT_SECRET` 实现仍在 |
| ② 配置自愈是否触发 | **未触发过**（好事：说明未发生配置损坏） | 自愈分支在 `pilotstd/core/config/manager.py:201-213`（写前备份 `.bak` + 回滚 + `配置解析失败，已从写前备份回滚` 日志）；全量 `logs/` 搜该文案 **0 命中**（2026-10-16 实测）；`data/config.json.bak` 存在属"每次写盘前的备份"，非损坏证据 |
| ③ docs_sync 误报计数 | **计数未回写、条件已满足** ⇒ 见 V-1 | main 上自 2026-09-27 起 176 次 push 运行 |
| ④ Phase 4 配置审计 / deep-gate 是否纳入 push | **Phase 4 全库无完成记录 ⇒ 视为未启动**；故"再评估"前置未完成、**未到期** | `docs/technical-debt.md` §0.4 原文仅两处提及 Phase 4，无完成记录 |

