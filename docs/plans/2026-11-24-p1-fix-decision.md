# P1 摸底结论 → 修复决策（2026-11-24）

> 三份摸底报告已完成：P1-5 / P1-6 / P1-7.1。本文把结论收敛成**修复批次**（做什么、按什么顺序、风险、验收）。
> 依 `AGENTS.md §0.0`：先分析决策，再执行。

## 输入

| 报告 | 核心结论 |
|---|---|
| `2026-11-24-p1-unknown-standards.md` | 88「未知」= **作废 58 + 即将实施 20 + 未生效 10**；数据/解析问题 **0**。主因是**聚合口径缺条目**，不是采集失败 |
| `2026-11-24-p1-notification-parity.md` | 44 事件；企微**应用形态（模板卡片）** 丢级别前缀（27）、丢详情链接（7）、丢列表计数（5），**34/44 受影响**；反向缺陷：`auto_backup` float 让 **TG 整条丢失**（生产实证 id=2034） |
| `2026-11-24-p1-api-asme-gap.md` | 40 样本三通道实跑：`ASME B16.5-2020` 被拆成 `ASMEB1/6/5`（**自己和自己比不过**）；`B31.3`/`Y14.5` 直接 MISS；BPVC 体系几乎全不识别；前端解析 38/40 全盲 |

## 修复分批（按「严重度 × 风险」排序）

### 批次 A（P0 严重度，已派工，并行）

| ID | 问题 | 文件 | 风险 | 验收 |
|---|---|---|---|---|
| A1 | 作废 58 条被折叠进 unknown | `pilotstd/manager/standard_service.py`（~6 行） | 低（无 Schema/API 契约变更） | `inactive 116→174`、`unknown 88→30`；单测锁定 |
| A2 | ASME B 系列拆号 → 自 mismatch | `pilotstd/core/std_utils.py`（后处理，不动共享正则） | 中（核心解析器，须防回归） | `ASME B16.5-2020`→`ASME/16/5/2020`；`B31.3`/`Y14.5` 可解析；既有族零回归 |
| A3 | `auto_backup` float → TG 整条丢失 | `pilotstd/core/notification/_builders_system.py`（1 行 `str()`） | 极低 | 渲染不抛 `TypeError`；生产日志出现 telegram success |
| A4 | 企微卡片丢级别/链接/计数 | `pilotstd/core/notification/renderer_wecom_card.py`（补 `level_prefix`、`jump_list`、列表计数） | 中（影响 34/44 事件的呈现，但不改发送链路） | 卡片 JSON 含级别前缀/详情 URL/「共 N 条」 |

### 批次 B（P1，紧随 A 之后）

| ID | 问题 | 文件 |
|---|---|---|
| B1 | 企微卡片拒收降级按字符截断（2000 汉字 > 2048 字节） | `channels/wechat.py` 改 `split_for_channel` |
| B2 | 无 blocks 时 markdown 丢标题 | `renderer.py` / `renderer_base.py` |
| B3 | 直连安全告警不认企微应用形态 | `security_notifier.py` |
| B4 | 5 个「缺对象」事件补对象 | `_builders_*.py` 单点 |
| B5 | BPVC 卷/册/篇识别 | `std_utils.py` 新增分支 + `scan/parser/_constants.py` |
| B6 | API 类型词污染代号（`API STD`→`APISTD`） | `std_utils.py` + `query/search_strategy.py` |

### 批次 C（P2，需窗口/跨端）

| ID | 问题 | 说明 |
|---|---|---|
| C1 | 前端 `standardParser.ts` 38/40 全盲 | 建议**前端复用后端已解析字段**而非再写一套正则；需四件套 |
| C2 | 即将实施 / 未生效 的统计桶与枚举归一 | 跨前后端 + 需产品确认三分类口径 |
| C3 | 写入端 `effect_status` 不归一 + 存量清洗 | **写生产库需维护窗口** |
| C4 | 新增/评估外部适配器（API Webstore / ASME / 重庆 / 福建） | 依 A2、B5 结论落地；逆向需集中窗口 |

## 依赖与顺序

```
A1 ─┐
A2 ─┤ 并行（文件互不重叠）
A3 ─┤
A4 ─┘
      ↓ 全部合入后统一跑四件套 + 门禁 + CI
B1..B6 ── 可再并行（不同文件），但需 A2/B5 先定解析口径
C1 ── 依赖 A2/B5（先定后端口径，前端再复用）
C4 ── 依赖 A2/B5（先知道缺口，才知道适配器补什么）
C3 ── 红线：生产写库，必须维护窗口授权
```

## 门禁预检（提前列清，不提交时才撞）

| 门禁 | 触发点 | 处置 |
|---|---|---|
| G-013 | `fix:` 提交 | 每个 fix 必须带测试 |
| G-031 | 改 `pilotstd/core/` → `docs/architecture/modules/core.md`；改 `pilotstd/manager/` → `docs/architecture/modules/manager.md`；改 `pilotstd/core/notification/` → `core.md` | **同批更新对应模块文档** |
| G-030 | 新增技术债标记 | 不新增 `TODO/FIXME` 裸标记 |
| G-047 | 中文日志/文案 | 用 i18n 或 `# i18n-allow` |
| G-010 | 新测试文件 | 有效行 <400 |
| G-055 | 新增视觉字面量 | 本次无前端样式改动（A 批全是后端/渲染器） |
| 前端四件套 | C1 会改 `web/` | type-check/lint/test/build |

## 执行结果（2026-11-24 收尾）

| 批次 | 状态 |
|---|---|
| A1 状态口径（作废计入废止族）| ✅ 5c501fbb（inactive 116→174 / unknown 88→30；**另发现并修复首页同类扩散点** _file_index_query.py） |
| A2 ASME 字母系列拆号 | ✅ 9e884765（22 例；48 样本行为差分 changed=0；1130 消费者零回归） |
| A3 企微卡片级别/链接/计数 | ✅ 并入 73be260f |
| A4 auto_backup float 整条丢失 | ✅ 并入 73be260f（一处 str() 覆盖四渠道） |
| 后端相关全量验证 | ✅ 1420 passed |
| 门禁 | ✅ 全绿（含 mypy 修正 jump_list 注解） |
| B1 企微降级分段 | ✅ 并入 c7be4541（字节口径 split_for_channel，超长多段） |
| B2 markdown 补标题 | ✅ 并入 c7be4541（仅 MarkdownRenderer） |
| B3 安全告警应用形态 | ✅ 并入 c7be4541（应用形态优先、Webhook 兜底） |
| B4 5 个事件补对象 | ✅ 35e3f12e（scan_empty/query_empty/archive_failed/normalize_failed/auto_pipeline_summary） |
| B5 ASME BPVC | ✅ 8a0da208（新增 std_utils_bpvc.py，Section/Div/Part/册篇字母） |
| B6 API 类型词 | ✅ 8a0da208（新增 std_utils_api.py，APISTD→API+类型词） |
| 后端广域验证 | ✅ **1763 passed, 1 skipped** |
| C1..C4 | ⏳ C1/C2 跨前端需四件套；**C3 写生产库需维护窗口**；C4 依赖 B5 已就绪可启动 |

## 执行纪律（本次已犯并纠正）

- ❌ **不要在子智能体编辑期间跑全量门禁/提交** → 未定稿文件会把门禁打红（本次已发生一次）。
- ✅ 等并行批次全部完成 → 一次跑门禁 → 分组提交。
- ✅ 每个 fix 的测试先红后绿。
