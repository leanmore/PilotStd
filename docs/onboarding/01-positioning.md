# 01 · 项目定位：PilotStd 到底是什么

> 本文件回答四个问题：**解决什么问题、给谁用、做什么、不是什么**。  
> 读完应能不看稿讲 3 分钟。

---

## 一、一句话定位

> **PilotStd 是企业标准文件的“收货—验真—补货—上架—保质期管理”系统。**

它不是一个“把文件搬来搬去”的小工具，而是围绕**标准号**建立的一条业务链：

```text
Inbox 文件
  → 解析标准号
  → 查询现行/废止/被代替
  → 缺的补下载
  → 按分类目录归档
  → 持续跟踪有效性
  → 过期作废分流
  → 通知/审计
```

---

## 二、它解决的真实痛点

### 1. 标准文件散、命名乱

企业标准库常见状态：

- 文件来自不同网站、不同人、不同时间；
- 文件名有全角/半角、无年份、带“修改单”、带广告后缀；
- 同一标准有多个版本、多个副本；
- 人工建目录、人工改名，容易错。

PilotStd 用 `StandardParser` 从文件名解析标准号，用 `FileMover` 统一目录/文件名。

### 2. 标准会废止、会被代替

标准不是静态文件：

- 今天现行，明年可能废止；
- 有替代标准；
- 有“即将实施”；
- 有“修改单”；
- 过期标准不应和现行标准混在一起。

PilotStd 通过查询适配器/公告缓存判断状态，并把废止标准分流到“过期作废”。

### 3. 缺失标准要补下载

用户手里只有一部分标准；查询发现缺失或新版时，系统可以下载补齐（目前主要支持 GB 类，具体以适配器为准）。

### 4. 大批量操作需要可观测

几百个文件同时进 Inbox 时，人工无法逐条确认。系统需要：

- 批量归档；
- 失败明细；
- 聚合通知；
- 可追踪的日志/数据库记录。

---

## 三、给谁用

| 角色 | 典型诉求 | 主要入口 |
|---|---|---|
| **标准管理员/资料员** | 批量整理、查重、归档、找过期标准 | Web / Win |
| **工程师/业务人员** | 查某标准是否现行、有没有替代、下载全文 | Web / Win |
| **运维/部署人员** | 部署 Docker、看健康、备份、排障 | Docker / 日志 |
| **管理者** | 看标准库规模、废止比例、任务结果 | Web 看板/通知 |

新员工不需要一开始记住所有角色，但要知道：**同一个后端，服务的是不同使用深度的人**。

---

## 四、它做什么（能力地图）

| 能力 | 说明 | 主要代码 |
|---|---|---|
| 扫描 | 遍历目录，过滤扩展名/跳过目录 | `pilotstd/scan/scanner.py` |
| 解析 | 从文件名解析代号/序号/年份/部分号/名称 | `pilotstd/scan/parser/` |
| 查询 | 多站点查询标准状态、缓存、配额、冷却 | `pilotstd/query/` |
| 分类路由 | 按状态分堆：归档/下载/待确认/兜底 | `pilotstd/manager/classifier.py`、`pilotstd/pipeline/router.py` |
| 下载 | 适配器下载、重试、落盘、采标跳过 | `pilotstd/download/` |
| 归档 | 生成目录/文件名、移动、去重、写索引 | `pilotstd/organizer/`、`pilotstd/manager/organize/` |
| 有效性 | 定时/手动 L1/L2/L3 检查 | `pilotstd/core/validity_checker.py` |
| 公告 | 拉取公告、匹配本地标准 | `pilotstd/announcement/` |
| 通知 | 事件构建、聚合、渠道发送 | `pilotstd/core/notification/` |
| 三端 | Web / Win / CLI | `docker/`、`web/`、`pilotstd/ui/`、`pilotstd/cli/` |

---

## 五、它不是什么

这一节很重要，能避免新人建立错误预期。

### 1. 不是通用文档管理系统

它围绕“标准号”组织，不是任意文件都能自动分类。没有标准号的文件只能走兜底镜像或人工处理。

### 2. 不是纯下载器

下载只是主链的一环。下载前有解析/查询，下载后有归档/索引/有效性。

