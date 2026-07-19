# 提交前自检清单

本文档中的每一项都是提交前的强制检查。不存在"按需"或"可选"。

## 自动检查（由 check_all.sh 执行）

提交前必须运行：

```bash
scripts/check_all.sh
```

包含：Ruff（G-031）、Mypy（G-031）、G-010 行数检查、Vulture 死代码（G-020）、Schema 一致性检查。
任何一项失败，禁止继续提交流程。

## 测试检查

```bash
# 后端全量测试
pytest

# 前端测试（涉及前端变更时必须执行）
npm run test
```

测试未全部通过，禁止生成交付报告。

## 死代码检查

```bash
# Python 死代码（check_all.sh 已包含，此处为补充确认）
vulture pilotstd/ --min-confidence 80

# 前端死代码（涉及前端变更时必须执行）
npx ts-prune
```

发现死代码必须清理。禁止以"后续处理"为由跳过。

## 安全检查

```bash
grep -rn "password\|secret\|token\|api_key" pilotstd/ --include="*.py" | grep -v "test_\|_test\.\|conftest"
```

输出不为空时，必须逐条确认是否为误报。确认为真实密钥的，必须移除后才能提交。

## 通过标准

| 检查项 | 通过标准 |
|--------|---------|
| check_all.sh | 全部通过，零错误零警告 |
| pytest | 全量通过 |
| 前端测试 | 全量通过（涉及前端变更时） |
| 死代码 | 无新增 |
| 密钥扫描 | 无硬编码敏感信息 |

所有检查项通过后，方可生成交付报告。
