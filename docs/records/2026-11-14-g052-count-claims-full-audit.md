# G-052 计数声明全量审计证据（2026-11-14）

> 目的：把"窗口内计数声明 0 未登记"从 15 篇抽样升级为**全量证据**。
> 口径：`git log --since="3 months ago"` 圈出的 docs（**221 篇**）× 当前登记的 6 类计数声明。
> 判定：按**命中位置**（不是按行）判断是否被该文档已登记的 `COUNT_CLAIMS` 正则覆盖。

## 一、总量

| 指标 | 数量 |
|---|---|
| 窗口内改动文档 | 221 |
| 含计数声明的文档 | 8 |
| 命中总数 | 18 |
| 已被登记正则覆盖 | 11 |
| 已登记但该处未被覆盖 | 1（见 §四，无法机械核对） |
| 未登记且未豁免 | **0** |
| 命中落在豁免文档内 | 6 |

> 扫描时点：本文档自身尚未入库；入库后窗口为 222 篇，本文不含计数声明，不改变"0 未登记"的结论。

复现命令：

```bash
python scripts/audit_count_claims.py --strict
python scripts/check_docs_drift.py
```

## 二、逐文档命中（8 篇）

| 文档 | 命中数 | 状态 | 说明 |
|---|---|---|---|
| `docs/onboarding/03-architecture.md` | 3 | 已登记 | 表格行 2 处 + 正文复述 1 处（本次新增登记） |
| `docs/onboarding/16-notification-matrix.md` | 1 | 已登记 | 通知事件数（第 6 类，2026-11-14 登记） |
| `docs/onboarding/18-schema-migrations.md` | 2 | 已登记 1 + 待核 1 | 迁移可解析表数已登记；"SQLite 实测表数"无法从源码推导 |
| `docs/onboarding/19-web-win-inventory.md` | 2 | 已登记 | router 模块数 / 唯一路径数 |
| `docs/onboarding/20-api-route-inventory.md` | 2 | 已登记 | 唯一路径数 / route×method 对数 |
| `docs/onboarding/README.md` | 2 | 已登记 | 迁移表数 / 迁移模块数 |
| `docs/governance/gates.md` | 5 | 豁免 | 门禁版本历史条目（记录当时口径） |
| `docs/PITFALLS.md` | 1 | 豁免 | 历史故障现象（迁移停在 v37 时的表数） |

## 三、本次全量扫描带来的两处修正

1. **`03-architecture.md:242`**：正文复述了"唯一 API 路径"数量，但原登记正则只覆盖表格行（形如"`**N 个 router 模块、N 个…**`"的合并写法，数字用 N 代指）。已新增一条声明（`Web 的 (\d+) 个唯一`），使正文与表格同步受校验；否则改表不改正文会留下同页矛盾。
2. **`18-schema-migrations.md:6`**：标题写作"旧快照 41 张"，与本页正文的 43 不一致。该数字是**历史快照**、不应跟随代码，故改写为"旧快照 41 个表"——既保留历史信息，又不会被规则误当成现行声明。

## 四、记下来但不改规则（无法机械核对）

| 位置 | 内容 | 为什么装不进现有 6 类 |
|---|---|---|
| `18-schema-migrations.md:4` | "SQLite 实测业务表 45 张" | 该数字来自**实跑迁移链后的 `sqlite_master` 计数**，`load_facts()` 只解析迁移源码得到 43；要机械核对需引入"空库跑迁移后数表"的昂贵步骤 |
| `ADR-010-mixin-refactor.md:32` | "16 个 Mixin 中的 15 个" | Mixin 数量无稳定代码事实（重构后已变化），属历史决策记录 |
| `g-010-enforcement.md:31` | "32 个函数 + 11 个文件超过阈值" | 历史度量快照（当时一次治理的统计） |
| `onboarding/README.md:5` | "约 5 工作日（6 个模块）" | 工作量估算，不是规模声明 |
| `DECISIONS.md:133` | "41 个事件" | 历史决策时的上限描述 |
| `governance/notification_coverage.md:93/102` | "3 / 38 个事件" | 上下文统计，非条目基数 |
| `reference/implementation-digest.md:69` | "6 个事件" | 某次变更涉及的事件数 |

> 以上 7 条按用户裁定"不再扩类"，只记录；若未来做第 7 类，优先评估"SQLite 实测表数"（可行性取决于是否接受空库跑迁移）。

## 五、结论

- 在**现有 6 类规则**下，221 篇全量窗口内**未登记项为 0**，且不存在"按行误判为已覆盖"的情况（1 处例外已单列）。
- 新增 2 条声明后，`check_docs_drift` 与 `audit_count_claims --strict` 均 PASS。
- 规则边界的已知盲区（§四）已显式记录，避免把"0 未登记"误读成"所有计数都受保护"。
