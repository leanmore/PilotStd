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

- **watcher 索引失败的可见性（2026-10-17，体检 D-8 第 11 批）**：`watcher.py` 在文件被锁定/已删除时对索引写入 `OSError` 原为 `pass`；现记 debug（`watcher index file failed`），监控链路不再无痕丢事件。**修正（同日）**：该日志不得引用 `file_hash`——哈希计算本身可能抛 `OSError`，此时变量未绑定会二次抛 `UnboundLocalError`（CI 实测）；改用 `path`。

## 相关文档

- [解析器模块](parser.md) — 标准号解析详细架构
- [UI 模块](ui.md) — 扫描触发入口（MainWindow）

> **2026-11-04 修改单标识（D1-2）**：扫描解析阶段把 `第N号修改单` 写入 `file_kind`，
> 归档文件名/索引名因此带上修改单后缀，供有效性检查排除（不随本体搬入“过期作废”）。

> **2026-11-04 归档 unparsed 计数（D1-1）**：`organize_files` 对无法解析的文件累计
> `unparsed` 并 `WARNING` 打印文件名（最多 10 个），不再静默丢弃；结果字典新增
> `unparsed` 字段，便于前端/日志定位命名不支持的输入。

> **2026-11-09 watcher 事件失败可见化（U-3/U-4 批 2b）**：`FileWatchHandler._handle_new_or_modified`
> 的兜底 `except` 由 `debug` 升 `warning`（文案带路径）——watcher 静默失败会让新文件不进索引、
> 归档链少文件且无人知晓；`OSError`（文件被锁/删除）分支仍保持 `debug`（属预期瞬态）。

## 注释语言规范化（2026-11-19）

- G-012 [LANG] 改为按词判定后，本模块注释里的英文普通词改为中文、裸标识符加反引号；
  仅注释与 docstring 变更，AST 比对无代码变化（全仓 504 行，见 27 日志 #81）。

## ASME BPVC 扫描侧识别口径扩展（2026-11-24，P1-7.1 B-5）

`scan/parser/_constants.py` 的 `_ASME_BPVC_RE` 扩展支持 `Section` / `Div(ision)` / `Part` / 册篇字母，
捕获组口径改为 **1=卷号、2=分册号、3=册篇字母、4=年份**；并加 `(?!\d)` 防止分册号吃掉年份前两位
（例：`BPVC.IX-2021` 曾被匹配为 div=20）。

`scan/parser/_exact_matcher.py` 同步取值并写入 `num_suffix`（`D` / `D.M`）。

**已知边界**：扫描侧 BPVC **无年份**写法（`Section VIII Div.1`、`II.D`）仍被 `validate_result` 拒绝
（属 G5 范围，本批未放开；**批次10 已放开，见下节**）。

回归：`tests/unit/scan/parser/test_bpvc_section_snapshot.py`；
缺口依据：`docs/plans/2026-11-24-p1-api-asme-gap.md` §2.2 / §4-G2。

## 解析器无年份/系列词/版次回归（2026-11-25，批次10）

扫描子包 `pilotstd/scan/parser/` 的口径扩展详见 [parser.md](parser.md) 同名章节；本节记录
`pilotstd/scan/` 层面同批变化与边界：

- `parser/_result_builder.validate_result` 对国外/国际代号允许 `year=0`（国内仍要求年份）——
  扫描件「可匹配但缺年份」不再整体判 MISS，`ASME B16.5` / `API STD 610` 等可进入归档/索引链路。
- `parser/_constants._NUM` 支持多字母/连字符后缀（`5CT` / `2A-WSD` / `938-C`）。
- `edition_detect.strip_edition` 在 `_preprocess_input` 中剥离英文序数版次（`11th`），
  避免被 `_YEAR_LOOSE` 当两位年份。
- 新增 `parser/_asme_series.py` 承载 ASME 分类字母/系列词匹配，故 `parse()` 匹配通道 8 → 9。

**已知边界**：`year=0` 记录进入归档后仍需下游按「无年份」展示/去重；国内标准仍不接受无年份。

回归：`tests/unit/scan/parser/test_no_year_and_series.py`、`tests/unit/scan/test_parser_failure_log.py`。
