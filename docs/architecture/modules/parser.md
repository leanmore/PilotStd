# 模块文档：标准号解析器（Parser）

| 属性 | 值 |
|------|-----|
| 模块路径 | `pilotstd/scan/parser/` |
| G-031 映射 | `pilotstd/core/parser.py` |
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

## 相关文档

- [ADR-001](../decisions/ADR-001-modal-dialog-auto-clicker.md) — 事件驱动架构决策
- [扫描模块](scan.md) — 文件扫描与解析器调用
