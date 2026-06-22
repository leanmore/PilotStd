# Contributing to PilotStd

## Development Guidelines

### Code Organization
- **Production code** lives under `pilotstd/`. It must NOT import any module from `tests/` or any file named `*mock*.py`, `*test*.py`, `*fake*.py` within `pilotstd/`.
- **Test code** lives under `tests/`. Test helpers (mocks, fixtures) must be placed in `tests/` and never imported by production code.

### Pre-commit Hooks
We use pre-commit hooks to enforce code quality. Install with:
```bash
pip install pre-commit
pre-commit install
```

The hooks will automatically check for forbidden imports before each commit.

### Pull Request Checklist
- No production code imports from `tests/` or `*mock*.py`.
- All tests pass locally.
- Documentation updated if needed.

---

## 治理规范

本项目采用**能力遗产治理框架**防止非功能性能力（后台线程、观测日志、缓存等）在重构中静默丢失。

- **核心文档**：[docs/governance/capabilities_registry.md](docs/governance/capabilities_registry.md) — 所有非功能性能力的登记簿
- **重构前必读**：[docs/governance/refactoring_checklist.md](docs/governance/refactoring_checklist.md)
- **归档前必读**：[docs/governance/archive_migration_protocol.md](docs/governance/archive_migration_protocol.md)
- **PR 合并前必须运行**：`python tests/test_observability.py --check-all`
- **归档文件前必须运行**：`bash scripts/extract_capabilities.sh <file>`

### 关键规则

| 规则 | 说明 |
|------|------|
| 重构前提取能力清单 | 查阅登记簿 + 运行 `extract_capabilities.sh` |
| 逐项迁移或声明放弃 | commit message 必须包含"已迁移能力"或"已放弃能力"段落 |
| 合并前自检 | `--check-all` 必须零 FAIL |
| 禁止静默归档 | 未生成能力清单 → 禁止 `git mv` |

详细规范请参阅 `docs/governance/` 目录下的完整文档。
