# PilotStd 新员工完整介绍

> 面向：**完全不了解 PilotStd 的新员工**（开发、运维、产品均可读）。  
> 目标：不是“听过”，而是学完后能**讲清业务、跑通主链、读懂代码、排查常见问题**。  
> 建议周期：**约 5 个半天（6 个模块）**；时间充裕可拉长到 2 周，每天 2 小时。

---

## 一、这份材料怎么用

| 你的时间 | 建议阅读 |
|---|---|
| 只有 30 分钟 | 本文件的「一页速览」+ [`02-file-journey.md`](02-file-journey.md) |
| 有 2 小时 | 本文件 + [`01-positioning.md`](01-positioning.md) + [`02-file-journey.md`](02-file-journey.md) + [`03-architecture.md`](03-architecture.md) |
| 有 5 个半天 | 按下面的课程表完整走，并完成 [`09-labs.md`](09-labs.md) |
| 准备改代码 | 加读 [`04-data-model.md`](04-data-model.md)、[`05-code-map.md`](05-code-map.md)、[`07-dev-workflow.md`](07-dev-workflow.md) |
| 准备部署/排障 | 加读 [`06-runtime-ops.md`](06-runtime-ops.md)、[`08-known-boundaries.md`](08-known-boundaries.md) |

---

## 二、课程表（约 5 个半天 / 6 个模块）

| 模块 | 主题 | 读完/做完能做到 | 对应文档 |
|---|---|---|---|
| M0 | 项目定位与全景 | 说清“是什么/为什么/不是什么” | 本文件、[`01-positioning.md`](01-positioning.md) |
| M1 | 一条文件的旅程 | 完整讲清主链、每站写哪张表 | [`02-file-journey.md`](02-file-journey.md) |
| M2 | 三端与架构 | 分清 Web / Win / CLI / Docker monitor | [`03-architecture.md`](03-architecture.md) |
| M3 | 数据模型与核心模块 | 知道三张核心表和各模块职责 | [`04-data-model.md`](04-data-model.md) |
| M4 | 运行、部署、排障 | 能启动、看日志、查健康、做备份 | [`06-runtime-ops.md`](06-runtime-ops.md) |
| M5 | 实战与考核 | 真跑、真改、teach-back | [`09-labs.md`](09-labs.md)、[`10-assessment.md`](10-assessment.md) |

固定的单次节奏：

```text
10 min  回顾昨天 + 提问
20 min  概念 + 一张图
40 min  代码走读（只读关键入口）
60 min  动手：放文件/看日志/查数据库
20 min  复盘 + 小测
```

---

## 三、一页速览

### 1. 一句话

> **PilotStd 是企业标准文件的“收货—验真—补货—上架—保质期管理”系统。**

它把散落在 Inbox 的标准文件，按“解析 → 查询有效性 → 下载缺失 → 归档 → 持续时效检查”串成一条链。

### 2. 一条主链

```mermaid
flowchart LR
    A[Inbox / 扫描目录] --> B[扫描 + 标准号解析]
    B --> C[查询 / 有效性判断]
    C --> D{需要下载?}
    D -- 是 --> E[下载到 /standards 根]
    D -- 否 --> F[归档]
    E --> F
    F --> G[写 file_index / standards / standard_validity]
    G --> H[兜底 / 清理空目录]
    H --> I[通知 / 汇总]
    G -. 定时/手动 .-> J[validity_check]
    J -- L2 + 开关开启 --> K[移入 过期作废]
```

### 3. 三个客户端，一个引擎

| 客户端 | 形态 | 主入口 | 一句话 |
|---|---|---|---|
| **Web** | Vue3 + FastAPI + Docker | `web/src/views/TaskView.vue`、`docker/api/` | 五段式：scan → query → download → normalize → archive |
| **Win** | PyQt6 桌面 | `pilotstd/ui/workers/auto.py` | 一键 `auto_run_stream`；也可手动分步 |
| **CLI** | 命令行 | `pilotstd/cli/commands/`、`main.py --cli` | `auto` / `scan` / `query` / `download` / `organize` |

三者共享 `pilotstd/manager/` 下的 `StandardManager` 与核心引擎，但**编排方式不同**，不能笼统说“一键处理”。

### 4. 三张核心表

| 表 | 回答的问题 |
|---|---|
| `file_index` | 文件现在在哪、属于哪个标准、状态是什么 |
| `standards` | 这个内容身份是什么（sha256 / code / name / size） |
| `standard_validity` | 这个标准的历史有效性、下次检查时间 |

### 5. 五个必须先懂的词

| 词 | 一句话 |
|---|---|
| **标准号** | 从文件名解析出的“身份”，如 `GB/T 1234-2020`；文件名只是原料 |
| **`effect_status`** | 本次查询得到的“当前状态”，归档目录以它为准 |
| **`standard_validity`** | 历史跟踪/待复检表，不是归档第一权威 |
| **规范化** | 预览新文件名；真正改名/移动发生在归档 |
| **过期作废** | 物理目录；默认不是“查到废止就自动搬” |

---

## 四、先记住的六句话

1. **一个引擎，三种入口**：Web / Win / CLI 共享核心，不共享编排。
2. **一条主链**：扫描 → 查询 → 下载 → 归档 → 收容 → 通知。
3. **两条时间线**：查询是“现在”，`standard_validity` 是“历史/待复检”。
4. **归档才写索引**：`scan_directory` 只解析，不搬文件、不写 `file_index`。
5. **规范化是预览**：真正命名在 `FileMover.normalize_filename()`。
6. **不同入口闭环程度不同**：Web 五段式、Win 一键、Docker monitor 各自不同，详见 [`08-known-boundaries.md`](08-known-boundaries.md)。

