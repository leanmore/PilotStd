# 项目结构化知识日志

> 本文档由 Knowledge Trigger 机制自动维护，CI pre-push hook 检查最后更新时间。
> 与 `~/.claude/projects/` 下的 Auto-Memory 相互独立——前者用于团队审计与 CI 检查，后者是 Claude 会话上下文缓存。

---

## Memory 条目模板

所有 Memory 条目使用以下格式：

### [日期] [类别] [标题]
- **类型**：决策 / 范式 / 放弃 / 规范 / 风险
- **内容**：（1-3句话描述核心事实或决策）
- **关联代码**：涉及的文件路径或模块
- **关联文档**：相关的 spec/plan/reference
- **有效期**：永久 / 至YYYY-MM-DD / 条件解除时

---

## 条目列表

### 2026-07-24 范式 五站Playwright侦查方法论
- **类型**：范式
- **内容**：JSL绕过 + XHR捕获范式，适用于剩余站点统一侦查分类
- **关联代码**：playwright_scout/*.py
- **关联文档**：docs/superpowers/specs/2026-07-24-adapter-batch-q22-q23-summary.md
- **有效期**：永久

### 2026-07-24 决策 ADAPTER_TYPE_MAP作为适配器唯一真实来源
- **类型**：决策
- **内容**：消除 _ALL_ADAPTER_NAMES/target_names/前端fullName() 三处硬编码，改为从ADAPTER_TYPE_MAP动态派生 + 适配器模块DISPLAY_NAME自描述
- **关联代码**：docker/api/adapter.py, web/.../AdapterStatusQueryCard.vue, 21个适配器模块
- **关联文档**：docs/superpowers/specs/2026-07-24-adapter-batch-q22-q23-summary.md
- **有效期**：永久

### 2026-07-24 放弃 NHC卫健委WAF阻断
- **类型**：放弃
- **内容**：nhc.gov.cn 站点WAF（Cloudflare + 5秒盾 + 验证码）不可绕过，经多轮测试确认放弃
- **关联代码**：playwright_scout/nhc_scout.py（如有）
- **关联文档**：docs/superpowers/specs/2026-07-24-adapter-batch-q22-q23-summary.md
- **有效期**：永久（除非NHC更换WAF策略）

### 2026-07-24 规范 DISPLAY_NAME常量规范
- **类型**：规范
- **内容**：21个适配器模块均定义DISPLAY_NAME常量（≤50字符），API自动暴露display_name字段
- **关联代码**：21个适配器模块, docker/api/adapter.py
- **关联文档**：docs/superpowers/specs/2026-07-24-adapter-batch-q22-q23-summary.md
- **有效期**：永久

### 2026-07-25 决策 三位一体体系加固
- **类型**：决策
- **内容**：引入 Inline 指令分级、.test_pass 自动化（含 commit_hash 锚点）、Knowledge Trigger 结构化知识日志、进度日志半自动化四项机制
- **关联代码**：CLAUDE.md, tests/conftest.py, scripts/gen_daily_log.py, .claude/memory.md
- **关联文档**：docs/superpowers/specs/2026-07-25-sysfix-trinity-hardening-spec-lite.md
- **有效期**：永久

### 2026-07-25 风险 Mypy 预存类型错误待清理
- **类型**：风险
- **内容**：项目中存在 99 个预存 Mypy 类型错误，分布在 13 个未修改文件中，非 SYSFIX-20260725-001 引入，需独立排期清理
- **关联代码**：涉及 13 个文件（详见 mypy 输出）
- **关联文档**：无
- **有效期**：至清理完成时

### 2026-07-25 经验 KeyError导致的skip隐蔽性
- **类型**：经验
- **内容**：当被测模块在导入或setUp阶段因KeyError崩溃时，pytest将用例归类为skip/error而非fail，且不在失败报告中显式列出。修复此类KeyError后pass增量可能大于原fail数量。验收时若skip下降且grep确认无标记改动，应优先判定为依赖链恢复的良性效应
- **关联代码**：CI-FIX-20260725-002（expire→organize 桶重命名导致的连锁KeyError）
- **关联文档**：无
- **有效期**：永久

### 2026-07-25 经验 xfail时效性与僵尸标记
- **类型**：经验
- **内容**：xfail 标记若在批量修复期间作为临时止血措施添加，其失效条件与原始修复强绑定。后续修复覆盖根因后必须同步清理，否则成为"僵尸标记"掩盖已恢复的测试覆盖。任何 xfail 都应附带"解除条件"注释，或在修复指令中列为必查项
- **关联代码**：CI-FIX-20260725-003 修复项3（test_pipeline_router.py xfail 移除）
- **关联文档**：无
- **有效期**：永久

### 2026-07-25 范式 Skip批量消除的分组验证策略
- **类型**：范式
- **内容**：>10 个同类 skip 的批量修复必须按根因分组、逐组修复+逐组验证，避免批量修改后的交叉污染和定位困难。58 个通知测试按 3 种根因分组验证，验证了该策略的有效性
- **关联代码**：CI-FIX-20260725-003 修复项1（test_notification_e2e.py 58 skip→0）
- **关联文档**：无
- **有效期**：永久

### 2026-07-25 规范 CI质量基线门禁
- **类型**：规范
- **内容**：自 2026-07-25 提交 `87e8737e` 起，所有新 PR 必须满足 Failed=0、Skipped≤6（仅限6个已确认外部依赖）、xfail=0、Passed≥2369。任何回退需附书面说明。批量 skip/xfail 复燃时引用 CI-FIX-003 的分组验证策略和 xfail 时效性原则
- **关联代码**：CI-FIX-20260725-001/002/003 全部改动
- **关联文档**：无
- **有效期**：永久（后续提交可上调 Passed 阈值，其余三项不可放宽）
