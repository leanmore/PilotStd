# 模块文档：扫描模块（Scan）

| 属性 | 值 |
|------|-----|
| 模块路径 | `pilotstd/scan/` |
| G-031 映射 | `pilotstd/scan/`（`parser/` 子包由 [parser.md](parser.md) 承载，本文件不重复要求） |
| 核心文件 | `scanner.py`、`parser/`、`watcher.py` |
| 总行数 | ~788（含 parser 子包） |
| 状态 | 活跃 |

## 模块职责

遍历文件系统目录，识别文件名中的标准编号，调用解析器提取结构化字段，输出可查询的标准条目列表。是 PilotStd 标准管理流水线的入口——"扫描 → 查询 → 下载 → 规范化 → 归档" 的第一步。

## 架构

```
pilotstd/scan/
├── scanner.py           — 文件扫描器，递归遍历目录
├── parser/              — 标准号解析器（详见 parser.md）
│   ├── __init__.py      — StandardParser 入口
│   ├── _core.py         — ParserCore 组合容器
│   ├── _exact.py        — 正则匹配引擎
│   ├── _foreign.py      — 国外标准后处理
│   └── ...              — 5 个 Handler + 常量定义
├── watcher.py           — 文件系统监听器（目录变更自动触发扫描）
├── edition_detect.py    — 版本/年代检测
├── filename_normalizer.py — 文件名规范化
└── lang_detect.py       — 语言检测
```

## 关键接口

| 文件 | 类/函数 | 说明 |
|------|---------|------|
| `scanner.py` | `scan_directory()` | 递归扫描目录，返回文件路径列表 |
| `scanner.py` | `FileScanner` | 扫描器主类，协调遍历→解析→去重 |
| `parser/__init__.py` | `StandardParser.parse()` | 文件名 → `ParsedStdInfo` |
| `watcher.py` | `FileWatcher` | 文件系统事件监听 |

## 扫描流程

```
用户选择目录
  → FileScanner.scan_directory() 递归遍历
  → 对每个文件调用 StandardParser.parse(filename)
  → 去重（同标准号不同文件）
  → 输出 ParsedStdInfo 列表
  → 传递给查询引擎进行在线查询
```

## 依赖关系

- `pilotstd/scan/parser/` — 标准号解析（核心依赖）
- `pilotstd.models.ParsedStdInfo` — 输出数据模型
- `pilotstd.core.file_index` — 文件索引（去重查询）
- `pilotstd.core.file_utils` — 文件操作工具

## 平台差异处理

`scanner.py` 的目录遍历异常处理中，Windows 特有的 `OSError.winerror`（错误码 206/123 表示路径过长）通过 `getattr(e, "winerror", 0)` 读取，非 Windows 平台安全降级（不访问不存在属性，直接抛出原始异常）——保证 Linux CI 静态检查（mypy G-038）与运行时行为均正常。

## 相关文档

- [解析器模块](parser.md) — 标准号解析详细架构
- [UI 模块](ui.md) — 扫描触发入口（MainWindow）
