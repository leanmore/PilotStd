# scan/parser.py 结构分析

> 分析日期：2026-06-30

---

## 当前结构

| 属性 | 值 |
|------|-----|
| 总行数 | **962** |
| 类 | 1 个（`StandardParser`，~764 行） |
| 模块级函数 | 2 个（`_compile`, `edition_skip_pattern`） |
| 模块级常量 | 12 个（正则模式 + 查询表） |
| 实例方法 | 23 个 |

---

## 方法清单

### 模块级（第 1-198 行，~198 行）

| 符号 | 类型 | 说明 |
|------|------|------|
| `PRESERVED_MULTI_WORD` | frozenset | 保留多词代号 |
| `FOREIGN_CODE_SET` | frozenset | 国外标准编码集 |
| `ISO_IEC_SET` | frozenset | ISO/IEC 集合 |
| `ITU_CODES` | frozenset | ITU 前缀 |
| `CAC_PREFIXES` | frozenset | 食品法典前缀 |
| `API_TYPES/IEC_TYPES/MIL_TYPES/SAE_PREFIXES` | frozenset | 各组织类型码 |
| `_ROMAN_MAP` | dict | 罗马数字映射 |
| `_PFX/NUM/PART/YEAR/SEP` 等 | re patterns | 正则拆分组件 |
| `_compile()` | func | 正则编译 |
| `_LANG_DETECTOR` | ref | 语言检测函数 |
| `_FOREIGN_GROUP_MAP` | dict | 国外标准分组 |

### 核心解析（3 方法，~170 行）

| 方法 | 行 | 描述 |
|------|-----|------|
| `__init__` | 48 | 构造，加载 code_mapping |
| `parse` | **101** | 主入口：去扩展名→匹配→构件名 |
| `_classify_code` | 19 | 代号分类（国标/行业/国外/DB） |
| `_post_process` | 14 | 后处理协调 |

### 国外标准处理（6 方法，~130 行）

| 方法 | 行 | 描述 |
|------|-----|------|
| `_post_process_foreign` | 9 | 国外标准后处理入口 |
| `_dispatch_foreign_handler` | 12 | 按分组派发 |
| `_handle_letter_class` | 29 | 字母类标准（ASTM/BS/API等） |
| `_handle_type_prefix` | 29 | 类型前缀标准（API Spec/IEC TR等） |
| `_handle_special_sep` | 27 | 特殊分隔符标准 |
| `_handle_unique` | 25 | 独特格式标准 |

### 精确匹配（7 方法，~225 行）

| 方法 | 行 | 描述 |
|------|-----|------|
| `_exact_match` | 14 | 通用精确匹配 |
| `_exact_match_no_year` | 33 | 无年份精确匹配 |
| `_exact_match_typed` | 30 | 类型前缀匹配 |
| `_exact_match_db` | 28 | 地方标准匹配 |
| `_exact_match_bpvc` | 28 | ASME BPVC 匹配 |
| `_exact_match_itu` | 35 | ITU 标准匹配 |
| `_fuzzy_match_with_context` | 57 | 模糊匹配兜底 |

### 工具函数（8 方法，~140 行）

| 方法 | 行 | 描述 |
|------|-----|------|
| `_clean` | 12 | 文本清理 |
| `_detect_language` | 5 | 语言检测 |
| `_detect_file_kind` | 17 | 文件类型判断 |
| `_normalize_year` | 5 | 年份规范化 |
| `_trim_prefix` | 15 | 前缀截断 |
| `_extract_number` | 18 | 编号提取 |
| `_extract_num_prefix` | 12 | 编号前缀提取 |
| `_extract_part` | 11 | 分册号提取 |
| `_clean_std_name` | 35 | 标准名称清理 |
| `_validate_result` | 22 | 结果校验 |
| `_build_result` | 55 | 结果对象构建 |

---

## 分组统计

| 分组 | 方法数 | 总行数 | 占比 |
|------|--------|--------|------|
| 模块常量 | 14 符号 | 198 | 21% |
| 核心解析 | 4 | 182 | 19% |
| 精确匹配 | 7 | 225 | 23% |
| 国外标准 | 6 | 130 | 14% |
| 工具函数 | 10 | 190 | 20% |
| 空行/注释 | — | 37 | 3% |

---

## 依赖关系

| 符号 | 外部引用数 | 说明 |
|------|-----------|------|
| `StandardParser` | 6 | facade, query engine, ahbz adapter, tests |
| `FOREIGN_CODE_SET` | 3 | std_utils, query engine, test_query |
| `ISO_IEC_SET` | 1 | std_utils |
| `_ROMAN_MAP` | 1 | std_utils |
| `CAC_PREFIXES`, `ITU_CODES` | 1 | query engine |

---

## 拆分建议

```
pilotstd/scan/parser/
├── __init__.py         ← StandardParser 核心类（__init__ + parse + _classify + _post_process）
├── _constants.py       ← 所有正则模式 + 查询表（~200行）
├── _exact.py           ← 7 个精确匹配方法（~225行）
├── _foreign.py         ← 6 个国外标准处理方法（~130行）
└── _utils.py           ← 10 个工具函数（~190行）
```

| 模块 | 行数 | 内容 |
|------|------|------|
| `__init__.py` | ~200 | 核心 + 组合类 |
| `_constants.py` | ~200 | 正则模式 + 查询表（可独立测试） |
| `_exact.py` | ~225 | 精确匹配变体 |
| `_foreign.py` | ~130 | 国外标准处理 |
| `_utils.py` | ~190 | 工具函数 |

### 导入兼容性

所有外部引用需保持不变，`__init__.py` 重导出 `StandardParser` 类和模块级常量。

---

## 拆分优先级

| 优先级 | 理由 |
|--------|------|
| **中** | 962 行。模块常量占 200 行，精确匹配占 225 行，可以独立 |
| 收益 | 按职责拆分后每个文件 <250 行 |
| 风险 | 外部引用较多（6 个文件），需确保所有模块级常量可导入 |