---

## 五、学完的验收标准

学完后，新员工应能：

- [ ] 用 5 分钟讲清 PilotStd 解决什么问题、三类用户怎么用；
- [ ] 画出“一条文件从 Inbox 到归档”的 7 站流程图；
- [ ] 说出每站对应的核心函数和至少一张表；
- [ ] 区分 Web 五段式、Win `auto_run_stream`、Docker `monitor._on_file`、Win `FileWatcher`；
- [ ] 在本地跑通后端测试和前端四件套；
- [ ] 用一个日志关键字定位到代码函数；
- [ ] 说出至少 3 个当前已知边界，并解释为什么不能“顺手修”。

考核方式见 [`10-assessment.md`](10-assessment.md)。

---

## 六、文档地图

| 文档 | 内容 |
|---|---|
| [`00-how-to-use.md`](00-how-to-use.md) | 文档使用方法、按问题类型查文档、检索脚本 |
| [`01-positioning.md`](01-positioning.md) | 项目定位、问题域、用户、能力地图、不是什么 |
| [`02-file-journey.md`](02-file-journey.md) | 一条文件的七站旅程、数据流、异常分支 |
| [`03-architecture.md`](03-architecture.md) | 三端一引擎、分层、模块职责、运行时拓扑 |
| [`04-data-model.md`](04-data-model.md) | 三张核心表、辅助表、状态字段、常用排查 SQL |
| [`05-code-map.md`](05-code-map.md) | 10 个入口文件、阅读顺序、测试地图、日志追踪 |
| [`06-runtime-ops.md`](06-runtime-ops.md) | Docker / Win / CLI、配置、日志、健康、备份、排障 |
| [`07-dev-workflow.md`](07-dev-workflow.md) | 环境矩阵、测试、门禁、提交、文档联动 |
| [`08-known-boundaries.md`](08-known-boundaries.md) | 当前缺口/坑：Web 下载、监控、有效性表、Word 重解析等 |
| [`09-labs.md`](09-labs.md) | 5 个安全的上手实验 |
| [`10-assessment.md`](10-assessment.md) | teach-back、题库、评分表 |
| [`11-open-questions.md`](11-open-questions.md) | 已查清但待决策的问题（v2 采样、announcement 语义等） |
| [`12-data-repair-plan.md`](12-data-repair-plan.md) | 709 条畸形 validity 键的修复方案（仅方案，不执行） |
| [`13-coverage-matrix.md`](13-coverage-matrix.md) | 功能覆盖/认知台账：哪些已了解、哪些还未补 |
| [`14-decision-log.md`](14-decision-log.md) | 用户决策记录：已定方向、待查/待执行事项 |
| [`15-query-adapter-matrix.md`](15-query-adapter-matrix.md) | 21 个查询适配器逐站能力/配额矩阵 |
| [`16-notification-matrix.md`](16-notification-matrix.md) | 44 个通知事件 × 4 渠道矩阵 |
| [`17-validity-state-machine.md`](17-validity-state-machine.md) | 有效性 L1/L2/L3 状态机 |
| [`18-schema-migrations.md`](18-schema-migrations.md) | 41 张表 + 29 个迁移模块清单 |
| [`19-web-win-inventory.md`](19-web-win-inventory.md) | Web/Win/CLI 功能与分支清单 |
| [`20-api-route-inventory.md`](20-api-route-inventory.md) | 132 个 API 路由全量清单 |
| [`21-notification-builders.md`](21-notification-builders.md) | 44 个通知事件的 builder/payload 明细 |
| [`22-announcement-deep-dive.md`](22-announcement-deep-dive.md) | 公告抓取/解析/匹配/OCR 细分 |
| [`23-peripheral-features.md`](23-peripheral-features.md) | 收藏/待确认/任务/上传/导出/备份/用户/设置 |
| [`24-ui-action-matrix.md`](24-ui-action-matrix.md) | Web 21 视图 / Win 12 FlowEngine 动作矩阵 |
| [`25-fix-readiness.md`](25-fix-readiness.md) | 修复就绪度：L0–L4 颗粒度与逐问题判断 |
| [`26-fix-dossiers.md`](26-fix-dossiers.md) | 6 个重点问题的 L3/L4 修复 dossier |
| [`27-implementation-log.md`](27-implementation-log.md) | 本轮本地代码改动、测试与回滚 |
| [`28-a-completion-and-deploy.md`](28-a-completion-and-deploy.md) | A 阶段收口、v74 迁移与 B 阶段部署/回滚手册 |
| [`glossary.md`](glossary.md) | 术语表（按字母/中文） |

---

## 七、维护约定

- 本目录只写“新人需要知道的稳定事实”，不写一次性故障报告；
- 代码/行为变化时，优先更新 [`02-file-journey.md`](02-file-journey.md)、[`03-architecture.md`](03-architecture.md)、[`08-known-boundaries.md`](08-known-boundaries.md)；
- 已知缺口如果被修复，从 [`08-known-boundaries.md`](08-known-boundaries.md) 移除，并在 commit 里注明；
- 不要在 onboarding 文档里复制大段代码，只保留入口路径和判断依据。
