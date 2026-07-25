# SYSFIX-20260725-001 三位一体体系加固 — spec-lite

## 用户指令摘要

对 PilotStd 项目"三位一体 SOP"体系进行全量加固，涉及 7 个模块：
Inlin 指令分级（补丁A）、.test_pass 自动化+commit hash 锚点（补丁B）、
Knowledge Trigger 结构化知识日志（补丁C）、进度日志自动化、G-025 文档联动扩展、
Q22-Q23 总结 spec 补全、adapter-development.md 更新。全部在本次推送前完成。

## 采纳的关键设计决策

1. **spec-lite 作为功能开发的最小文档单元**：≤30 行、4 个必填区块，架构变更仍走完整 spec+plan
2. **pytest session-finish hook 自动管理 .test_pass**：`trylast=True` 确保在所有测试后执行，commit_hash 锚点防篡改
3. **.claude/memory.md 独立于 Auto-Memory 体系**：前者是项目级 CI 可审计的结构化日志，后者是 Claude 会话索引缓存
4. **进度日志半自动化**：gen_daily_log.py 生成 commit 列表草稿，执行者补充关键进展和阻塞项
5. **G-025 触发条件扩展**：adapter 变更强制检查 adapter-development.md 同步 + 新适配器检查 spec-lite 存在

## 识别到的风险点

1. **pytest hook 与现有 fixtures 的兼容性**：conftest.py 已有 shared_db session fixture，hook 的 trylast 确保在所有 fixture teardown 后执行，无冲突
2. **zoneinfo 依赖**：Python 3.9+ 内置，PilotStd 目标环境已确认 ≥3.11
3. **CLAUDE.md 行数增长**：预计新增 60-80 行，当前 116 行，远低于 G-010 500 行阈值

## 验证方式

1. `pytest` 全量通过后检查 `.claude/.test_pass` 自动生成，含 commit_hash 字段
2. `python scripts/gen_daily_log.py` 正常输出当日 commit 列表
3. `scripts/check_all.sh` 零错误通过
4. 手动检查：CLAUDE.md 含 Inline 指令分级 + Knowledge Trigger 规则；.claude/memory.md 含 4 条决策记录