### 3. 不是三端同一套 UI

Web、Win、CLI 共享核心引擎，但**编排不同**：

- Web 是五段式 API；
- Win 一键是 `auto_run_stream`；
- CLI 是 `auto_run` / 分命令；
- Docker monitor 是另一条 `scan → archive` 入口。

### 4. 不是“点一下所有事都自动完成”

不同入口的闭环程度不同。当前已知边界见 [`08-known-boundaries.md`](08-known-boundaries.md)，例如：

- 生产当前 Web 五段式的下载结果不会自动进入归档；本地代码已修，待部署；
- Docker monitor 只做扫描+归档，不查询/不下载；
- Win 的 `FileWatcher` 只更新索引，不归档。

### 5. 不是“查到废止就自动搬文件”

默认 `validity.auto_move_expired=false`；只有 L2（适配器实时查询）证据 + 开关开启，才搬“过期作废”。

---

## 六、三端形态一览

| 端 | 技术 | 启动 | 适用场景 | 入口 |
|---|---|---|---|---|
| Web | Vue3 + FastAPI + SQLite | `docker compose up -d`，端口 9028 | 局域网多人、远程访问 | `web/src/views/TaskView.vue`、`docker/api/` |
| Win | PyQt6 | exe 或 `python main.py` | 单机桌面、离线/半离线 | `pilotstd/ui/` |
| CLI | argparse | `python main.py --cli ...` | 批量/自动化/排障 | `pilotstd/cli/commands/` |

三端都最终调用 `pilotstd/manager/` 的门面；**业务核心只有一套**。

---

## 七、用“物流中心”理解它

| 物流概念 | PilotStd |
|---|---|
| 收货区 | `/inbox` |
| 贴标签 | 扫描 + 标准号解析 |
| 验真/查有效期 | 查询公告/适配器 |
| 缺货补货 | 下载 |
| 上架 | 归档到分类目录 |
| 隔离区 | `过期作废/` |
| 回执 | 通知 |
| 自动收货线 | Docker `monitor._on_file` |
| 仓库台账 | `file_index` / `standards` / `standard_validity` |

这个类比能解释 80% 的业务；剩下 20% 是“不同入口的编排差异”和“有效性证据等级”。

---

## 八、关键术语（先记 8 个）

| 术语 | 一句话 | 详见 |
|---|---|---|
| 标准号 | 从文件名解析出的身份，如 `GB/T 1234-2020` | [`glossary.md`](glossary.md) |
| `logical_code` | 标准代号，如 `GB/T`、`HG/T`、`TSG` | [`glossary.md`](glossary.md) |
| `ParsedStdInfo` | 解析后的标准信息对象 | `pilotstd/models.py` |
| `QueryResult` | 一次查询的结果对象 | `pilotstd/query/models.py` |
| `effect_status` | 查询得到的当前状态 | [`02-file-journey.md`](02-file-journey.md) |
| `standard_validity` | 历史有效性/待复检表 | [`04-data-model.md`](04-data-model.md) |
| 规范化 | 预览新文件名，不移动文件 | [`02-file-journey.md`](02-file-journey.md) |
| 过期作废 | 物理目录，不是状态值 | [`08-known-boundaries.md`](08-known-boundaries.md) |

---

## 九、边界与坑（先知道，不深挖）

- 生产当前 Web 下载不回灌归档；本地代码已修，待部署；
- Docker monitor 只 scan + archive；
- Win watcher 只更新索引；
- 手动/一键下载任务不持久化；
- `standard_validity` 是跟踪表，不是归档第一权威；
- Word 重解析使用空 `scan.code_mapping`，TSG 可能进 `T 未知行业(T)`。

每一条的证据、影响和“为什么不能顺手修”，见 [`08-known-boundaries.md`](08-known-boundaries.md)。

---

## 十、自检

读完本文件，试着不看稿回答：

1. PilotStd 用一句话怎么介绍？
2. 它解决哪四个真实痛点？
3. 它“不是什么”？至少说 3 个。
4. 三端分别是什么形态？各自入口在哪？
5. 为什么不能笼统说“一键处理”？

参考答案见 [`10-assessment.md`](10-assessment.md)。
