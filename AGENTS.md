# AGENTS.md — PilotStd 执行约束

> DeepSeek Harness 启动时自动加载。这里只放**不可协商的约束与入口**；详细步骤在 playbook，不在本文件堆规则。

---

## 零、任务开始前（强制）

非 trivial 任务（排查、设计、改代码、迁移、部署）先做：

1. 检索文档，不靠记忆：
   ```bash
   python scripts/find_docs.py "通知 未读 聚合"
   ```
2. 打开命中的 1~3 篇；优先看 `docs/onboarding/00-how-to-use.md`、`08-known-boundaries.md`、`26-fix-dossiers.md`。
3. 分析/修复/交付时写明“已查阅：路径 + 章节/编号”；无依据不得下根因结论。
4. 修完回写：边界写 `08`，dossier 写 `26`，改动/测试/回滚写 `27`。

### 0.0 收到「任务包 / 多问题清单 / 一批需求」时的第一动作（**禁止直接开干**）

**先产出分析，再动手**。第一个动作不是改代码，是写《任务包分析》并落到
`docs/plans/<日期>-<主题>-analysis.md`，必须包含以下 6 项，缺一不得开始执行：

| # | 必填项 | 判据 |
|---|---|---|
| 1 | **问题归属** | 每条落到模块/目录/端点；说不出位置说明还没查够 |
| 2 | **类别聚合** | 按「问题类」归并（不是按用户列举的条目逐条干）；注明类内还有哪些潜在同类 |
| 3 | **改动面与依赖** | 每条要改哪些文件；哪些共享同一文件/组件/门禁（冲突点） |
| 4 | **并行/串行判定** | 谁和谁无依赖可并行（列出并行组）；谁在关键路径上必须串行 |
| 5 | **验收方式** | 每条怎么证明修好了（可量化指标/截图/接口断言/测试用例） |
| 6 | **门禁与约束预检** | 本次会触发哪些门禁（G-010/G-013/G-031/G-047/G-055…）、需要同步哪些文档、哪些约束会在提交时挡路 |

**执行纪律（排期模型见 `docs/onboarding/31-scheduling-model.md`）**：

任务 = DAG + 受限资源（我的注意力=1、共享工作区写者=1、门禁/CI=1、审查带宽=1）。
**并行不增加这些容量**，无上限地多开 lane 只会把队列搬到我这里。

派工前按四步排程，不许"凭感觉并行/串行"：
1. **建图**：节点 / 依赖边 / lead time / 耦合点（共享文件即未来冲突点）。
2. **找关键路径**（最长路径，决定总用时下界）：其上节点**主线独占、不排队、不空等**。
3. **限 WIP + 分类启动**：WIP 上限 = 最紧资源容量（利用率别超 ~85%）；
   - **前馈型**（lead time 长、低耦合、后续要用，如摸底/长验证）→ **早启动**，后台跑，主线继续；
   - **即用型**（lead time 短、高耦合，如 1~2 行修复）→ **JIT 串行**，临到需要才做。
4. **验证左移 + 整合点批处理**：单测/ruff 在节点内跑；全量门禁/四件套/CI 只在整合点跑一次
   （共享工作区有活跃写者时**禁止跑全量门禁与提交**）。

判据：**协调成本 ≥ 并行收益 → 立即转串行**；节点在关键路径上 → 自己做；
节点会占用同一资源（同文件/同门禁窗口/同审查人）→ 串行。

**隔离用 git，不用"文件切分"**：并行单元 = `分支 + worktree + PR`。
`main` 始终可构建可发布；lane 各自 CI 绿后**按依赖拓扑序**合并，主线统一整合验证。

门禁链**提前查清**（改 `scripts/` ⇒ `gates.md` ⇒ `docs/governance/README.md` 三级联动；
`fix:` ⇒ 必须带测试；新增字面量 ⇒ G-055 基线流程；改 `pilotstd/core|manager/` ⇒ 对应模块文档），
不要提交时才撞出来 —— 返工是本项目最大的成本项。

