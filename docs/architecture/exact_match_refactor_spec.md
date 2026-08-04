# ExactMatchMixin 重构立项方案

> 状态：草稿 | 日期：2026-08-04 | 作者：AI 辅助分析

## 1. 历史动机探究

### 1.1 Git 历史

```
42300558 fix(Q4+Q5+Q25): Web归档三缺陷修复
e30dd62d docs: G-012注释密度清零
89e82a0d docs: G-012注释密度清零
67c3d518 feat: P5.2文档同步门禁+P5.3覆盖率报告
```

近 4 次提交均为 bug 修复和合规性文档补充，说明此模块功能已稳定。

### 1.2 设计动机推测

`staticmethod` + MRO 注入的设计初衷推测为**多重继承的性能优化**：

```python
# StandardParser 类体（__init__.py:52-61）
_clean = staticmethod(TextCleaner.clean)
_detect_language = staticmethod(LanguageDetector.detect)
_normalize_year = staticmethod(NumberExtractor.normalize_year)
_extract_number = staticmethod(NumberExtractor.extract_number)
# ...共 8 个 staticmethod 覆盖
```

**为什么用 staticmethod？**
- 这些辅助方法本质是无状态的纯函数（不访问 `self`）
- `staticmethod` 避免了每次调用时传递 `self` 的开销
- 如果定义为普通实例方法，Python 会通过 descriptor 协议创建 bound method，有微小性能成本

**为什么通过 MRO 注入？**
- `ExactMatchMixin._exact_match()` 内部调用 `self._normalize_year()`，Python 通过 MRO 查找
- `StandardParser` 用 `staticmethod` 覆盖了 Mixin 中的 `raise NotImplementedError` 声明
- 这样做的好处：Mixin 定义了解析通道的"接口契约"，StandardParser 通过类体赋值提供具体实现
- 这是 Python 中一种轻量级的"依赖注入"——不需要构造函数传参，不需要抽象基类

**是否是历史遗留？**
- 不是。此模式在项目中是**特例**——其他 Mixin 都没有使用 `staticmethod` 覆盖。
- 注释 "子类用 staticmethod 覆盖时 mypy 报签名不匹配，但运行时正确" 表明这是刻意选择，且已知与类型检查器存在不兼容。

## 2. 现状分析

### 2.1 文件结构

```
pilotstd/scan/parser/
├── __init__.py          # StandardParser 类体（含 staticmethod 绑定）
├── _exact.py            # ExactMatchMixin（271 行，15 方法）
├── _core.py             # ParserCore（或内嵌在 __init__.py）
├── _foreign.py          # ForeignHandlerMixin（已重构）
├── _number_extractor.py # NumberExtractor
├── _result_builder.py   # ResultBuilder
└── _constants.py        # 常量
```

### 2.2 MRO 注入链

```
StandardParser(ExactMatchMixin)
  ├── 继承 ExactMatchMixin 的 15 个方法（7 具体 + 8 声明）
  ├── 覆盖 8 个 raise NotImplementedError 声明：
  │   _normalize_year  → NumberExtractor.normalize_year   [staticmethod]
  │   _extract_number   → NumberExtractor.extract_number    [staticmethod]
  │   _extract_num_prefix → NumberExtractor.extract_num_prefix [staticmethod]
  │   _extract_part     → NumberExtractor.extract_part      [staticmethod]
  │   _clean_std_name   → ResultBuilder.clean_std_name      [staticmethod]
  │   _validate_result  → ResultBuilder.validate_result     [staticmethod]
  │   _trim_prefix      → StandardParser._trim_prefix       [实例方法]
  │   _build_result     → StandardParser._build_result      [实例方法]
  └── 注入属性：
      regex, regex_no_year, regex_typed, regex_typed_v2, regex_db [__init__ 初始化的正则]
      code_mapping                                                  [__init__ 初始化的映射表]
```

### 2.3 exact.py 中的 self 访问分类

