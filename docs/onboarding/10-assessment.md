# 10 · 考核：teach-back、题库与评分

> 目标：确认新人不是“背过”，而是能**讲清、定位、动手、判断边界**。  
> 建议总时长：90–120 分钟。

---

## 一、考核结构

| 环节 | 时长 | 形式 | 权重 |
|---|---|---|---|
| A. 30 分钟 teach-back | 30 min | 新人讲，导师打断提问 | 40% |
| B. 代码定位 | 20 min | 给日志/需求，找函数 | 20% |
| C. 题库 | 20 min | 口头/书面 | 20% |
| D. 小任务 | 30 min | 改一个测试/补一段日志/写一段文档 | 20% |

通过线：**80%**；任何一项低于 60% 需补学后重考。

---

## 二、A. teach-back 评分表

让新人用 15–20 分钟讲“一条文件的旅程”，导师在以下维度打分（1–5 分）：

| 维度 | 5 分表现 | 1 分表现 |
|---|---|---|
| 业务定位 | 能说清“是什么/不是什么/给谁用” | 只会说“管理标准文件” |
| 主链完整 | 7 站完整，顺序正确 | 漏查询/下载/收尾 |
| 代码入口 | 每站能说 1 个函数/文件 | 只会说“有个 manager” |
| 数据流 | 能说每站读/写哪张表 | 只会说“存数据库” |
| 三端差异 | 能区分 Web/Win/CLI/Monitor | 把三端当同一套 |
| 异常分支 | 能讲解析失败/目标已存在/废止 | 只讲正常路径 |
| 边界意识 | 能主动说 2–3 个当前缺口 | 把现状当设计 |

导师追问示例：

- “这一步如果文件已经存在会怎样？”
- “这条日志对应哪个函数？”
- “为什么 Web 的下载件可能不在分类目录？”
- “`standard_validity` 和 `effect_status` 冲突时谁赢？”

---

## 三、B. 代码定位题

给 7 条日志/现象，要求 2 分钟内说出最先看的文件/函数。

| # | 现象 | 期望定位 |
|---|---|---|
| 1 | `解析失败: path=... error=no_match` | `scan/parser/__init__.py::StandardParser.parse` |
| 2 | `[MONITOR] 归档完成: N 条` | `monitor/scheduler.py::_on_file` |
| 3 | `SQL执行失败: INSERT INTO standard_validity` | `core/validity_checker.py::register_new_standard` |
| 4 | Web 点击下载后文件在 `/standards` 根目录 | `download/engine.py::_save_file` / `TaskView.vue` |
| 5 | 归档到了 `T 未知行业(T)` | `manager/organize/organizer.py::_organize_word_item` |
| 6 | 通知 Telegram 429 | `core/notification/channels/telegram.py` |
| 7 | Win 一键没归档 | `ui/workers/auto.py::AutoWorker` / `_auto.py::auto_run_stream` |

评分：每题 1 分，说出文件/函数即可；能补充“为什么”加 0.5。

---

## 四、C. 题库（含答案）

> 先让新人答，再对照。答案不要求逐字，意思对即可。

### 1. 一句话介绍 PilotStd

**答**：企业标准文件的“收货—验真—补货—上架—保质期管理”系统；围绕标准号做解析、查询、下载、归档、有效性跟踪。

### 2. 它“不是什么”？至少 3 个

**答**：不是通用文档管理；不是纯下载器；不是三端同一套 UI；不是“点一下所有事都自动完成”；不是“查到废止就自动搬”。

### 3. 一条文件从 Inbox 到归档的 7 站

**答**：发现 → 扫描解析 → 查询/分类 → 下载（可选）→ 归档 → 收容/清理 → 通知/后续时效检查。

### 4. `effect_status` 从哪来？归档读 `standard_validity` 吗？

**答**：来自 Query 的 `QueryResult.status`，由 `QueryClassifier._write_back_results()` 写回；归档不读 `standard_validity`，只 `register_new_standard()` 写“未知”。

### 5. `standard_validity` 的角色

**答**：历史跟踪/待复检表；定时/手动检查更新；不是归档第一权威。归档目录以 Query 的 `effect_status` 为准。

### 6. 三张核心表分别回答什么

**答**：

- `file_index`：文件在哪、属于哪个标准、状态；
- `standards`：内容身份（sha256/code/name/size）；
- `standard_validity`：历史有效性、下次检查时间。

### 7. Web 五段式与 Win 一键的差异

**答**：Web 是 scan→query→download→normalize→archive 五个 API；生产当前下载 `saved_path` 不回灌归档，本地代码已修待部署。Win 一键是 `AutoWorker → auto_run_stream`，下载后同批归档，闭环。

### 8. Docker monitor 与 Win watcher 的差异

**答**：Docker `_on_file` 会 scan+archive；Win `FileWatcher` 只更新 `file_index`，不归档；`watchdog.enabled` 默认 false。

### 9. 规范化会不会移动文件？归档用不用 `new_filename`？

**答**：不会移动；`normalize_files_stream()` 只算预览；Web 归档接口不使用 `new_filename`，`FileMover` 重新计算。

### 10. 下载任务重启后会恢复吗？

