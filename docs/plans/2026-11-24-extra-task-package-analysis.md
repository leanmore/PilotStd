# 增量问题池（附加任务包）执行分析 — 2026-11-24

> 依 `AGENTS.md §0.0`：收到任务包先出本分析再动手。本文记录**分析结论 + 执行记录**，
> 6 项必填逐项可查。任务包原始分级：P0（前端修复，穿插）/ P1（摸底下发）/ P2（重度开发）。

---

## 1. 问题归属（每条落到模块/目录/端点）

| 编号 | 问题 | 归属（实测定位） |
|---|---|---|
| P0-1 | 日期控件 × 与日历图标不统一 | `web/src/components/ui/AppDatePicker.vue`（全站唯一日期实现；`AppCalendar.vue` 是其薄封装） |
| P0-2 | 下拉框中文垂直不居中 | `web/src/components/ui/AppSelect.vue`（全站唯一 Select 实现） |
| P0-3 | 公告翻页需刷新 | `web/src/views/AnnounceView.vue`（`<Paginator>` 未绑 `:first`） |
| P0-4 | 左侧工作栏不随动 | `web/src/components/AppSidebar.vue`（`.sidebar` 为 `position:static` + flex stretch） |
| P1-5 | 88 个「未知」标准定性 | 后端 `standards status` 判定 + `/api/standards/status` + `announcement_record` 数据 |
| P1-6 | 企微 vs TG 通知信息量 | `pilotstd/core/notification/`（`_builders_*.py` / `renderer*.py` / `channel_spec.py`） |
| P1-7.1 | API/ASME 编号识别 | `pilotstd/core/std_utils.py::parse_std_number` + `web/src/utils/standardParser.ts` |
| P2-7.2 | 新增/评估适配器 | `pilotstd/query/adapters/`（API Webstore / ASME / 重庆 / 福建；评估 全国团标 / 国家能源局） |

---

## 2. 类别聚合（按「问题类」而非逐条）

| 问题类 | 类内条目 | 全量复核结论（**不是只修用户指出的那几处**） |
|---|---|---|
| **A. 表单控件框体不一致** | P0-1 | 全站 7 处日期控件全走 `AppDatePicker`/`AppCalendar`，改一处即全覆盖；业务代码**零裸用** `primevue/datepicker`（代码审计 + `main.ts` 全局注册核对） |
| **B. 固定高盒子文字垂直偏移** | P0-2 | 自建「文字墨迹偏移探测器」扫描 7 个页面所有「固定高 24–64px + 单行文本」控件：**除 `.card-header`（区块标题，刻意上对齐）外 0 处**；`line-height:var(--line-height-none)` 全量 7 处均为独立大字/弹性居中，无同类形态 |
| **C. 受控分页缺 `:first`** | P0-3 | 全站 4 个 `Paginator` **全部**缺 `:first`：`AnnounceView`（用户报的）、**`OrganizeView`、`PendingView`（未报但同缺陷：均从存储恢复 page）**、`TaskView/TaskHistoryList`（受控组件，父级重置页码会错位）→ 4 处全修 |
| **D. 长页面侧栏不固定** | P0-4 | 全站仅 1 个侧栏（`AppSidebar`）；其余 `position:sticky/fixed`（`AppHeader`、悬浮按钮、移动端底部导航、`NotificationLogsView` 表头）均为各自设计意图，非同类缺陷 |

**提炼出的共性判据（后续新页面可复用）**：
1. 有边框的 PrimeVue 复合控件，边框必须只画在**一个**层级（外层或多层叠加即成"胶囊"）。
2. 固定高度容器内的文本，必须用 `flex + align-items:center`，**不能**靠 `line-height` 猜。
3. 页码/分页索引凡有「持久化/父级可重置」状态的，`Paginator` 必须绑 `:first`。
4. 长页面侧栏必须 `sticky` + 视口高 + 内部滚动，不能靠 flex stretch。

---

## 3. 改动面与依赖

| 组 | 文件 | 冲突点 |
|---|---|---|
| P0-1 | `components/ui/AppDatePicker.vue` | 与 P0-2 同目录但**不同文件**，无冲突 |
| P0-2 | `components/ui/AppSelect.vue` | 同上 |
| P0-3 | `views/AnnounceView.vue`、`OrganizeView.vue`、`PendingView.vue`、`TaskView/TaskHistoryList.vue` | 4 文件独立 |
| P0-4 | `components/AppSidebar.vue` | 独立 |
| 测试 | `views/AnnounceView.pagination.test.ts`（新）、`e2e/p0-ui-regressions.spec.ts`（新） | 独立 |
| 门禁联动 | `scripts/design_token_baseline.json` → `docs/governance/gates.md` → `docs/governance/README.md` | **三级联动**，必须同批提交 |
| P1-5/6/7.1 | 各自只写 `docs/plans/` 报告 | 互不冲突 |

