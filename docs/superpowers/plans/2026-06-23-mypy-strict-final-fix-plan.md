# mypy --strict 最终阶段修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `mypy pilotstd/ --strict` 错误从 159 降至 0（UI 目录通过 `ignore_errors = true` 压制）

**Architecture:** 按错误类型分 7 批修复。每批先列出完整清单，再逐个文件修改。修改后即时验证该批错误是否清零。

**Tech Stack:** Python 3.12, mypy 1.x, typing 标准库

**约束：**
- 允许使用 `# type: ignore[<code>]` 但必须附带注释说明原因
- 允许阶段性 `--no-verify` 提交，最终版本必须通过全部检查
- 只修复类型注解，不改动业务逻辑

---

## 错误分布总览

| 批次 | 错误类型 | 数量 | 涉及文件 |
|------|---------|------|---------|
| 1 | unused-ignore | 38 | facade.py(34), parser.py(2), engine.py(1), base.py(1) |
| 2 | no-untyped-def | 39 | commands.py(11), ocr.py(7), notify.py(4), network.py(5), daily_quota.py(2), facade.py(1), monitor.py(2), queue.py(1), search_strategy.py(1), pending_service.py(1), rotator.py(1), service_factory.py(1), announce/base.py(1), njbz365.py(1), \_\_init\_\_.py(1) |
| 3 | type-arg | 12 | ocr.py(7), engine.py(1), organizer_service.py(1), expire_handler.py(1), std_utils.py(1), scan/parser.py(1) |
| 4 | no-untyped-call | 12 | ocr.py(6), daily_quota.py(5), facade.py(1) |
| 5 | no-any-return | 36 | facade.py(26), ocr.py(5), db.py(2), config.py(1), pending_service.py(2), scheduled_service.py(1), organizer_service.py(1), commands.py(1), njbz365.py(1), query/\_\_init\_\_.py(1), parser.py(1), search_strategy.py(0, counted elsewhere) |
| 6 | 其他 | 22 | arg-type(7), assignment(3), union-attr(2), name-defined(2), attr-defined(2), operator(1), list-item(1), valid-type(1), has-type(1), exit-return(1), call-overload(1), str(4), int(3) |
| 7 | 验证 | — | 全量 mypy --strict + ruff + 自检 |

---

### Task 1: 删除所有 unused-ignore 注释

**策略：** 这些 `# type: ignore` 注释已不再需要（mypy 不再报告对应错误），直接删除注释行或删除行尾注释。

**文件清单：**

- [ ] **Step 1: pilotstd/query/adapters/base.py:196** — 删除 `# type: ignore` 注释

- [ ] **Step 2: pilotstd/query/engine.py:414** — 删除 `# type: ignore` 注释

- [ ] **Step 3: pilotstd/announcement/parser.py:367-368** — 删除 2 处 `# type: ignore` 注释

- [ ] **Step 4-20: pilotstd/manager/facade.py** — 删除以下 34 行的 `# type: ignore` 注释（有些行同时有 no-any-return，删除后 no-any-return 仍会报错，留待 Task 5 处理）：
  101, 453, 615, 641, 778, 832, 877, 881, 885, 893, 903, 917, 923, 965, 1001, 1011, 1021, 1054, 1064, 1070, 1082, 1086, 1094, 1098, 1357, 1370, 1423, 1469, 1477, 1494, 1521, 1529, 1534, 1539

- [ ] **Step 21: 验证** — 运行 `python -m mypy pilotstd/ --strict 2>&1 | grep "unused-ignore"` 确认输出为空

- [ ] **Step 22: 提交** — `git commit -m "fix: remove 38 unused type: ignore comments"`

---

### Task 2: 修复 no-untyped-def（添加缺失的返回类型注解）

**策略：**
- 函数体无 return 或 `return None` → 添加 `-> None`
- 函数体有返回值 → 从上下文推断类型并添加
- 无法推断 → 添加 `-> Any`（需要 `from typing import Any`）

**文件清单：**