**答**：手动/一键下载任务在内存，不恢复；只有 `favorite_downloads` 收藏链有持久化状态机；`task_queue` 有表但没有真实下载 handler。

### 11. 为什么 TSG Word 会进 `T 未知行业(T)`？

**答**：`OrganizerCore._std_parser` 用空 scan.code_mapping；`_exact_match_group()` 把 `TSG` 匹配成 `T/SG`；`get_folder_name("T/SG")` 取 base `T` → `T 未知行业(T)`。PDF 走扫描器解析器，通常进 `TSG`。

### 12. 为什么 `standard_validity` 会与 `file_index` 不一致？

**答**：归档只写“未知”，Query 状态不回写；定时检查才更新表；`/api/stats` 看 `file_index`，导出/历史看 `standard_validity`；畸形键也会导致匹配失败。

### 13. 文件没归档，排查顺序

**答**：看 `/inbox` 是否还有文件 → 看 `解析失败`/`未识别` 日志 → 看 `file_index` 是否写入 → 看目标是否已存在 → 看监控是否启动 → 看 `file_index`/DB 错误。

### 14. 通知没收到，先看什么？

**答**：`notification_log` 的 `status/error_msg` → 渠道配置/启用 → 静音时段 → 聚合窗口 → Telegram/企微错误码。

### 15. 为什么不能手工改版本号/用本地 tag 判断部署版本？

**答**：版本由 CI `version` 作业按 commit message 生成并打 tag；镜像由 bump 后提交构建，sha 与 tag 可能不一致；部署版本以 `/api/health` 的 `version` 为准。

### 16. 生产环境红线是什么？

**答**：禁止直接修改容器内代码、直接 UPDATE 生产数据库、为测试重启生产服务；所有修复先在开发/验证环境确认。

### 17. 改 `web/` 要跑哪四条？

**答**：`type-check`、`lint`、`test`、`build`（`pnpm` 或 `pnpm.cmd`）。

### 18. 哪些改动需要 `generate_capabilities.py`？

**答**：新增/修改/删除 ADR；修改 `pilotstd/core/`、`docker/api/`；修改 `docs/` 治理文档。提交前生成并纳入同一 commit。

### 19. 说 3 个当前已知边界

**答**（任选 3）：

- 生产当前 Web 下载不回灌归档（本地已修待部署）；
- Docker monitor 只 scan+archive；
- Win watcher 只索引；
- 手动下载不持久化；
- 规范化只预览；
- `standard_validity` 是跟踪表；
- Word 重解析空 mapping；
- 通知聚合/渠道限流；
- DB SELECT+INSERT 竞争。

### 20. 如果让你修“Web 下载件不归档”，第一步做什么？

**答**：先复现/确认边界（下载件落在哪、archive 入参是什么）；再查 `TaskView` 与 `/api/archive`；出方案（如何把 `saved_path` 转成 `ParsedStdInfo`、如何处理重复/覆盖）；写失败测试；再改代码；最后前端四件套 + 后端测试。本轮已实现前端 `archiveItems` 合并，测试见 `TaskView.test.ts`。

---

## 五、D. 小任务（任选 1）

| 任务 | 要求 | 评分点 |
|---|---|---|
| **D1. 补一个解析测试** | 为一种真实文件名格式加测试，先失败后通过 | 测试有效、命名清晰、断言具体 |
| **D2. 补一条可观测日志** | 在失败分支加日志，含路径/标准号/错误 | 不泄露敏感信息、能定位 |
| **D3. 写一段 onboarding 文档** | 把某个概念讲清（如 `effect_status` vs `standard_validity`） | 准确、有代码引用、无臆测 |
| **D4. 修一个文档错误** | 找 README/架构文档与代码不一致处，提交修正 | 有证据、范围最小 |

要求：

- 先说明方案；
- 不顺手改无关代码；
- 跑相关测试；
- 提交信息符合 Conventional Commits。

---

## 六、常见“危险信号”

如果新人出现以下回答，需要补学：

- “三端是一套 UI” → 重读 [`03-architecture.md`](03-architecture.md)；
- “归档会读 `standard_validity`” → 重读 [`02-file-journey.md`](02-file-journey.md)、[`04-data-model.md`](04-data-model.md)；
- “规范化会移动文件” → 重读 [`08-known-boundaries.md`](08-known-boundaries.md)；
- “监控和 watcher 一样” → 重读 [`03-architecture.md`](03-architecture.md)；
- “下载任务重启会恢复” → 重读 [`08-known-boundaries.md`](08-known-boundaries.md)；
- “查到废止就自动搬” → 重读 [`02-file-journey.md`](02-file-journey.md)；
- “生产可以直接 UPDATE 修数据” → 立即纠正，重读 [`07-dev-workflow.md`](07-dev-workflow.md)。

---

## 七、通过后的下一步

建议给新人一个 **30/60/90 天** 路径：

| 时间 | 目标 |
|---|---|
| 第 1 周 | 跑通 Lab、能讲一条文件旅程 |
| 第 1 月 | 独立改一个小功能 + 跑对应测试 |
| 第 2 月 | 独立排查一个线上/验证环境问题 |
| 第 3 月 | 能评审一个跨模块改动（解析/归档/通知/Web） |
