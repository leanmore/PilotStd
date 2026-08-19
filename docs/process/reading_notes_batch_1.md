# 精读笔记 — 第 1 批（项目入口）

- **Created**: 2026-08-19T21:23:00+08:00
- **Updated**: 2026-08-19T21:23:00+08:00
- **批次状态**: 待确认（等待人类 Gate 确认）
- **精读深度判定留痕**: 依据审计报告描述「CLAUDE.md = 治理文档/项目核心指令/与 G-037 联动」「README.md = 项目入口」→ 判定为**核心入口 → 逐字精读**（全文）

---

## 1. CLAUDE.md（205 行）

### 1.1 结构与职责
| 章节 | 内容 | 关联文档 |
| :--- | :--- | :--- |
| §1 核心铁律 | 5 条（密钥/except/日志/去重/Conventional Commits） | — |
| §2 强制工作流 | 三位一体 SOP 五步 + Inline 指令分级 + 读文档触发表（13 条）+ 冲突处理 | spec-lite-template.md |
| §3 门禁规则 | G-010/020/025/030/031/034 + 强制执行层（Hooks/CI） | gates.md |
| §4 验证交付 | .test_pass 机制 + 交付报告模板 | .claude/.test_pass |
| §5 常用命令 | check_all.sh / pytest / vulture 等 | — |
| §6 收工流程 | Knowledge Trigger（memory.md）+ 进度日志（gen_daily_log.py） | .claude/memory.md、archive/项目进度日志.md |
| §7 Ruff/MyPy 边界 | "动哪改哪"规则 + 多工具联合豁免规范 | — |
| §8 能力矩阵同步 | generate_capabilities.py 触发条件 | capabilities_registry.md |

### 1.2 引用有效性核验（规则 3 前置）
| 引用 | 状态 |
| :--- | :--- |
| L43 development-flow.md、L45-48 reference/*、L49 ci-lessons、L50 gates.md、L52 technical-debt.md、L53-54 coding-standards/pre-commit-checklist、L55 index.md | ✅ 全部存在（审计已确认） |
| L37 spec-lite-template.md | ✅ 存在 |
| L139 gen_daily_log.py → archive/项目进度日志.md | ✅ 脚本存在；⚠️ 见待确认 #3 |

### 1.3 发现的问题
1. **日志表述歧义（潜在）**：L9 "日志唯一入口：LoggerManager()，禁止 print 或 _log()"——实际代码标准用法是模块级 `logging.getLogger(__name__)`（LoggerManager 是配置初始化入口）。新执行者可能误解为禁止使用 logging 模块。→ 待确认是否需澄清措辞。
2. **进度日志路径**：L139 固定指向 `docs/archive/项目进度日志.md`，但审计发现该主题共 3 份文件并存（见 pending #3）。

## 2. README.md（117 行）

### 2.1 结构与职责
功能特性（6 项）→ 界面 → 快速开始 → 部署方式（exe/Docker/源码）→ 依赖文件（4 个）→ 技术栈 → 目录结构 → 开发与测试 → 许可证。

### 2.2 引用有效性核验
| 引用 | 状态 |
| :--- | :--- |
| LICENSE、assets/screenshots/main_window.png、desktop/requirements-win.txt、docker-compose.yml | ✅ 全部有效（第 7 批已验证） |
| L105-109 Playwright E2E 指引（docker/app.py 后端） | ✅ 与 CONTRIBUTING.md 一致 |

### 2.3 发现的问题（数据过时/不一致）
1. **适配器数量自相矛盾**：L15 功能特性"6 个适配器" vs L75 目录结构"7 个适配器" vs 实际 22 个（Q22-Q23 后）→ **README 内部不一致 + 与代码不一致**。
2. **badge 过时**：L6 "Tests-942 passed"（历史）、L9 "python-3.12+"（实际 3.14）。
3. **公告监控描述**：L18 "定期拉取国家标准公告，交叉比对本地标准库"——与当前 announcement 子系统（gb/hb/db 三适配器增量抓取）基本一致，无重大问题。
4. **目录结构遗漏**：L70-91 未列 `pilotstd/announcement/`、`pilotstd/wechat_ip/`、`pilotstd/monitor/`、`pilotstd/task/`、`config/`、`data/`、`docs/` 等实际存在的目录（结构图与代码现状有差距）。

## 3. 交叉关联（本批与前序审计）
- CLAUDE.md 触发条件表是"文档导航唯一权威"→ 与 DOCUMENTATION_MAP.md 目标（阶段 C 生成）直接相关：地图需覆盖触发表未列的文档（如 guides/、superpowers/）。
- README.md 的过时数据已在审计 §6 记录（#257），本批精读补充了 L75 内部矛盾与目录遗漏细节。

## 5. Q1-1 适配器数量证据链（2026-08-19T21:31 核实，规则 1 留痕）

**结论：权威口径 = 21 个生产查询适配器（ALL_ADAPTERS 注册表）**

| 口径 | 数量 | 证据 |
| :--- | :--- | :--- |
| 生产查询适配器（注册） | 21 | `pilotstd/query/adapters/registry.py:27-50` ALL_ADAPTERS（ahbz, ccsn, csres, cssn, dbba, energy, gongbiaoku, hbba, iso_gov, jjg, jtst, mee, miit, ncha, njbz365, nrsis, sppt, sppt_local, std_gov, tdpress, ttbz = 21 key） |
| 查询适配器文件（含 Mock） | 22 | `pilotstd/query/adapters/` 目录：21 业务 .py + mock.py（base/registry/__init__/_njbz365_session_manager 为基础设施非适配器） |
| Mock 适配器 | 1 | `mock.py`（MockQueryAdapter），docs/adapters/README.md mock 行注明"不注册到 ALL_ADAPTERS" |
| README.md L15"6 个" | 过时 | Q22-Q23（2026-07-24）前统计；当前 registry 21 |
| README.md L75"7 个" | 过时 | 同上 |
| modules/query.md"8（7+1Mock）" | 过时 | 同上，第 2 批将标注修正 |

**差异原因**：docs/adapters/README.md 头部口径含 Mock（22），表格与注册表口径为生产 21；README.md 的 6/7 为历史遗留未更新。

**修改建议（阶段 C 执行）**：README.md 适配器数量统一为"21 个查询适配器（registry.py 注册）"，依据本证据链。

> 其他适配器类别（与"22 个查询适配器"口径无关，供地图参考）：下载适配器 1（download/adapters/openstd_download.py）、公告适配器 3（announcement/adapters/samr_{gb,hb,db}.py）、通知渠道 4（core/notification/channels/{wechat,telegram,feishu,dingtalk}.py，命名 Channel 非 Adapter）。
