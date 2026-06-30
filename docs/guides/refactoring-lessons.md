# 大函数拆分经验记录

> 日期：2026-06-28 至 2026-06-30
> 范围：32 个函数拆分 + 11 个文件包化

---

## 一、成功经验

### 1. 分批渐进式治理

**做法**：将 46+ 个大函数分 5 批处理，每批 5-10 个，难度递增。

| 批次 | 难度 | 策略 |
|------|------|------|
| 包化 | 简单 | 只拆文件不拆逻辑，先消除文件违规 |
| 第一批 | 低 | 纯编排函数，提取子函数不改变数据流 |
| 第二批 | 中 | 含嵌套闭包/异步逻辑，需闭包→方法转换 |
| 第三批 | 大 | 含闭包捕获 15+ 变量，需 ctx 字典/参数捆绑 |

**收益**：每批完成后立即测试验证，问题范围可控。

### 2. 先包化后拆分

**做法**：先用 `xxx.py → xxx/__init__.py` 包化消除文件级违规，再逐步拆分内容。

**收益**：
- 拆分时可利用已有的子模块文件
- 相对导入路径自然修正
- 避免一次性大量改动

### 3. 门禁驱动

**做法**：每次修改后立即运行 `ruff check` + `pytest`，不积累问题。

**命令**：
```bash
ruff check <file> && python -m pytest tests/ -k "<related>"
```

### 4. 审查先行

**做法**：编写代码前先写自写审查报告，逐项核对原始逻辑→替换逻辑。

**格式**：
```markdown
- 函数签名：[通过/不通过]（说明）
- 空值守卫：[通过/不通过]（逐行对比）
- ...
- 审查结论：[通过/不通过]
```

**收益**：在动手前发现 90% 的逻辑遗漏和签名不一致问题。

---

## 二、反模式与陷阱

### 1. 信息不足时写代码

**教训**：任务描述中的函数签名、返回值类型常与实际代码不一致。

**案例**：
- `match_result`：描述为 `tuple[str, str]`，实际为 `Tuple[bool, str]`
- `classify`：描述为 `tuple[list, list, list]`，实际返回 `None`（输出参数）
- `_csres_worker`：描述为 `asyncio.create_task`，实际使用 `ThreadPoolExecutor.submit`

**正确做法**：先 `Read` 实际代码，以代码为准，不盲从任务描述。

### 2. 闭包提取需注意

**陷阱**：闭包隐式捕获外层变量，提取为方法/函数时需全部显式化。

**案例**：`_csres_worker` 闭包捕获 4 个外层变量 (`csres_results`, `csres_failures`, `self`, 隐式)，提取为方法后需显式传参。

**检查清单**：
- [ ] 列出闭包中使用的所有外层变量
- [ ] 确认 `nonlocal` 变量处理方式（list 包裹 → 保持引用）
- [ ] 确认 `self` 引用正确处理（闭包 → 方法）
- [ ] 确认调用方式适配（`executor.submit(_closure, ...)` → `executor.submit(self._method, ...)`）

### 3. 返回值结构变更导致测试失败

**教训**：拆分时"优化"返回结构（如统一 key 名称）会破坏调用方。

**案例**：`update_container` 拆分时把 `{"updated": ..., "restarted": ...}` 改为 `{"success": ..., ...}`，导致 5 个测试失败。

**正确做法**：严格保持原始返回值结构，不做"顺便优化"。

### 4. 包化后导入路径需全量检查

**教训**：`xxx.py → xxx/__init__.py` 包化后，文件内 `from .. import` 的相对层级会变化。

**案例**：`engine.py → engine/` 后，`_routing.py` 中 `from ..core.std_utils` 应改为 `from ...core.std_utils`（多一层）。

**检查命令**：
```bash
grep -rn "from \.\.core\|from \.\.scan" pilotstd/query/engine/
```

---

## 三、工具链建议

### 检测大文件

```bash
find pilotstd docker -name '*.py' ! -path '*/tests/*' -exec wc -l {} + | sort -rn | head -20
```

### 检测大函数

```python
import ast, os
for root, _, files in os.walk('pilotstd'):
    for f in files:
        if f.endswith('.py'):
            tree = ast.parse(open(os.path.join(root, f)).read())
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    lines = node.end_lineno - node.lineno + 1
                    if lines > 60:
                        print(f'{lines}行 {root}/{f}:{node.lineno} {node.name}')
```

### 验证导入路径

```bash
# 包化后检查相对导入
grep -rn "from \.\.\." pilotstd/ | grep -v "from \.\.\."
```

### 快速验证

```bash
ruff check pilotstd docker && python -m pytest tests/ -q --tb=no
```

---

## 四、拆分模式参考

### 模式 A：纯编排拆分

适用：函数是线性步骤序列，每步可独立命名。

```python
# 拆前 (100 行)
def process():
    step1...
    step2...
    step3...

# 拆后 (10 行)
def process():
    self._step1()
    self._step2()
    self._step3()
```

### 模式 B：闭包→方法

适用：函数内定义嵌套闭包，捕获外层变量。

```python
# 拆前
def outer():
    shared = {}
    def inner(x):  # 捕获 shared
        shared[x] = ...

# 拆后
def outer():
    shared = {}
    self._inner(x, shared)

def _inner(self, x, shared):
    shared[x] = ...
```

### 模式 C：Mixin 拆分

适用：大文件需拆为多个文件，但类需保持完整。

```python
# 拆前 (500+ 行文件)
class Foo:
    method_a...
    method_b...
    method_c...

# 拆后 (_a.py 100 行 + _b.py 150 行 + _c.py 200 行)
class AMixin:
    def method_a(self): ...

class Foo(AMixin, BMixin, CMixin):
    pass  # 组合三个 mixin
```

### 模式 D：ctx 字典

适用：闭包捕获 10+ 个变量，逐个传参不现实。

```python
ctx = {"results": results, "locks": locks, "callbacks": callbacks, ...}
self._worker(ctx)  # 方法通过 ctx["key"] 访问共享状态
```