- [ ] **Step 1: pilotstd/__init__.py:20** — 添加返回类型注解
- [ ] **Step 2: pilotstd/query/rotator.py:35** — 添加 `-> None`
- [ ] **Step 3: pilotstd/announcement/monitor.py:38, 56** — 添加返回类型
- [ ] **Step 4: pilotstd/task/queue.py:107** — 添加 `-> None`
- [ ] **Step 5: pilotstd/query/daily_quota.py:40, 47** — 添加 `-> None`
- [ ] **Step 6: pilotstd/core/notify.py:22, 41, 46, 56** — 添加返回类型
- [ ] **Step 7: pilotstd/query/search_strategy.py:56** — 添加返回类型
- [ ] **Step 8: pilotstd/manager/pending_service.py:88** — 添加参数类型注解
- [ ] **Step 9: pilotstd/query/network.py:72, 123, 134, 145, 153** — 添加参数/返回类型
- [ ] **Step 10: pilotstd/query/adapters/njbz365.py:134** — 添加参数类型
- [ ] **Step 11: pilotstd/announcement/ocr.py:193, 393, 408, 431, 439, 507** — 添加返回类型（部分 `-> None`，部分需推断）
- [ ] **Step 12: pilotstd/announcement/base.py:179** — 添加参数类型
- [ ] **Step 13: pilotstd/manager/service_factory.py:16** — 添加返回类型（`create_services`）
- [ ] **Step 14: pilotstd/manager/facade.py:953** — 添加参数类型
- [ ] **Step 15: pilotstd/cli/commands.py:40, 85, 171, 220, 240, 257, 296, 326, 366, 394, 418** — 添加参数类型（11 个 CLI 命令函数）

- [ ] **Step 16: 验证** — `python -m mypy pilotstd/ --strict 2>&1 | grep "no-untyped-def"` 确认输出为空

- [ ] **Step 17: 提交** — `git commit -m "fix: add missing type annotations for 39 untyped definitions"`

---

### Task 3: 修复 type-arg（泛型容器缺少类型参数）

**策略：**
- `dict` → `dict[str, Any]`
- `list` → `list[Any]`
- `tuple` → `tuple[Any, ...]`
- `set` → `set[str]`（按上下文）
- `Pattern` → `Pattern[str]`

**文件清单：**

- [ ] **Step 1: pilotstd/scan/parser.py:156** — `Pattern` → `Pattern[str]`
- [ ] **Step 2: pilotstd/core/std_utils.py:66** — `dict` → `dict[str, Any]`
- [ ] **Step 3: pilotstd/organizer/expire_handler.py:20** — `dict` → `dict[str, Any]`
- [ ] **Step 4: pilotstd/manager/organizer_service.py:64** — `set` → `set[str]`
- [ ] **Step 5: pilotstd/query/engine.py:446** — `tuple` → `tuple[Any, ...]`
- [ ] **Step 6-12: pilotstd/announcement/ocr.py:160, 286, 382, 719, 770, 779, 788** — 7 处 `dict` → `dict[str, Any]`

- [ ] **Step 13: 验证** — `python -m mypy pilotstd/ --strict 2>&1 | grep "type-arg"` 确认输出为空

- [ ] **Step 14: 提交** — `git commit -m "fix: add type arguments to generic containers (12 occurrences)"`

---

### Task 4: 修复 no-untyped-call（调用无类型函数）

**策略：** 找到被调用的函数，为其添加参数和返回类型注解。

**文件清单：**

- [ ] **Step 1: pilotstd/query/daily_quota.py** — `_ensure_today_rows` 和 `_ensure_date` 添加类型注解（5 处调用报错）
- [ ] **Step 2: pilotstd/announcement/ocr.py** — `_sign`（3 处）、`_save`（1 处）、`_set_thread_priority_idle`（1 处）、`ProviderCooling`（1 处）添加类型注解
- [ ] **Step 3: pilotstd/manager/facade.py:138** — `create_services` 在 service_factory.py 中添加返回类型（已在 Task 2 Step 13 处理）

- [ ] **Step 4: 验证** — `python -m mypy pilotstd/ --strict 2>&1 | grep "no-untyped-call"` 确认输出为空

- [ ] **Step 5: 提交** — `git commit -m "fix: add type annotations for untyped callables (12 occurrences)"`

---

### Task 5: 修复 no-any-return（返回 Any 类型）

**策略：**
- 优先方案：在函数末尾 return 语句处添加显式类型转换（如 `return int(result)`）
- 备选方案：添加 `# type: ignore[no-any-return]  # 数据库返回值无精确类型`
- facade.py 中大量数据库操作方法返回 Any，统一用 ignore 注释处理

**文件清单（按文件分组）：**

