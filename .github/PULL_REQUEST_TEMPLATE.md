## 变更说明

<!-- 请简要描述本次变更的内容 -->

## 三位一体治理体系执行确认

### 文档支柱

- [ ] **已阅读相关文档**：请列出本次任务阅读的文档名称
- [ ] **已同步更新文档**：请贴出更新的文档及变更行，或填写 `N/A`

### 测试支柱

- [ ] **测试已通过**
- [ ] **新增/修改代码已有对应测试**

### 门禁支柱

- [ ] **本地检查已通过**（`scripts/check_all.sh` 零警告）
- [ ] **文档与代码已在同一个 commit 中提交**
- [ ] **已确认新增/修改的 i18n key 在所有 locale 文件中存在**（`web/src/locales/*.json` 键名对齐，无遗漏）→ 排查指南见 [i18n-troubleshooting-sop.md](docs/reference/i18n-troubleshooting-sop.md)

## 🛡️ 质量门禁自查（i18n / 安全 / 状态恢复）

- [ ] **i18n 安全**：所有 `*Key` 字段均已通过 `t()` / `$t()` 包装，ESLint `no-raw-i18n-key` 无告警
- [ ] **状态恢复安全**：Store 中 `role` / `permission` / `token` 等敏感字段未出现在 Pinia 持久化 `paths` 白名单中
- [ ] **登出原子性**：若涉及登出逻辑修改，已同步更新 `clearUser()` + `_initialized` 标记 + 后端注销 API
- [ ] **Fallback 一致性**：若修改了 i18n 文件或 Fallback 数组，两者值已保持同步
- [ ] **E2E 覆盖**：若本次修复涉及权限/i18n/状态恢复，已补充或更新对应 Playwright 用例

## 🔍 P3 人工审查前置自查（Claude Code 必填）

> ⚠️ 以下勾选框由 Claude Code 在提交前逐项验证。未勾选或 **"说明"字段留空** 将导致人工审查直接退回。

### G-035 测试联动
- [ ] 生产代码变更已同步更新 `tests/` 中相关测试文件的硬编码值（含常量、枚举值、测试数据中的固定字符串/数字）、断言及预期结果
- [ ] 或：本次变更不涉及测试文件中的硬编码依赖
  **说明：** ___

### G-036 文档联动（10 条触发规则）
- [ ] 已逐条检查以下触发规则，对应文档已更新或标注合法 N/A：
  - [ ] API 行为变更 → `docs/architecture.md`
  - [ ] DB/查询逻辑变更 → `docs/architecture.md`
  - [ ] 工具链配置变更 → `docs/development.md` 或 `docs/ci-lessons.md`
  - [ ] E2E 测试变更 → `docs/testing/e2e-test-manifest.md`
  - [ ] Handler/Engine 范式变更 → `docs/guides/*.md`
  - [ ] 架构决策新增/修改 → `docs/adr/*.md`
  - [ ] 门禁规则变更 → `docs/governance/gates.md`
  - [ ] 代码规范/适配器开发变更 → `docs/reference/*.md`
  - [ ] 配置项变更 → `docs/configuration/*.md`
  - [ ] Spec/Plan 变更 → `docs/superpowers/specs/*.md`
- [ ] 或：本次变更未触发任何文档联动规则
  **说明：** ___

### G-037 触发条件对齐
- [ ] `CLAUDE.md` 与 `docs/index.md` 的文档索引已双向比对一致
- [ ] 或：本次变更不涉及文档索引或触发条件调整
  **说明：** ___

### G-038 历史遗留错误清零
- [ ] `ruff check . && mypy .` 全量通过，无任何 lint/类型错误
- [ ] 未使用 `# noqa` 或 `# type: ignore` 静默告警
- [ ] 或：仅修改已有 noqa/type-ignore 注释且附带清理计划
  **说明：** ___