**派工 prompt 必须带上第 6 项预检出的门禁约束**（否则子任务会产出被门禁打回的代码，主线再返工）：
- G-010：目标文件当前有效行数 + 「警告档 400~500 不允许增长 / >500 阻断」；
- G-013：`fix:` 必须带测试；
- G-031：改哪个模块目录 ⇒ 同批要更新哪份模块文档（子任务只回报、主线改）；
  **注意 CI 有两套映射表**：check_g_031_docs_sync.py（pilotstd/scan/parser/→parser.md）与
  check_module_doc_mappings.py（pilotstd/scan/→scan.md）粒度不同，**两处都要满足**，
  提交前用 DOCS_SYNC_RANGE=<before>..HEAD 分别跑一次；
- G-047：中文日志/文案需 i18n 或 `# i18n-allow`；
- G-055：新增视觉字面量需走基线流程；
- 前端改动：四件套。

每个「同类问题」类做完后，必须回写**全量复核结果**（类内还有多少处、为何不修/已修），
不能只修用户指出的那几处。

---

## 一、环境与版本

| 环境 | 代码 | 后端 | 用途 |
|---|---|---|---|
| 开发 | 本地最新 | 本地/Mock | 写代码；数据不可靠 |
| 验证 | 本地新代码 + Vite | 局域网 Docker | 修复后首选验证 |
| 复现 | Git 旧 commit | 同一 Docker API | 回归/控制变量 |
| 生产 | 已发布 | Docker + 真实数据 | 只读验证；写操作需窗口 |

- **凭证**：`config/docker_creds.json`，含 GBK 注释；按行读取，不直接 JSON 解析。
- **GitHub API**：token 在 Windows 凭据管理器 `LegacyGeneric:target=git:https://github.com`，用 `git credential fill` 读取；禁止打印 token、写文件或提交。
- **版本**：只信 `/api/health` 的 `version` / `schema_version`；本地 tag、`VERSION` 不作部署证据。细节见 `docs/reference/health-check.md`。
- **排查路径**：复现 → 证据 → 假设 → 修复 → 验证 → 收口。

---

## 二、工作流：6 个闸门

| 闸门 | 动作 | 退出条件 |
|---|---|---|
| G0 分诊 | 判断类型（设计/缺陷/数据/部署）与影响端（Web/Win/CLI/Docker） | 能说清类型、影响面、风险 |
| G1 取证 | 文档检索 + 代码搜索 + 日志/DB/健康检查 | 至少 1 条文档依据 + 1 条运行证据 |
| G2 假设 | 一句话写根因/目标 | 假设可被测试或日志证实/证伪 |
| G3 变更 | 最小 diff；逻辑/数据变更先写失败测试 | 改动可追溯到需求 |
| G4 验证 | 单测/契约/四件套/门禁/CI；真实数据 ≥3 条 | 命令跑过、输出看过 |
| G5 收口 | 回写 `08/26/27`；提交；记录部署状态 | 文档与代码同批 |

**停止条件**：

- 没有证据 → 不下根因结论，先查；
- 涉及生产写库/重启/改容器 → 停下，要维护窗口；
- 需求有歧义 → 只问最关键的一个问题；
- 跨 3 个以上模块或改 schema → 先出方案，不直接写；
- 测试失败 → 不进下一闸门；
- 文档未回写 → 不算完成。

---

## 三、不可协商的 8 条

1. **生产红线**：不直接改容器代码、不 UPDATE 生产库、不为测试重启服务。
2. **门禁不绕过**：禁止用 `noqa`/`skipif`/`continue-on-error` 掩盖失败；失败就修。
3. **最小 diff**：只改目标范围；死代码先告知，不擅自删。
4. **测试先行**：逻辑/算法/数据处理变更先写失败测试；GUI/配置/文档可跳过。
5. **先搜再建**：新增函数/常量/迁移/编号前先 grep，确认无重复、无被否决方案。
6. **临时文件出仓**：写 `%TEMP%`；提交消息用 `git commit -F <仓库外路径>`。
7. **文档联动**：核心模块/API/DB 变更同批改对应文档；否则不算完成。
8. **证据优先**：结论附路径+行号+实测输出；不凭记忆、不脑补。

