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
