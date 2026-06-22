# mypy --strict 最终阶段修复设计

日期：2026-06-23

## 目标

将 `mypy pilotstd/ --strict` 错误从 159 降至 0（UI 目录通过 `ignore_errors = true` 压制）。

## 当前状态

- 初始错误数：950 → 当前 159
- 影响 30 个文件（UI 目录已排除）
- 已有配置：`pyproject.toml` 中 `pilotstd.ui.*` 设置 `ignore_errors = true`

## 修复策略（按类型分批，与用户方案 B 一致）

| 优先级 | 错误类型 | 数量 | 修复方式 |
|--------|---------|------|---------|
| 1 | unused-ignore | 38 | 删除无效 `# type: ignore` 注释 |
| 2 | no-untyped-def | 39 | 添加返回类型注解 |
| 3 | type-arg | 12 | 泛型容器添加类型参数 |
| 4 | no-untyped-call | 12 | 为被调用函数添加类型注解 |
| 5 | no-any-return | 36 | 添加 `# type: ignore[no-any-return]` 或修正返回类型 |
| 6 | return-value | 若干 | 修正返回类型与实际返回值一致 |
| 7 | 其他 | 22 | arg-type, union-attr, operator 等逐个处理 |

## 修复原则

1. **最小改动**：只修复类型注解，不改动业务逻辑
2. **不破坏 API**：所有公共函数签名保持向后兼容
3. **优先删除而非压制**：unused-ignore 直接删除注释，不替换为新的 ignore
4. **Any 作为最后手段**：无法推断类型时使用 `Any`，而非错误的类型

## 执行顺序

1. 先删除所有 unused-ignore（38 个，最安全）
2. 补全 type-arg（12 个，可能连锁修复其他错误）
3. 添加 no-untyped-def 返回类型（39 个）
4. 处理 no-untyped-call（12 个，依赖上一步）
5. 处理 no-any-return（36 个）
6. 修正 return-value 和其他零散错误
7. 最终验证

## 验收标准

- `mypy pilotstd/ --strict` 输出 `Success: no issues found`
- Ruff 检查零错误
- 项目正常启动