| self 访问 | 次数 | 当前来源 | 重构后来源 |
|-----------|------|---------|-----------|
| `self.regex/regex_db/regex_no_year/regex_typed/regex_typed_v2` | 5 | StandardParser.__init__ | ExactMatcher.__init__ 注入 |
| `self.code_mapping` | 6 | StandardParser.__init__ | ExactMatcher.__init__ 注入 |
| `self._normalize_year(...)` | 5 | MRO → NumberExtractor | `self._parser._normalize_year(...)` |
| `self._clean_std_name(...)` | 3 | MRO → ResultBuilder | `self._parser._clean_std_name(...)` |
| `self._build_result(...)` | 3 | MRO → StandardParser | `self._parser._build_result(...)` |
| `self._validate_result(...)` | 4 | MRO → ResultBuilder | `self._parser._validate_result(...)` |
| `self._extract_number(...)` | 3 | MRO → NumberExtractor | `self._parser._extract_number(...)` |
| `self._extract_num_prefix(...)` | 3 | MRO → NumberExtractor | `self._parser._extract_num_prefix(...)` |
| `self._extract_part(...)` | 3 | MRO → NumberExtractor | `self._parser._extract_part(...)` |
| `self._trim_prefix(...)` | 3 | MRO → StandardParser | `self._parser._trim_prefix(...)` |
| `self._current_file_kind` | 1 | StandardParser 实例变量 | 通过 parser 引用访问 |

### 2.4 调用方清单

| 调用方 | 方式 | 影响 |
|--------|------|------|
| `StandardParser.parse()` | MRO → `_exact_match()` 等 | 需改为 `self._matcher._exact_match(text)` |
| `StandardParser._post_process()` | 间接（不调用 Mixin 方法） | 无影响 |
| 外部代码 | 通过 `StandardParser.parse()` | 无直接影响 |
| `tests/test_parser.py` | 直接测试 StandardParser | 需更新 fixture |

## 3. 重构目标

### 3.1 目标架构

```
ExactMatcher (独立类)
  ├── __init__(self, parser)
  │     self._parser = parser       # 持有 StandardParser 引用
  │     self.regex = parser.regex    # 直接复制引用（共享对象）
  │     self.code_mapping = parser.code_mapping
  │
  ├── 7 个匹配通道方法（原 ExactMatchMixin 的具体实现）
  │     self.regex → self.regex（本地引用）
  │     self._normalize_year(...) → self._parser._normalize_year(...)
  │     self.code_mapping → self.code_mapping（本地引用）
  │
  └── 不再需要 8 个 raise NotImplementedError 声明

StandardParser
  ├── 不再继承 ExactMatchMixin
  ├── __init__ 中创建 self._matcher = ExactMatcher(self)
  ├── parse() 中调用 self._matcher._exact_match(text) 等
  └── 8 个 staticmethod 绑定保留（仍需被 matcher 通过 self._parser 访问）
```

### 3.2 匹配通道方法清单（7 个，从 ExactMatchMixin 迁出）

1. `_exact_match_db(text)` — 地方标准 DB 匹配
2. `_exact_match_bpvc(text)` — ASME BPVC 罗马数字匹配
3. `_exact_match_itu(text)` — ITU 推荐号匹配
4. `_exact_match(text)` — 通用精确匹配
5. `_exact_match_no_year(text)` — 无年份匹配（修订版标准）
6. `_exact_match_typed(text)` — 带类型前缀匹配
7. `_fuzzy_match_with_context(raw_name)` — 上下文感知模糊匹配

## 4. 风险点

| 风险 | 严重度 | 缓解措施 |
|------|--------|---------|
| `staticmethod` 绑定依赖 MRO → 改为显式 `self._parser.xxx()` | 中 | 在 StandardParser 保留 staticmethod，ExactMatcher 通过 parser 引用调用 |
| `self.regex` 等 5 个正则对象在 ExactMatcher 中需同步更新 | 低 | 共享引用（同一个对象），不需同步 |
| `self._current_file_kind` 是 StandardParser 的实例变量 | 低 | 改为 `self._parser._current_file_kind` |
| `self.code_mapping` 在 ExactMatcher 中需与 StandardParser 保持一致 | 低 | 共享引用 |
| 性能影响：从 `self._normalize_year()` 变为 `self._parser._normalize_year()` 增加一次属性访问 | 极低 | Python 属性访问开销远小于正则匹配开销，可忽略 |
| mypy 类型检查：原 `staticmethod` 覆盖已有 `# type: ignore[assignment]` | 低 | 重构后不再有 MRO 类型不匹配问题 |