---

## 4. 并行 / 串行判定

**关键路径（串行，主线独占）**：
```
P0 修复 → 四件套 + 门禁（含 G-055 基线 → G-031 两级文档联动）→ 提交 → CI 绿 → 合并
```

**并行组（互不依赖，可同时跑）**：
- 并行组 1：P1-5（未知标准定性）/ P1-6（通知对照）/ P1-7.1（编号识别）—— 三个只读分析，
  共享同一生产只读接口但**不同代码面**，无写冲突 → **已派出 3 个子智能体**（`p1-unknown` / `p1-notify` / `p1-api-asme`）。
- 并行组 2：P0-1 与 P0-2（不同文件、不同 CSS 类）可交替；P0-3 与 P0-4 同理。
- 主线在等待子智能体时：做 P0 收尾与门禁预检，不空等。

**串行约束**：P2-7.2 依赖 P1-7.1 的《编号识别缺口报告》（先知道缺口，才知道适配器要补什么字段）。
→ P2 必须排在 P1-7.1 之后，不得并行。

---

## 5. 验收方式（每条可量化）

| 编号 | 验收证据 | 实测结果 |
|---|---|---|
| P0-1 | 计算样式断言：外层 1px 边框、下拉按钮 `border=0/background=transparent`、× 与日历图标同色同尺寸 | ✅ `clear=14×14`、`dropSvg=14×14`、同色 `rgb(148,163,184)`；e2e 断言通过 |
| P0-2 | 文字墨迹中心 vs 容器中心偏差 ≤2px | ✅ **-9.97px → -0.5px**；e2e 断言通过 |
| P0-3 | 翻页/刷新后「高亮页码 == 数据页」 | ✅ 刷新后高亮 2 == 第 2 页内容；单测 3 例锁定 `first === page*rows` |
| P0-4 | 滚到底 `sidebar.top >= -1` 且导航可见；高度 ≤ 视口 | ✅ `position=sticky`、`height=900=视口`、滚到底 `top=0` 可见 |
| P1-5 | 88 条全量清单 + 定性分布 | ⏳ 子智能体进行中 |
| P1-6 | 通知模板对照表（覆盖全部事件） | ⏳ 子智能体进行中 |
| P1-7.1 | 编号识别缺口报告（期望 vs 实际） | ⏳ 子智能体进行中 |

---

## 6. 门禁与约束预检（**提前查清，不提交时才撞**）

| 门禁 | 为什么会触发 | 处置 |
|---|---|---|
| **G-055** 设计令牌 | 新增 `transparent` / `0` / `none` / `100vh` / `top:0` 等 9 处归零声明 | 先尽力消除（删掉 `border-radius:0`×2、`flex-shrink:0`、`outline` 尝试、`height:100%`），仍必要 6 键 9 次 → 按流程 `--suggest-baseline` 分类后**人工并入基线**（B 155→156、C 621→629） |
| **G-031** 文档联动（三级） | 改 `scripts/design_token_baseline.json` ⇒ 需 `docs/governance/gates.md`；改 `docs/governance/` ⇒ 需 `docs/governance/README.md`；且**读的是暂存区** | 三级同批更新 + `git add` 后再跑检查 |
| **G-013** 修复须带测试 | `fix:` 提交 | 补 3 例单测 + 3 例 e2e |
| **G-012/G-047/G-050** | 新增注释/日志 | 注释密度已一次性通过；无新增中文日志硬编码 |
| **G-010** 代码规模 | 新测试文件 | 有效行均 <400 |
| 前端四件套 | 改 `web/` | `type-check` / `lint` / `test` / `build` 全跑 |

> **教训（已写入 AGENTS.md §0.0）**：本次门禁链是**提交时才逐级撞出来**的
> （G-055 → G-031 gates.md → G-031 README），本应在动手前一次性列出。已固化为必填第 6 项。

---

## 7. 执行记录

| 阶段 | 状态 |
|---|---|
| 分析（本文） | ✅ |
| P0-1/2/3/4 修复 + 类内全量复核 | ✅ 提交 `e5b20338` |
| P0 回归测试（单测 3 + e2e 3） | ✅ |
| P1-5 / P1-6 / P1-7.1 摸底 | ⏳ 3 个子智能体并行中 |
| P2-7.2 适配器 | ⛔ 待 P1-7.1 结论后启动 |
| 主线状态 | 部署验收已完成（`0e92e5d2`，batch1 10/0）；本分支 PR 待开 |
