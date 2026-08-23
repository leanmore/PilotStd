# G-010 代码规模控制规则

> 版本：v1.0
> 生效日期：2026-06-24 (非阻断模式) → 2026-06-30 (阻断模式)
> **当前状态：✅ 已达标 (0 文件 >500行, 0 函数 >80行)**
> 治理详情：[治理汇总](../architecture/governance-summary.md) | [包化分析](../architecture/refactoring-analysis.md)

---

## 一、规则定义

| 规则编号 | 规则 | 红线 | 测量方式 |
|---------|------|------|---------|
| G-010a | 文件有效代码行数 | ≤ 500 行（>400 警告，>500 阻断） | 有效代码行（剔除空行与注释行） |
| G-010b | 函数行数 | ≤ 80 行 | AST 解析 `FunctionDef.end_lineno - lineno` |

**例外**：
- 测试文件 (`tests/`) 不受限制（门禁扫描排除 `tests/` 目录）
- 虚拟环境 (`.venv/`) 不受限制
- 前端代码 (`web/`) 受门禁约束（.vue/.ts 文件纳入检查）
- 数据文件 (JSON/CSV/配置) 不受限制

---

## 二、执行模式演进

| 阶段 | 模式 | 日期 | 说明 |
|------|------|------|------|
| 0 | 无规则 | 6月24日前 | 13+ 文件 >500 行，46+ 函数 >80 行 |
| 1 | 非阻断 CI | 6月24日 | pre-commit 手动执行，CI 报告但不阻断 |
| 2 | 渐进式治理 | 6月28-30日 | 分三批拆分 32 个大函数 + 11 个文件包化 |
| 3 | 阻断模式 | 2026-07-01 | 全部违规清零，CI `continue-on-error: false`，pre-commit 新增 hook |

### 阻断配置

- **CI** (`.github/workflows/ci.yml`): `continue-on-error` 已移除，违规导致 CI 失败
- **Pre-commit** (`.pre-commit-config.yaml`): 新增 `gate-15` hook，提交时自动检查

---

## 三、违规处理流程

```
新代码提交
  → pre-commit hook: 检查文件行数 + 函数行数
    ├── 通过 → 继续提交
    └── 违规 → 拒绝提交
          ├── 文件 >500 行 → 拆分为目录 (__init__.py + 子模块)
          ├── 函数 >80 行 → 拆分为若干子函数 (_ 前缀)
          └── 无法拆分 (如数据表定义) → 申请例外 (需审查批准)
```

---

## 四、检查命令

**有效代码行数**（与门禁脚本口径一致）：
```bash
python scripts/check_g_010_code_size.py
```

**函数行数**：
```bash
# 使用 AST 检查
python -c "
import ast, os
for root, dirs, files in os.walk('pilotstd'):
    for f in files:
        if f.endswith('.py'):
            with open(os.path.join(root, f)) as fp:
                tree = ast.parse(fp.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    lines = node.end_lineno - node.lineno + 1
                    if lines > 80:
                        print(f'{lines}行 {root}/{f}:{node.lineno} {node.name}')
"
```

**CI 集成** (`pre-commit` config):
```yaml
- repo: local
  hooks:
    - id: gate-10
      name: G-010 code size check
      entry: python scripts/check_g_010_code_size.py
      language: python
      files: \.py$
      exclude: ^tests/|^pilotstd_env/
```

---

## 五、治理成果

| 维度 | 治理前 (6月24日) | 治理后 (6月30日) | 变化 |
|------|-----------------|-----------------|------|
| 文件 >500 行 | 13+ | 0 | -100% |
| 函数 >80 行 | 46+ | 0 | -100% |
| 包化目录 | 0 | 11 | — |
| 拆分函数 | 0 | 32 | — |
| 新增 mixin 文件 | 0 | 6 | — |

---

## 六、维护规则

1. **新增文件**：创建时即应 ≤500 行。若接近 400 行，提前规划拆分。
2. **新增函数**：保持 ≤60 行（留 20 行余量）。超过 60 行立即评估拆分。
3. **修改现有**：修改导致文件/函数超标的，必须同时拆分。
4. **审查**：每个 PR 必须通过 G-010 检查。
5. **例外审批**：确实无法拆分的特殊情况（如 AST 生成的代码），需在 PR 描述中说明理由并获得批准。