## 5. 测试策略

### 5.1 现有测试安全网

| 测试文件 | 覆盖内容 | 测试数 |
|---------|---------|--------|
| `tests/test_parser.py::TestExactMatchMixin` | 精确匹配基本路径 | ~6 |
| `tests/test_parser.py::TestForeignHandlerMixin` | 国外标准后处理 | ~2 |
| 集成测试 | StandardParser.parse() 全流程 | ~散落各处 |

### 5.2 需补充的测试（Phase 0）

按匹配通道逐个补快照测试：

| 方法 | 正常用例 | 边界用例 | 预估 |
|------|---------|---------|------|
| `_exact_match` | GB/T 123-2020 | 无年份、无部分号 | 3 |
| `_exact_match_db` | DB35/T 123-2020 | 无 T 类型、无年份 | 2 |
| `_exact_match_typed` | ISO/IEC 123-2020 | 无 endorser、无年份 | 2 |
| `_exact_match_no_year` | MIL-STD-810G | 无字母后缀（应返回 None） | 2 |
| `_exact_match_bpvc` | ASME BPVC IX-2021 | 非 BPVC ASME 标准 | 2 |
| `_exact_match_itu` | ITU-T G.992.1-1999 | 无年份 | 2 |
| `_fuzzy_match_with_context` | 模糊文件名 | code_mapping 不匹配 | 2 |
| **合计** | | | **~15** |

### 5.3 行为等价验证

重构完成后，运行现有 parser 全量测试：
```bash
pytest tests/test_parser.py tests/ -k "parser" -v
```

如果全部通过，即为行为等价。

## 6. 执行顺序

### Phase A：补快照测试（不改源码）
1. 创建 `tests/unit/scan/parser/test_exact_matcher_snapshot.py`
2. 使用真实 `StandardParser` 实例 + `build_code_mapping()` 构造测试数据
3. 每个匹配通道 ≥2 用例（正常 + 边界）
4. 验收：`pytest tests/unit/scan/parser/test_exact_matcher_snapshot.py -v` 全绿

### Phase B：提取 ExactMatcher
1. 创建 `pilotstd/scan/parser/_exact_matcher.py`
2. 迁移 7 个匹配通道方法
3. 注入 `parser` 引用，替换所有 `self._normalize_year()` → `self._parser._normalize_year()`
4. 复制 `self.regex`, `self.code_mapping` 引用

### Phase C：更新 StandardParser
1. 移除 `ExactMatchMixin` 继承
2. `__init__` 中创建 `self._matcher = ExactMatcher(self)`
3. `parse()` 入口中将 `self._exact_match(text)` → `self._matcher._exact_match(text)`
4. 删除 `_exact.py` 文件

### Phase D：回归验证
1. `pytest tests/ -k "parser" -v` 全绿
2. `ruff check` 无警告
3. 手动验证 5 条真实标准文件名的解析结果

## 7. 回退方案

**并行运行策略**（推荐）：
- Phase B 中，`StandardParser` 同时保留 Mixin 继承和新 `ExactMatcher` 实例
- 添加特性开关 `_USE_EXACT_MATCHER = True`，默认使用新类
- 若发现回归，设置 `_USE_EXACT_MATCHER = False` 立即回退
- 稳定运行 1 个迭代周期后，删除 Mixin 和开关

**预估工时**：4-6 小时（测试 2h + 提取 2h + 回归 2h）

---

> **决策建议**：本项目当前优先级为"暂缓白名单"。触发条件为以下任一：
> 1. ParserCore 发生 API 变更需要修改匹配通道
> 2. 团队有新人需要理解解析器架构
> 3. mypy 严格模式需要消除 `# type: ignore[assignment]` 警告
