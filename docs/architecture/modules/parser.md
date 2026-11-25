# 模块文档：标准号解析器（Parser）

| 属性 | 值 |
|------|-----|
| 模块路径 | `pilotstd/scan/parser/` |
| G-031 映射 | `pilotstd/scan/parser/` |
| 核心类 | `StandardParser` |
| 文件数 | 11 |
| 总行数 | ~1,119 |
| 状态 | 活跃 |

## 模块职责

将文件名/标准编号字符串解析为结构化字段（代号、顺序号、年份、部分号），是 PilotStd 标准识别流水线的第一步。所有查询、下载、归档、规范化操作均依赖解析器输出的 `ParsedStdInfo`。

## 架构

```
StandardParser (入口)
├── ExactMatcher (组合注入) — 正则精确/模糊匹配（7 通道分流）
├── _post_process_foreign   — 国外标准后处理（模块级纯函数）
└── ParserCore (组合容器)
    ├── TextCleaner       — 文本清洗（全角→半角、特殊字符替换）
    ├── LanguageDetector  — 中/英文检测
    ├── FileKindDetector  — 文件属性标记（替代/修改单/勘误）
    ├── NumberExtractor   — 年份/顺序号/分册号提取
    └── ResultBuilder     — 构建并校验 ParsedStdInfo
```

> 旧版 `ExactMatchMixin` 已替换为 `ExactMatcher` 组合类，`ForeignHandlerMixin` 已纯函数化。
> 旧版 `UtilsMixin` 已被拆分为 5 个独立 Handler，通过 `ParserCore` 组合。

## 关键接口

| 方法 | 签名 | 说明 |
|------|------|------|
| `parse()` | `(filename: str) -> ParsedStdInfo \| None` | 唯一公开入口，自动完成预处理→匹配→后处理 |
| `_preprocess_input()` | `(raw: str) -> tuple` | 清理 + 语言检测 + 文件类型标记 |
| `_post_process()` | `(info: ParsedStdInfo) -> ParsedStdInfo` | 按代号分类做定向后处理（国外标准映射等） |

## 解析流程

```
输入文件名
  → _preprocess_input (TextCleaner + LanguageDetector + FileKindDetector)
  → 7 通道分流 (DB / BPVC / ITU / exact / typed / fuzzy / no_year)
  → _post_process (_post_process_foreign 按代号分类处理)
  → 输出 ParsedStdInfo { code, number, year, part, kind, ... }
```

## 依赖关系

- `pilotstd.models.ParsedStdInfo` — 输出数据模型
- `pilotstd.core.std_utils.classify_std_code` — 代号分类
- `pilotstd.scan.parser._constants` — 正则片段 + 代号集合（ISO_IEC_SET、FOREIGN_CODE_SET 等）

## 已知待办

- **A-9**：解析失败日志尚未统一为"路径/类型/错误/详情"四段（`pilotstd/scan/parser/__init__.py`）。
  登记于 [技术债 A-9](../../debt/03-open.md)；动日志格式时需同批改断言测试。

## 相关文档

- [ADR-001](../../adr/ADR-001-modal-dialog-auto-clicker.md) — 事件驱动架构决策
- [扫描模块](scan.md) — 文件扫描与解析器调用

> **解析失败日志四段化（2026-10-28，A-9）**：`StandardParser.parse()` 未命中任何匹配器时输出 `解析失败: path=<文件名> type=<扩展名> error=no_match detail=<N>_matchers（值**不含空格**，可直接按 `key=value` 解析）`；沿用项目既有 `xxx失败: key=%s` 风格（参照 `announcement/base.py:184`、`core/audit.py:51`），便于 grep 与排障。

> **2026-11-04 修改单独立身份（D1-2）**：文件名命中 `第N号修改单` 时，`file_kind` 追加
> `第N号修改单`（随 `make_standard_filename` 写入文件名与索引名），使修改单与本体在
> `file_index`/目录中可区分；扫描代号仍统一为带斜杠形态（`GBT 1234-2020.pdf` → `GB/T`）。

> **2026-11-04 解析边界修复（D1-1/D1-3）**：两位年份按 **70 分界**展开
> （`GB1234-20` → 2020、`GB1234-86` → 1986；`NumberExtractor.normalize_year` 同步修正）；
> 国内标准不再清空 `language`，`(英文版)`/`（英文版）` 也能被识别，中英文版本因此在
> 文件名/索引里可区分。契约：`tests/test_batch3_edge_fixes.py`。

> **2026-11-04 审计补丁**：两位年份展开支持带后缀文件名（`GB1234-20 标准名称.pdf`）；
> `make_standard_filename` 在 `std_name` 已含“第N号修改单”时不再追加 `file_kind`，
> 避免文件名出现重复标识。

> **2026-11-19 注释语言规范化（G-012 [LANG] 收口）**：本目录注释里的英文普通词改为中文、
> 裸小写标识符加反引号；仅注释与 docstring 变更，AST 归一化比对无代码变化（全仓 504 行，见 27 #81）。

## ASME BPVC 识别口径扩展（2026-11-24，P1-7.1 B-5）

`_ASME_BPVC_RE` 扩展支持 `Section` / `Div(ision)` / `Part` / 册篇字母，捕获组口径改为
**1=卷号、2=分册号、3=册篇字母、4=年份**；另加 `(?!\d)` 防止分册号吃掉年份前两位
（例：`BPVC.IX-2021` 曾被匹配成 div=20）。

`_exact_matcher` 同步取值并写入 `num_suffix`。**已知边界**：扫描侧 BPVC 无年份写法
（`Section VIII Div.1`、`II.D`）仍被 `validate_result` 拒绝（属 G5 范围）。
回归：`tests/unit/scan/parser/test_bpvc_section_snapshot.py`。
