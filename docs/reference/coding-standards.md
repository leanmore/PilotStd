# 编码规范详细版

## Python 规范

### 异常处理

| ✅ 正确 | ❌ 错误 |
|---------|---------|
| `except (ValueError, TypeError) as e:` | `except:` |
| `except Exception as e: logger.error(...)` | `except Exception: pass` |
| 捕获具体异常类型 | 裸 except 吞掉所有异常 |

### 日志

| ✅ 正确 | ❌ 错误 |
|---------|---------|
| `LoggerManager().info(...)` | `print(...)` |
| `LoggerManager().error("msg", exc_info=True)` | `_log("msg")` |
| 使用 `exc_info=True` 记录堆栈 | 手动拼接 traceback |

### 数据库

| ✅ 正确 | ❌ 错误 |
|---------|---------|
| 查询字段加索引 | 全表扫描 |
| 使用参数化查询 | 字符串拼接 SQL |
| 迁移脚本管理 Schema 变更 | 手动 ALTER TABLE |

## TypeScript / Vue 规范

### 类型安全

| ✅ 正确 | ❌ 错误 |
|---------|---------|
| `const status: ParseStatus = res.status` | `const status = res.status as any` |
| 接口返回类型明确定义 | 使用 `any` 接收 API 响应 |
| `v-if` 控制渲染 | `v-show` 隐藏含敏感数据的元素 |

### 组件

| ✅ 正确 | ❌ 错误 |
|---------|---------|
| Composition API + `<script setup>` | Options API |
| Props 定义类型 | Props 无类型约束 |
| 响应式数据用 `ref` / `reactive` | 直接修改 props |

## 通用规则

- 单文件不超过 400 行（G-010）
- 新增函数必须有单元测试（G-034）
- 提交前 Ruff / Mypy 零错误（G-031）
- 禁止引入未使用的 import（G-020）
