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
