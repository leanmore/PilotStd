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
- 运行 `python scripts/fix_relative_imports.py` 验证相对导入有效性。
- [ ] 修改 `path_guard.py` 时，确认 `/inbox` 和 `/standards` 在白名单中（G-019 检查）
- [ ] 修改 `logger.py` 的 `_TAG_MAP` 时，确认 `[PROGRESS]` 等标签不受影响（G-005 检查）
- [ ] 新增 OCR 敏感字段时，同步添加到 `settings.py` 掩码列表（G-018 检查）
- [ ] 修改 `_ALL_ADAPTER_NAMES` 时，同步更新 `capabilities_registry.md`（G-025 检查）
- [ ] 修改 `docker-compose.yml` 时，已确认未挂载 `/app` 目录（G-026 检查）
- [ ] 新增挂载点时，已确认不覆盖容器内代码或配置目录
- [ ] 修改 `SENSITIVE_FIELDS` 时，已确认所有 OCR 敏感字段均已掩码（LOG-02）
- [ ] 修改日志协议标识（如 `PROGRESS_TAG`）时，已同步更新所有跨进程引用（LOG-03）
- [ ] 修改日志格式时，已确认三端使用同一 `_TagFormatter`（LOG-04）
- [ ] 修改 WinUI 进度条时，已确认 `_on_auto_stage_changed` 阶段切换时归零（UI-01）

### 自动门禁脚本
```bash
python scripts/check_relative_imports.py             # 相对导入有效性检查
python scripts/check_ui_sensitive_fields.py      # G-018 敏感字段掩码（前后端统一）
python scripts/check_g_025_adapters.py            # G-025 适配器一致性
python scripts/check_g_026_docker_mounts.py       # G-026 Docker 挂载黑名单
python scripts/check_g_027_define_options.py      # G-027 Vue 组件 defineOptions
python scripts/check_g_028_no_hardcoded_admin.py  # G-028 禁止硬编码 admin
```

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
