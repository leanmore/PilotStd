# 开发指南（已迁移）

本文件内容已并入：
- 开发流程：docs/onboarding/07-dev-workflow.md
- 测试基线：docs/testing/testing-baseline.md
- CI 经验：docs/ci-lessons.md

（保留文件名以维持现有引用；2026-11-08 由 PilotDoc Closeout 迁移）

## CI 工作流变更记录

- **2026-11-08**：security-scan job 的 bandit 改为 `--severity-level high` 阻断；新增 pip-audit `--strict --desc on` 真拦截；Pillow 升至 13.0.0、urllib3 升至 2.8.0；pip-audit 对 ecdsa/python-jose 加带理由的 ignore。详见 `.github/workflows/ci.yml` 的 security-scan 段。