---

## 四、验证入口

- 后端：`python -m pytest <target> -q`；提交前跑相关门禁。
- 前端（改 `web/` 必跑四件套）：
  ```bash
  pnpm.cmd run type-check
  pnpm.cmd run lint
  pnpm.cmd test
  pnpm.cmd run build
  ```
- 门禁：`bash scripts/check_all.sh --fast --guards --local`；CI 以 GitHub Actions 为准。
- 详细清单：`docs/reference/pre-commit-checklist.md`。

---

## 五、交付与提交

交付四要素：

1. 差异表（假设 vs 实测）；
2. 改动文件清单；
3. 验证结果；
4. 自审清单（红线/测试/文档/无关改动）。

提交：Conventional Commits，按逻辑分组；未经用户同意不推送。

---

## 六、能力矩阵

修改 `pilotstd/core/`、`docker/api/`、ADR 或 `docs/` 治理文档前，跑：

```bash
python scripts/generate_capabilities.py
```

生成物 `docs/governance/capabilities_registry.md` 与代码同批提交。

---

## 七、文档生命周期

### 7.1 读取侧（G-037 依赖，勿删）

本节是 G-037 的硬依赖：从下面这张“读文档触发条件表”提取路径，并与 `docs/index.md` 双向对齐。

| 触发条件 | 必须读取的文档 | 文档性质 |
|----------|---------------|---------|
| 涉及数据库/Schema | `docs/architecture.md` | 代码说明书 |
| 涉及公告解析/入库 | `docs/reference/announcement-pipeline.md` | 代码说明书 |
| 涉及公告来源判断 | `docs/reference/announcement-sources.md` | 代码说明书 |
| 涉及下载链/下载适配器 | `docs/reference/download-pipeline.md` | 代码说明书 |
| 开发或修改适配器 | `docs/reference/adapter-development.md` | 人的指引 |
| 涉及前端 UI 组件 | `docs/reference/ui-components.md` | 人的指引 |
| 涉及按钮/视觉规范 | `docs/reference/ui-system.md` | 人的指引 |
| 涉及健康检查/部署排障 | `docs/reference/health-check.md` | 人的指引 |
| 涉及 CI/CD 或门禁 | `docs/ci-lessons.md` | 人的指引 |
| 涉及门禁配置变更 | `docs/governance/gates.md` | 索引（G-031 强制同步） |
| 涉及架构决策 | `docs/adr/` | 索引 |
| 涉及技术债 | `docs/technical-debt.md` | 索引 |
| 查历史决策 / 准备改判 | `docs/DECISIONS.md` | 索引（唯一真相） |
| 编写新代码时 | `docs/reference/coding-standards.md` | 人的指引 |
| 提交代码前 | `docs/reference/pre-commit-checklist.md` | 人的指引 |
| 不确定下一步做什么 / 查排期 | `docs/ROADMAP.md` | 索引 |
| 不确定该读什么 | `docs/index.md` | 索引 |

### 7.2 回写侧

| 文档 | 对应代码范围 |
|------|-------------|
| `docs/architecture.md` | DB/Schema/API/整体架构 |
| `docs/reference/announcement-pipeline.md` | `pilotstd/announcement/` 状态机/流程 |
| `docs/reference/announcement-sources.md` | 来源/字段 |
| `docs/reference/download-pipeline.md` | `pilotstd/download/` 下载链路 |

---

## 八、详细资料在哪

- 工作流/按问题查文档：`docs/onboarding/00-how-to-use.md`
- 当前边界：`docs/onboarding/08-known-boundaries.md`
- 问题 dossier：`docs/onboarding/26-fix-dossiers.md`
- 实施记录：`docs/onboarding/27-implementation-log.md`
- 编码规范：`docs/reference/coding-standards.md`
- 提交前清单：`docs/reference/pre-commit-checklist.md`
- 历史教训：`docs/ci-lessons.md`

> 本文件有长度预算：新增规则前先问“是否跨任务不可协商”。单任务流程写 playbook，不写这里。
