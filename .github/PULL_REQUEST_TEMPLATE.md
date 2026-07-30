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
