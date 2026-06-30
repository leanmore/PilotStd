# 文档同步策略

> 创建日期：2026-06-30
> 最后更新：2026-06-30

## 一、触发规则

以下任一情况发生时，必须联动更新相关文档：

| 触发条件 | 需更新的文档 | 操作 |
|---------|-------------|------|
| 新增/删除 Python 模块 | `specs/模块与功能清单.md` | 更新对应层级表格 |
| 文件/函数行数变化（跨 500/80 红线） | `architecture/governance-summary.md`、`STATUS.md` | 更新统计数字 |
| 新增 API 端点 | `STATUS.md`、`CHANGELOG.md` | 记录变更 |
| 测试通过率变化 | `STATUS.md` | 更新测试数据 |
| 安全相关变更 | `architecture/technical-debt-registry.md` | 登记新条目 |
| 接受技术债/设计决策 | `architecture/technical-debt-registry.md` | 登记决策 |
| 重构大文件/大函数 | `architecture/governance-summary.md`、`STATUS.md` | 更新治理数据 |
| CI/CD 配置变更 | `STATUS.md` | 更新工作流说明 |
| 归档过时文档 | `archive/YYYY-MM-DD/README.md` | 记录归档清单 |

## 二、PR 门禁

每个 Pull Request 合并前必须检查：

- [ ] 是否修改了 `pilotstd/` 或 `docker/` 下的任意 `.py` 文件 → 检查 docs/ 是否有对应文档需要更新
- [ ] 是否新增/删除了文件 → 检查 `specs/模块与功能清单.md` 是否需要更新
- [ ] 是否改变了函数签名 → 检查文档中的 API 示例代码是否仍然正确
- [ ] 测试通过率是否变化 → 更新 `STATUS.md`

**例外**：纯格式化（ruff format）、类型注解修正（仅 mypy）、死代码删除可以跳过文档更新。

## 三、同版本原则

文档和代码必须在同一版本中保持一致：

- 代码提交和文档更新应在**同一个 PR** 中完成
- 不允许"代码先合，文档后补"的延迟更新
- 归档文档时使用 `git mv` 保留历史

## 四、定期审计

每季度进行一次文档健康度审计：

1. 扫描所有文档，检查是否有引用已移动/已删除文件
2. 检查统计数字（测试数、行数、文件数）是否与当前代码一致
3. 过时文档移至 `archive/YYYY-MM-DD/` 并记录归档原因
4. 更新 `architecture/governance-summary.md` 中的文档健康度章节

审计命令：
```bash
# 检查引用旧文件路径
grep -rn "\.py'\|\.md'" docs/ | grep -v archive/

# 检查测试数字一致性
grep -rn "PASS\|FAIL\|SKIP" docs/ | grep -v archive/ | grep -v superpowers/
```

## 五、归档协议

1. 确认文档内容已过时（引用不再存在，或数据不准确）
2. 创建 `docs/archive/YYYY-MM-DD/` 目录（如果不存在）
3. 使用 `git mv` 移动文件（保留历史）
4. 在归档目录的 `README.md` 中记录归档原因
5. 创建/更新替代文档
6. 在 PR 描述中注明归档操作

## 六、相关文档

- [技术债登记簿](../architecture/technical-debt-registry.md)
- [治理汇总](../architecture/governance-summary.md)
- [重构经验](../guides/refactoring-lessons.md)

---

## 七、月度审计

**执行人**：项目负责人（或指定成员）

**审计日期**：每月最后一周的周五

**输出物**：审计结果记录在 `docs/architecture/governance-summary.md` 的"文档健康度"章节

### 触发规则执行路径表

| 触发规则 | 对应文档 | 检查人 | 检查时机 |
|---------|---------|--------|----------|
| 新增/修改 API 端点 | `STATUS.md` + `CHANGELOG.md` | PR提交者 | 代码提交前 |
| 修改核心模块路径 | `docs/architecture/governance-summary.md` | PR提交者 | 代码提交时 |
| 新增/修改环境变量 | `.env.example` + 相关部署文档 | PR提交者 | 代码提交时 |
| 修改门禁规则 | `docs/development/gate-15-enforcement.md` | PR提交者 | 修改门禁时 |
| 修改数据库 Schema | 迁移脚本注释 + `STATUS.md` | PR提交者 | 迁移文件提交时 |
| 新增/修改测试策略 | `docs/development.md` | PR提交者 | 测试代码提交时 |
| 完成/移除技术债务 | `docs/architecture/technical-debt-registry.md` | PR提交者 | 债务消除时 |
| 文件/函数拆分完成 | `docs/architecture/refactoring-analysis.md` | PR提交者 | 拆分任务完成时 |