- [ ] **Step 1: pilotstd/core/db.py:121, 279** — db 操作方法，添加类型转换或 ignore
- [ ] **Step 2: pilotstd/core/config.py:82** — 配置读取，添加类型转换
- [ ] **Step 3: pilotstd/manager/pending_service.py:82, 115** — 添加 ignore 或类型转换
- [ ] **Step 4: pilotstd/manager/scheduled_service.py:206** — 添加 ignore
- [ ] **Step 5: pilotstd/manager/organizer_service.py:527** — 添加 ignore
- [ ] **Step 6: pilotstd/query/adapters/njbz365.py:300** — 添加 ignore
- [ ] **Step 7: pilotstd/query/__init__.py:57** — 添加 ignore
- [ ] **Step 8: pilotstd/announcement/parser.py:340** — 添加 ignore
- [ ] **Step 9: pilotstd/announcement/ocr.py:391, 402, 406, 415, 420** — 添加 ignore 或类型转换
- [ ] **Step 10: pilotstd/cli/commands.py:522** — 添加 ignore
- [ ] **Step 11-36: pilotstd/manager/facade.py** — 以下 26 行的 no-any-return（部分已在 Task 1 中删除了错误的 ignore 注释，现需添加正确的）：
  641, 776, 877, 881, 885, 893, 903, 917, 923, 961, 1011, 1054, 1064, 1070, 1082, 1086, 1092, 1098, 1357, 1370
  （精确行号以实际 mypy 报告为准）

- [ ] **Step 37: 验证** — `python -m mypy pilotstd/ --strict 2>&1 | grep "no-any-return"` 确认输出为空

- [ ] **Step 38: 提交** — `git commit -m "fix: resolve 36 no-any-return errors with type: ignore annotations"`

---

### Task 6: 修复其他零散错误（22 个）

按子类型分组处理：

**6a: arg-type (7 个)**

- [ ] **Step 1: pilotstd/scan/watcher.py:68, 71, 74, 83, 87** — 参数类型 `bytes | str` vs `str`，在函数签名中扩展类型为 `str | bytes` 或添加类型转换
- [ ] **Step 2: pilotstd/query/engine.py:280, 291** — 参数类型不兼容，修正类型注解

**6b: name-defined (2 个)**

- [ ] **Step 3: pilotstd/core/std_utils.py:6** — 添加 `from typing import Any`
- [ ] **Step 4: pilotstd/query/adapters/hbba.py:87** — 添加 `from typing import Optional`

**6c: assignment (3 个)**

- [ ] **Step 5: pilotstd/core/config.py:379** — 修正赋值类型不兼容
- [ ] **Step 6: pilotstd/query/engine.py:1007** — float vs int 赋值不兼容
- [ ] **Step 7: pilotstd/manager/announce_service.py:44** — 修正赋值类型

**6d: union-attr + operator (3 个，同一位置)**

- [ ] **Step 8: pilotstd/query/adapters/csres.py:183-184** — 添加类型守卫处理 `AttributeValueList | None`

**6e: valid-type + attr-defined (3 个)**

- [ ] **Step 9: pilotstd/scan/watcher.py:98, 131, 132** — `watchdog.observers.Observer` 类型注解修正

**6f: 其他 (4 个)**

- [ ] **Step 10: pilotstd/core/db.py:52** — `__exit__` 返回类型 `bool` → `Literal[False]`
- [ ] **Step 11: pilotstd/task/queue.py:111** — `list.__setitem__` 类型不匹配修正
- [ ] **Step 12: pilotstd/query/engine.py:284** — list-item 类型不兼容
- [ ] **Step 13: pilotstd/core/config.py:446** — `_fernet` 类型无法确定

- [ ] **Step 14: 验证** — `python -m mypy pilotstd/ --strict 2>&1 | grep "error:"` 确认输出为空

- [ ] **Step 15: 提交** — `git commit -m "fix: resolve 22 miscellaneous mypy errors"`

---

### Task 7: 最终验证与清理

- [ ] **Step 1: 全量 mypy 验证**

```bash
python -m mypy pilotstd/ --strict
```
预期输出：`Success: no issues found in source files`

- [ ] **Step 2: Ruff 检查**

```bash
ruff check pilotstd/ docker/ --fix
ruff format pilotstd/ docker/
```
预期：零错误

- [ ] **Step 3: 运行测试**

```bash
python -m pytest tests/ -x --timeout=60 2>&1 | tail -20
```
预期：全部通过（或与修复前一致）

- [ ] **Step 4: 更新 STATUS.md** — 记录 mypy --strict 最终修复状态

- [ ] **Step 5: 最终提交**

```bash
git add -A
git commit -m "fix: complete mypy --strict cleanup (159→0 errors)"
```

- [ ] **Step 6: 推送**

```bash
git push origin main
```
