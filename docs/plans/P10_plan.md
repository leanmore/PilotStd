# P10 补全闭环计划

### P10 闭环记录（2026-07-17）

**修复项**：
1. 缩进错误：`_query_summary.py` L251 修复（0 → 4 空格），`compileall` 全量验证通过（45/45）
2. 迁移 checksum 不匹配：三级自愈机制落地，G-012 豁免迁移文件

**补充修复（第二轮）**：
- 自愈逻辑条件完善：从"存储值 == 原始值"改为"原始值 != 标准化值"，覆盖旧版本残留值场景
- 验收：容器启动正常，无需手动干预

**公告详情页完善（第三轮）**：
- 来源/附件/正文显示：API 关联查询 announcements 表 + DOMPurify 渲染
- 附件解析按钮状态联动 + 序号两位数格式化
- Source 标识符重构：announcement_gb→annc_gb URL 映射 + 旧链接兼容重定向
- 正文提取 `extract_content()` 三层回退：精确选择器→p标签→关键词启发式
- bcrypt 版本锁定 4.0.1（passlib 兼容性）
- sync_test_schema.py：自动同步 9 个测试文件的 CREATE TABLE 至生产 Schema
- check_schema_consistency.py：EXTRA=0, MISSING=0

**门禁落地**：
- Pre-commit：`py-compile-core` hook 覆盖 `ui/core/`
- CI：`compileall` 合并到 vulture job

**文档更新**：
- `CLAUDE.md`：新增 3.8 证据约束 + 3.9 迁移校验机制 + 3.10 Source 映射规则 + 3.11 交付验证强制标准
- `STATUS.md`：更新最新进展
- `docs/architecture.md`：数据库模块末尾追加迁移校验机制说明
- `docs/plans/P10_plan.md`：本闭环记录
