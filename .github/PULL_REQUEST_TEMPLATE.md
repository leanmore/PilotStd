## Description
<!-- Please include a summary of the change -->

## Capability Migration Status (Governance Required)

> If this PR does NOT involve refactoring or migration, check "Not applicable" and skip the table.

- [ ] Not applicable (new feature or bug fix, no refactoring)
- [ ] Involves refactoring (fill table below)

| Capability Name | Source Location | Target Location | Status |
|----------|----------|----------|----------|
|          |          |          | migrated / abandoned / new |
|          |          |          | migrated / abandoned / new |

**Verification**:
- [ ] Ran `python tests/test_observability.py --check-all`, result: ___ (PASS / FAIL)
- [ ] Updated `docs/governance/capabilities_registry.md` if capabilities changed

---

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Refactoring
- [ ] Documentation

## Checklist
- [ ] My code follows the project's style guidelines.
- [ ] I have performed a self-review of my code.
- [ ] I have commented my code, particularly in hard-to-understand areas.
- [ ] I have made corresponding changes to the documentation.
- [ ] My changes generate no new warnings.
- [ ] I have ensured that no production code imports from `tests/` or any `*mock*.py` file.
- [ ] I have added tests that prove my fix is effective or my feature works.
- [ ] New and existing unit tests pass locally with my changes.
- [ ] **【Mixin 检查】**：是否新增或修改了 Mixin？
  - 若新增 → 请在 PR 描述中说明为何不能使用组合模式
  - 若修改 → 请说明是否同时重构了涉及该 Mixin 的 UI 类
- [ ] 本地运行 `mypy pilotstd/ --strict` 通过
- [ ] 本地运行 `ruff check .` 通过

## 文档同步检查
- [ ] 代码变更对应的文档已同步更新（参考 [文档同步策略](docs/development/documentation-policy.md)）
- [ ] 如有新增 API，已在接口文档中记录
- [ ] 如有路径变更（文件移动/重命名），已在目录结构中更新
- [ ] 如有技术债务消除，已在 [technical-debt-registry.md](docs/architecture/technical-debt-registry.md) 中标记
- [ ] 如有新配置项或环境变量，已补充到环境配置文档
