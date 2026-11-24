# 全站技术债与隐患总清单（2026-11-23 全量扫描）

> 扫描范围：`docs/debt/` 全部台账（00/02/03/04/05 + technical-debt.md 主档）+ 全库代码 TODO/FIXME/HACK/XXX/TEMP 与中文债务词 + 八类深度隐患排查
> 扫描基准：`main` @ `93219881`（2026-11-23 19:37:49 +0800）
> 扫描方式：Python 脚本批量扫描（AST + 正则 + 门禁实跑），写 `%TEMP%/debt_scan/`；关键隐患逐条读源码确认
> 统计：共 **118 项**（P0 × 25 / P1 × 15 / P2 × 66 / 已接受 × 12），另附 **11 项已核实无需处理**（防重复排查）
>
> **本文件只做扫描与分类，未改任何源码。**

---

## 统计总览

| 类别 | 数量 | 其中 P0 | P1 | P2 |
|---|---:|---:|---:|---:|
| 债务台账（A/V/T/DT/G/W） | 60 | 25 | 8 | 27 |
| 无主 TODO/FIXME | 3 | 0 | 0 | 3 |
| 异常静默 | 8 | 0 | 1 | 7 |
| 性能隐患 | 12 | 0 | 3 | 9 |
| 文档漂移 | 10 | 0 | 1 | 9 |
| 资源泄漏 | 6 | 0 | 0 | 6 |
| 安全健壮性 | 3 | 0 | 2 | 1 |
| 测试缺口 | 4 | 0 | 0 | 4 |
| **合计（不含已接受）** | **106** | **25** | **15** | **66** |
| 已接受不做（单列，不计入 P 级） | 12 | — | — | — |

**门禁现状实测（2026-11-23，全部 EXIT=0）**：

| 门禁 | 结果 |
|---|---|
| `check_g_050_silent_errors.py` | PASS（pass=46 / return=46 / debug=66，基线 46/47/69，3 条可收紧） |
| `check_docs_drift.py` | PASS（路由 133 / 表 43 / 配置键 133 / 事件 44，违规 0） |
| `check_g_032_doc_health.py` | 通过（3 warning：STATUS.md 缺失 ×2、`docs/architecture/architecture.md` 不存在） |
| `check_design_tokens.py` | PASS（36 条 `[STALE]` 待人工收敛基线） |
| `check_g_010_code_size.py` | PASS（阻断档 0；**警告档 20 个文件 >400**） |
| `check_g_012_comment_density.py` | PASS（阻断 0；**`[LANG]` 警告 27 条**） |
| `check_g_030/031/034`、`check_property_proxy`、`check_signal_connect` | 全部 EXIT=0（05-audit 记的「零调用且必 FAIL」已修） |
| `check_i18n_hardcoded.py` / `_python.py` / `check_terminology.py` | PASS（基线内；python 侧 10 文件存量已低于基线） |

---

## 一、P0（必须立刻修：数据损坏/安全/生产阻断）

| # | 编号 | 类别 | 位置 | 问题 | 影响 | 修法 |
|---|---|---|---|---|---|---|
| 1 | G-14 | 台账·数据 | `pilotstd/core/config/manager.py` | 配置多实例整文件覆盖写（`save()` 写整份快照，长任务收尾覆盖他方键）→ IP 失败重复通知根因。**代码已修（`update()/update_many()`），状态=已修复（待部署）** | 生产上仍会丢配置键；长任务与前台并发时静默回滚他人写入 | 随下一版本部署 + 生产复验「并发写后键不丢」 |
| 2 | G-15 | 台账·UI | `web/src/style.css`（三处 CSS） | 深色主题按钮文字对比度不足（outlined danger 1.36:1、悬浮工作台 2.98:1、侧栏收起 4.04:1，共 32 处）。**已修待部署** | 生产用户看不清按钮文字，无障碍不达标 | 部署 + Playwright 复扫 107 按钮 0 个低于 AA |
| 3 | G-17 | 台账·数据 | `pilotstd/monitor/`（`remove_dir_if_empty`） | Inbox 空目录自动清理「假生效」：只含 Thumbs.db 清不掉、只清一层、`start==watch_root` 直接 return。**已修待部署** | 生产上 Inbox 目录无限堆积，磁盘压力 | 部署 + 生产跑一次清理核对目录数 |
| 4 | G-18 | 台账·功能 | 公告抓取前端 + 后端默认值 | 抓取起始日期默认「今天」导致漏抓历史公告。**已修待部署**（改「最近 7 天」+ 可清空） | 生产上每次抓取漏掉 7 天以前公告 | 部署 + 生产抓一次核对条数 |
| 5 | G-19 | 台账·数据 | `docker/api/organize.py:84`（`/api/clean-empty`，`remove_dir_if_empty`） | `/api/clean-empty` 与空目录清理不同口径，垃圾文件目录漏清。**已修待部署** | 与 G-17 同源，生产磁盘占用不降 | 与 G-17 同批部署 |
| 6 | G-20 | 台账·UI | `web/src/config/themes.ts`、`style.css` | 四主题配色不统一（`--primary` 兼任文字色与按钮底色）。**已修待部署**（拆 `--primary-fill`） | 四主题下对比度不一致，部分组合不达标 | 部署 + `theme-spec.test.ts` 30 例绿 |
| 7 | G-21 | 台账·功能 | `docker/api/announce.py`（分页） | 公告列表固定 `LIMIT 100`，历史公告「看不到」被误判为没抓到。**已修待部署** | 生产上 GB 2022 年 2850 行只显示 100 条 | 部署 + 生产按 `total` 核对分页 |
| 8 | G-22 | 台账·可观测 | `docker/api/system.py`（`/api/system/archive-stats`） | 归档是否真落盘无法核对（`/api/files` 看不到 data 目录）。**已修待部署** | 归档静默失败无人发现 | 部署 + 调接口核对 HTML/附件数量 |
| 9 | G-23 | 台账·功能 | `web/src/views/settings/`（localeOptions） | 设置页「界面语言」下拉消失（界面 Tab 整块不渲染，`localeOptions` 未取 `.value` 致 PrimeVue Select 崩溃）。**已修待部署** | 生产用户无法切换界面语言 | 部署 + dev 实测下拉存在 |
| 10 | G-29 | 台账·功能 | `docker/api/notification_menu.py` | A-27 菜单无配置写入口（只能手改 config.json）。**已修待部署** | 生产上菜单配置无法通过 UI 落地 | 部署 + 调 `PUT /api/notification/menu/config` |
| 11 | G-34 | 台账·解析 | `pilotstd/announcement/`（NFKC 归一化） | 补抓 7 条失败中的修改单解析（全角 `／`/`－`）。**已修待部署** | 生产上全角写法的公告正文解析为空 | 部署 + 重跑那 7 条 |
| 12 | G-36 | 台账·可观测 | `docker/api/system.py`（`/api/system/quarantine-stats`） | 隔离区文件数无法从外部核对（G-05 重验缺口）。**已修待部署** | 隔离区增长不可见 | 部署 + 调接口核对 |
| 13 | G-37 | 台账·功能 | `pilotstd/core/notification/menu/clients.py` | A-27 飞书群 `chat_id` 无发现入口。**已修待部署** | 飞书菜单配置无法落地 | 部署 + 调 `GET /api/notification/menu/chats` |
| 14 | G-38 | 台账·数据 | `pilotstd/core/_validity_pipeline.py` | U-1 旧状态恒空（`last_status` 从未初始化）。**已修待部署** | 生产上「旧 → 新」状态永远显示空 | 部署 + 跑一次时效检查核对 `last_status` |
| 15 | G-39 | 台账·通知 | 通知策略表回退 | 28 个事件无出厂渠道，新装用户只收 16/44。**已修待部署** | 新装用户漏收 64% 通知 | 部署 + 新装实例核对渠道数 |
| 16 | G-40 | 台账·通知 | `channels/base.py` + 两张卡片 | `message.link` 四渠道不渲染 + 级别只有飞书/钉钉可见。**已修待部署** | 生产通知里链接点不动、级别看不到 | 部署 + 四渠道各发一条核对 |
| 17 | G-41 | 台账·通知 | `pilotstd/core/notification/channels/`（`do_test_send`） | 企微应用形态测试连接构造参数错位。**已修待部署** | 「测试连接」对企微应用形态永远失败 | 部署 + 企微应用形态点一次测试连接 |
| 18 | G-42 | 台账·数据 | `record_result_metrics()` | 批次 found/not_found 不落表。**已修待部署** | 生产上批次成功率无数据可查 | 部署 + 跑一批核对 `query_metrics` |
| 19 | G-44 | 台账·通知 | `pilotstd/core/notification/_dispatcher.py` | 零渠道用户事件静默丢弃（站内不可见）。**已修待部署** | 未配置渠道的用户完全收不到任何提示 | 部署 + 零渠道账号触发一次事件 |
| 20 | G-46 | 台账·通知 | `ChannelCapabilities` / `channel_capabilities()` | 渠道内容能力（图片/@/按钮）无声明，上层按渠道名写死。**已修待部署** | 新增渠道要改多处、能力误判 | 部署 + 4 例测试绿 |
| 21 | G-47 | 台账·通知 | `MENU_CLIENT_FACTORIES` | 菜单客户端工厂 if/elif 写死。**已修待部署** | 加渠道要改多处 | 部署 + 注册表键断言绿 |
| 22 | G-48 | 台账·数据 | `pilotstd/manager/pending_service.py` + 定时任务 | `mark_missing` 无入口（只能手工跑）。**已修待部署** | pending 的 `file_missing` 永远不自动核销 | 部署 + 等一次 03:30 UTC 定时任务 |
| 23 | G-27 | 台账·数据 | `pilotstd/manager/scheduled_service.py:72-140` | `scan-and-index`：indexed 0 / skipped 825 / failed 0，`file_missing` 仍 33 条；不是窗口问题，需查扫描匹配逻辑。**状态=待做** | 生产上索引永不更新，查询结果指向旧路径 | 复现 → 定位四要素匹配（`sha256/code/name/size`）断在哪一环 |
| 24 | G-28 | 台账·数据 | `superseded_by` 列 | 方向迁移（演练完成，待定规则）：备份 232,668 行、非空 32,432 行；100 条样本仅 33 条可安全交换（67 条目标行已有值，直接写会覆盖）。**状态=待做** | 直接跑迁移会覆盖 67% 目标值 → 数据损坏 | 先定规则（仅空才写/追加/保留较新）再授权 |
| 25 | G-33 | 台账·数据 | `pilotstd/core/db/_migrate_v7x_*.py`（`superseded_by`） | 抽样 4,000 行：方向倒退 **3,695（92%）**；33 个目标行已有值无一条正向。**状态=已查清，待决策** | DB 内 `superseded_by` 92% 指反，所有「被替代」关系失效 | 规则宜「仅写空值 + 先清洗已有乱值」；用 `scripts/migrate_superseded_by_direction.py` 演练 |

> P0 前 22 项的共同点：**代码已修、生产未部署**。它们是同一批动作（一次部署 + 逐项生产复验），不拆成 22 个独立修复任务。

---

## 二、P1（应尽快修：功能缺陷/明显体验问题）

| # | 编号 | 类别 | 位置 | 问题 | 影响 | 修法 |
|---|---|---|---|---|---|---|
| 26 | T-42 | 台账·通知 | `pilotstd/core/notification/channels/base.py:49-59` | 渠道限流**具体错误码未逐家取证**（钉钉官方文档 JS 渲染取不到正文），现用 `_RATE_LIMIT_HINTS` 关键词兜底 | 站点改文案后限流识别失效 → 当场丢通知 | 取到任一家的 `errcode`/`code` 后改按码判定 |
| 27 | A-40 | 台账·数据 | `notification_log`（v71 前存量） | 残余 **89 行**（2026-10-31~11-14）`user_id=1` 待决；已订正 452+67 行 | 多用户下这些通知归错用户 | 先确认 89 行是否含真实用户动作，再按「系统→0 / 用户动作→1」清零 |
| 28 | A-44 | 台账·功能 | `pilotstd/monitor/scheduler.py`（watchdog） | monitor 实时路径：新目录不触发（旧目录正常）；Windows bind mount 下目录创建事件未送达 | 新目录投放必须 restart 补扫，实时性残缺 | ① 补子目录 watch 巡检 ② 评估 `PollingObserver` ③ 文档写明（现按 ③） |
| 29 | A-45 | 台账·通知 | 通知渠道系统 | 无 dry-run/站内渠道：`test-event` 会真实外发，AC-6 触发链路无法在生产安全复验（`dry_run` 已修，站内渠道仍缺） | 生产复验要冒真实外发风险 | 新增站内渠道（需产品决策），不阻塞现有验收 |
| 30 | G-03 | 台账·可观测 | 健康检查探针 | 11 站 `probe_pending`；已随 v0.196.1 部署，**待生产复跑** | 11 个站点的健康状态不可见 | 生产复跑 `/api/adapters/health/run`，确认 pending 是否收敛 |
| 31 | G-25 | 台账·可观测 | 同上 | 探针自动发现**已执行未改善**（found 6 / no_result 4 / error 0 / probe_pending 11）；根因已转 G-26（适配器从未返回结果） | 探针覆盖率停在 60% | 随 G-27 一起看（同属「查询链没结果」） |
| 32 | G-35 | 台账·数据 | `scripts/migrate_superseded_by_direction.py` | 迁移脚本已就绪（默认演练、`--apply` 前建备份、两阶段写入、回滚覆盖），**待授权全量** | 与 G-28/G-33 同源，不授权则数据一直错 | 规则定了之后 `--apply`，先 33 条试点再全量 |
| 33 | G-43 | 台账·可观测 | `notification_log` | 通知日志 info/warning 计数口径是否偏差，**待核实（缺两时点分布）**；上批「新增 2 条 info」解释自相矛盾 | 计数口径不可信则所有通知统计失真 | 取生产两时点 `event_type × level` 分布定论（SQL 见 `27` #105） |
| 34 | NEW-01 | 异常静默 | `scripts/check_g_050_silent_errors.py:106-118` | **门禁盲区**：`_handler_kinds()` 只认「单语句 `pass`」与「单语句空 `return`」，**不认 `except: continue` / `except: break`**。实测扫描范围内有 **29 处**（27 continue + 2 break）这类「失败即跳过」的吞错，全部不受棘轮保护 | 新增 `except Exception: continue` 永远不会被拦；比 `pass` 更隐蔽（看起来像正常控制流） | 给 `_handler_kinds` 加 `continue`/`break` 两档（口径同 `pass`），跑 `--emit` 生成基线后冻结存量 |
| 35 | NEW-02 | 健壮性 | `pilotstd/core/db/database.py:75-84` | `_acquire_migration_lock()` 的 `except OSError: continue` **跳过超时判断直接回到 `while True`** ⇒ 锁文件不可读（权限/占用）时**死循环**，永不返回 `False` | 数据库迁移卡死且无日志、无超时；容器启动挂起 | `except OSError` 分支也应走 `time.time() - start > timeout` 判定；顺带 `time.sleep(0.5)` 提到分支外 |
| 36 | NEW-03 | 性能 | `docker/api/system.py:262` → `:156-166` | `async def update_container()` 里调**同步阻塞** `subprocess.run(timeout=300)`（`docker pull` 最长 300s）+ `_restart_via_compose` 120s，**直接阻塞事件循环** | 一次「检查更新」期间整个 API 服务无响应（含 `/api/health`） | 改 `await asyncio.create_subprocess_exec(...)` 或 `run_in_executor`；至少把 `pull` 移出事件循环 |
| 37 | NEW-04 | 性能 | `pilotstd/manager/pending_service.py:87-120` | `record_pending()` **N+1**：每条先 `SELECT id FROM pending_lookup WHERE standard_number=?` 再 `INSERT`；批量 200 条 = 400 次往返 | 大批次入库明显变慢（与 `matcher.py` 已做批量写入的路径不一致） | 改 `INSERT OR IGNORE` + 唯一索引（`standard_number,status`），一次 `executemany` |
| 38 | NEW-05 | 性能 | `pilotstd/core/file_index.py:143-172` | `validate_paths()` **全表 `SELECT id, file_path` 无 LIMIT**，再逐行 `os.path.exists()`（网络盘上单次 stat 可达毫秒级）；1 万条 = 1 万次 stat | 启动校验线程长时间占 IO；大盘上分钟级 | 分批 `LIMIT/OFFSET` 或按 `last_checked` 游标增量；`os.scandir` 按目录批量判定 |
| 39 | NEW-06 | 安全 | `docker/api/upload.py:20,45-52,93-102` | 允许上传 **SVG**（仅校验「以 `<svg`/`<?xml` 开头」），且 `/api/backgrounds/{filename}` 以**同源** `FileResponse` 返回（无 `Content-Disposition: attachment`）。CSP 里 `script-src 'self' 'unsafe-eval'` | 管理员上传恶意 SVG → 同源直接打开可执行脚本（存储型 XSS，可窃取 admin 会话） | ① 去掉 `.svg`；或 ② SVG 强制 `Content-Disposition: attachment` + 单独 `Content-Security-Policy: sandbox`；③ 上传后 `X-Content-Type-Options` 已有，需补 `Content-Type: image/svg+xml` 的显式下载头 |
| 40 | NEW-07 | 文档漂移 | `docs/debt/03-open.md` ↔ `docs/debt/00-global-issues.md` | **同一编号两处状态互斥（5 项）**：A-43（open「未修」/ global「已闭合」）、A-44（open「观察中」/ global「已闭合」）、A-45（open「定触发」/ global「已闭合(dry-run)」）、A-40（open「部分已订正·残余待决」/ global「已闭合(部分记录)」）、T-42（open「基座已具备·残留」/ global「已闭合」） | 读者按任一文件判断「还剩多少」都会得到相反结论；下一个人会重复修已修项或漏修 | 以 00-global 为准回写 03-open 状态列；建立「两处状态必须一致」的机械校验（可挂 G-030 增量检查） |

---

## 三、P2（可排期修：代码质量/可维护性）

### 3.1 债务台账（P2 部分，27 项）

| # | 编号 | 类别 | 位置 | 问题 | 影响 | 修法 |
|---|---|---|---|---|---|---|
| 41 | T-40 | 台账·通知 | `data/config.json` `notification.channels.wechat` | V6 wechat 真发未取证（`webhook_url` 为空，非部署环境无法真发）；用户 2026-10-17 裁定「后续再说」 | 企微真发能力无生产证据 | 部署环境补一次真发取证（会真发一条） |
| 42 | T-43 | 台账·通知 | `docker/api/notification_callback.py` | 企微回调取证，已并入 A-27；需一条真实菜单点击报文校准 `EventKey/FromUserName/AgentID` | 菜单点击回调参数未校准 | 随 A-27 真实联调 |
| 43 | A-5 | 台账·测试 | `pilotstd/templates/adapter/` | cookiecutter 真实 CLI 端到端未入 CI（渲染/编译/零字面量已由 jinja2 用例覆盖） | hooks 改动无端到端保护 | hooks 变更时补一条真实 CLI 用例 |
| 44 | A-22 | 台账·UI | Windows 端托盘 | Q7：15 个共享事件是否走托盘（S4 真实验收）需 Windows 实跑 | 托盘通知路径无验收 | 用户 Windows 本机跑一次（约 5 分钟） |
| 45 | A-27 | 台账·功能 | `pilotstd/core/notification/menu/` | 自定义菜单（企微/飞书/Telegram/钉钉）代码已落地 `8dc5393a`，**剩余各平台后台权限下的真实联调** | 真实 API 未验证 | 各平台后台联调一次 |
| 46 | A-27.1 | 台账·通知 | 同上 | 真实渠道 API 验证（企微 `corpid/corpsecret/agentid`；飞书 `app_id/secret`+`chat_id`；TG bot token）**阻塞部署验证** | 无法确认菜单在生产可用 | 凭证到位后逐家联调 |
| 47 | A-27.2 | 台账·UI | 前端设置页 | 菜单配置前端 UI 未做（现走 config + admin API） | 配置门槛高 | 不阻塞发布；排期做设置页 |
| 48 | A-32 | 台账·工具 | `pilotstd/templates/adapter/hooks/post_gen_project.py` | cookiecutter 把 `myadapter.py` 判为二进制，现用 `_CONTEXT` + Jinja2 手动渲染**绕开**；不覆盖 `{% if %}` 控制块、可能误判合法 `{{` | 扩展其它文件时会静默跳过 | 升级 cookiecutter 时修，修后删该步 |
| 49 | A-42 | 台账·通知 | `docker/api/auto.py`、`docker/api/archive.py` | 两端点有 `@require_role("admin")` 但调 manager 时未传 `NotificationContext(user_id=...)` ⇒ 事件归 system(0) | 多用户下用户看不到自己触发的通知 | 调用点传 `get_current_user_id()`；随多用户主线 P1 |
| 50 | A-43 | 台账·文档 | `docs/onboarding/18-schema-migrations.md` | 「SQLite 实测业务表 45 张」来自实跑 `sqlite_master`；`load_facts()` 只解析源码得 43 ⇒ **无法机械核对**（G-052 列为「已登记但不可核对」） | 43/45 不一致会反复被质疑 | 二选一：① 新增「空库跑迁移后数表」事实源 ② 改「以实测为准」不写具体值 |
| 51 | A-46 | 台账·数据 | `pending_lookup`（33 条 `file_missing`） | 33 个隔离文件丢失（含 `HJ 536-2009`）：误移到未挂载 `/data`，v0.191.1 重启丢失 | 33 条 pending 永久挂着 | 重取后归档并核销；在此之前保持 `file_missing` 不伪装关闭 |
| 52 | A-52 | 台账·UI | `web/src/**`（27 文件） | **B 类无令牌硬编码总账**：基线实测 B=155 / C=621（`scripts/design_token_baseline.json`）；116 处带 `TODO: [Design Debt]` 注释（有主） | 令牌体系不完整，主题切换/视觉一致性受限 | 按类补语义令牌（先过四主题对比度）再批量替换，每类单独提交并收敛基线 |
| 53 | V-2 | 台账·测试 | `web/`（vitest） | 本地 `vitest run` 偶发「全绿但 exit=1」（2026-10-16 复跑 42 files/324 passed/exit=0，仍未复现） | CI 假红/假绿风险 | 再出现时存全量输出定位 |
| 54 | V-3 | 台账·数据 | `pilotstd/core/config/manager.py` | 配置文件跨进程写锁（**已决定不引入文件锁**）；现靠 `update()` 收口（G-14） | 同毫秒并发写仍可能丢键 | 实测到一次并发丢配置即改「原子写+重试+写后校验」或 SQLite 配置后端 |
| 55 | V-6 | 台账·CI | `.github/workflows/ci.yml` | 自动 `chore: bump version` 提交不触发 CI | 版本号/CHANGELOG 不一致事故无自动拦截 | 出现一次事故即查；兜底是 G-009（`ci.yml:205`） |
| 56 | V-7 | 台账·CI | `.github/workflows/*.yml` | `ubuntu-latest → Ubuntu 26` 预告；2026-10-16 实测 `warning=0 / notice=9` | 未来 runner 升级可能破构建 | 2026-10-19 起验证；可用 `ubuntu-24.04` 钉住 |
| 57 | V-8 | 台账·代码规模 | `web/src/views/TaskView.vue` | 逼近 G-010 警告线——**记录值 399 已过期，实测 475 有效行**（见 NEW-08） | 与 500 阻断线只差 25 行，随时可能阻断 CI | 拆分（历史列表/详情面板已部分外移，继续拆 run 编排段） |
| 58 | V-9 | 台账·代码规模 | `pilotstd/core/notification/event_spec_data.py` | 1b 拆分豁免——**记录值 417 已过期，实测 457**（见 NEW-09） | 距 500 阻断线 43 行 | ① 破 500 阻断档 ② 新增变动频繁业务族时拆 |
| 59 | V-10 | 台账·前端 | `web/src/views/HomeView.vue:18` | `grid-layout-plus` workaround（`layout.value = [...layout.value]` 克隆） | 升级依赖后可能白改 | 升级 `grid-layout-plus`（`web/package.json:23`）后浏览器实测锁定/解锁拖拽 |
| 60 | V-11 | 台账·i18n | `scripts/check_terminology.py` | G-044 术语覆盖缺口：三语严格相等仅覆盖登记键 **40/346**，其余 340 键「改简体忘改繁体不会被拦」 | i18n 翻译漂移无门禁 | ① 通知文案新增/变更批次 ② 术语表扩容专项 |
| 61 | V-13 | 台账·工具链 | `docs/archive/pre-commit-config.archived.yaml` | 工具链版本漂移：本地 `ruff 0.15.17` vs 归档配置钉的 `v0.11.6`（该钉版**不再被执行**，仅存档） | 按它重排会产生大量无意义 diff | 不要按它重排；现行口径是 CI `ruff check`（G-038） |
| 62 | V-14 | 台账·类型 | `pilotstd/download/session.py:38` | L1 mypy `--follow-imports=skip` 下 `[override]` 不报（2026-10-16 实测 442 文件 0 error） | 改 mypy 默认口径会冒出错误 | 若将来改 `follow-imports` 时处理 |
| 63 | V-16 | 台账·测试 | `web/src/components/TaskManager.vue` | 分支覆盖仅 **27.9%**（行 51.85%），失败/重试分支无测试（与 NEW-10 的 4 处 `catch { /* ignore */ }` 同源） | 失败路径改动无回归保护 | 下次功能变更时补失败分支用例；分支回 ≥60% 摘除 |
| 64 | V-17 | 台账·门禁 | `scripts/check_g_012_comment_density.py` | G-012 注释密度对**新建脚本**反复红，被迫补低价值注释（2026-11-14 两次：0.9%、2.0%）；实测当前 `[LANG]` 警告 **27 条** | 门禁逼人造注释，反而降低质量 | ① 新文件过渡期 ② 改按「公共函数是否有 docstring」判定 |
| 65 | V-18 | 台账·可观测 | `pilotstd/query/engine/_metrics.py` | `query_metrics` 无法区分 `chain_exhausted` 原因：冷却/配额/无结果三类计数器 0 时不落库，只剩 `chain_exhausted` 总数 | 归因只能靠日志 | 修 P3-16 时一起改：分别落 `quota_exhausted`/`no_result` 键 |
| 66 | V-19 | 台账·UI | `scripts/check_design_tokens.py`（C 组映射） | G-055 `no-literal` **177 条口径收紧风险**：`0/auto/none/transparent` 现按策略排除并计入基线；若收紧会一次性产生大量 `[STALE]` 噪音 | 口径变更会掩盖真实清理 | 触发时先 `--suggest-baseline` 重生成 + 人工评审，**不得脚本自动改** |
| 67 | V-20 | 台账·UI | `web/src/styles/` | overlay 半透明底 4 档标度（`--overlay-weak/soft/strong/solid`）：实测 196 处、20 个 alpha 取值，集中 ≈0.06/0.12/0.30/0.85 | 统一会产生**可见视觉变化** | 需产品确认后才做；评估见 `docs/analysis/2026-11-21-v19-assessment.md` §三 |

### 3.2 无主 TODO/FIXME（3 项）

> 全库代码扫描（排除 `node_modules/.venv/__pycache__/dist/.git` 等）命中 **1166** 处英文标记 + 中文债务词，逐条甄别后**真正无主且可动作的只有 3 处**。
> 其余均为假阳性（工具自身的关键字表、`T/XXX` 标准号、`TEMP TABLE`、`%TEMP%` 目录、测试数据）或**有主**（116 处 `TODO: [Design Debt]` 归 A-52）。

| # | 编号 | 类别 | 位置 | 问题 | 影响 | 修法 |
|---|---|---|---|---|---|---|
| 68 | NEW-08 | 无主 TODO | `.github/workflows/ci.yml:864` | `# TODO(P2): restore to 68 after UI handler tests are added`——整体覆盖率门槛从 68 降到 58 的临时值，**无债号、无到期日** | 58 这个数字会永久留在 CI 里（已存在 2 个多月），覆盖率缓慢劣化 | 补 UI handler 测试后恢复 68；或在 `docs/governance/gates.md` 正式登记为 G-034 的子项 |
| 69 | NEW-09 | 无主 TODO | `web/src/views/HomeView.vue:18` | `// TODO(前置条件): grid-layout-plus 升级到 > 1.1.1（当前 ^1.1.1）后重新评估是否仍需此 workaround`——写了前置条件但**未挂 V-10**（V-10 在 04-watch 里另记一份） | 两处记录会各自漂移 | 与 V-10 合并为一条（把 `HomeView.vue:18` 的 TODO 改成 `TODO(V-10)`） |
| 70 | NEW-10 | 无主 TODO | `web/src/styles/design-tokens.css:11` | `本轮不做视觉收敛。8pt 收敛与语义化收敛记入 docs/design-token-audit.md 的 TODO 清单`——指向的清单本身也在 TODO 状态，**闭环条件未定义** | 8pt 栅格收敛永久悬空 | 挂到 A-52 子项，或写明「不做的理由 + 重评触发」后删掉该 TODO |

### 3.3 异常静默（P2 部分，7 项）

| # | 编号 | 类别 | 位置 | 问题 | 影响 | 修法 |
|---|---|---|---|---|---|---|
| 71 | NEW-11 | 异常静默 | `pilotstd/announcement/_attachment_parser.py:32-40` | `for parser in (...): try: ... except Exception: continue`——**三种解析器全失败也不留痕**，只在末尾打「无法解析附件：未知格式」，看不到每个解析器各自的异常 | 附件正文为空时无法定位是哪个解析器、什么错 | `except Exception as e: logger.debug("parser %s failed: %s", parser.__name__, e)` |
| 72 | NEW-12 | 异常静默 | `pilotstd/query/adapters/energy.py:109-114` | `except Exception: continue`——fallback URL 轮询时**吞掉所有异常**（含 DNS/TLS/编码），最终只报「第 1 页请求失败（含 fallback，status=None）」 | 站点不可达与代码 bug 无法区分 | 记录 `type(e).__name__` + 最后一次异常；或复用 `safe_request`（已有 `_warn` 机制） |
| 73 | NEW-13 | 异常静默 | `pilotstd/query/adapters/jjg.py:91-94`、`energy.py:131-134` | `except Exception: break` / `except ValueError: break`——JSON 解析失败直接结束整批查询，**无日志** | 站点返回 HTML 错误页时静默返回 0 结果，看起来像「没查到」 | 至少 `logger.warning("... resp.json() 失败: %s", e)`；区分「无结果」与「解析失败」 |
| 74 | NEW-14 | 异常静默 | `main.py:19-23`、`:39-45`、`:57-63` | 三处 `except Exception: pass`——① `faulthandler.enable` 失败 ② 崩溃日志写盘失败 ③ 线程崩溃日志写盘失败 | 崩溃日志本身写不进去时**没有任何提示**，排查无现场 | ②③ 改成 `print(..., file=sys.stderr)`（此时 logging 可能也不可用） |
| 75 | NEW-15 | 异常静默 | `docker/scheduler.py:133-139` | 备份清理 `except FileNotFoundError: continue` / `except OSError: continue`——**删除失败的旧备份不留痕** | 备份目录只增不减会撑满磁盘（与 P2-10 批 1 升 warning 的 `:118` 同类，但这两个分支漏了） | 合并为 `except OSError as e: logger.warning("删除旧备份失败: %s", e)` |
| 76 | NEW-16 | 异常静默 | `web/src/components/FileMonitor.vue:75,82,92,111,117`、`CacheManager.vue:35,42,52`、`TaskManager.vue:64,91,95,118` | 前端 **54 处** `catch { /* ignore */ }` 或 `catch { console.warn(...) }`（实测注释-only **48 处** + console-only **6 处**）；其中 **12 处集中在 3 个组件**，且 `TaskManager` 的失败分支正是 V-16 覆盖率 27.9% 的部分 | 用户点「启动监控」「清理缓存」「重试任务」失败时**界面无任何反馈**，看起来像成功 | 优先修这 3 个组件：失败时 `useAppToast().error(...)`；其余按「用户主动操作」优先排序 |
| 77 | NEW-17 | 异常静默 | `web/src/stores/app.ts:83-87` | `window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', ...)` **注册后从不移除**（模块级 store，无 `onUnmounted`） | HMR/重复挂载会累积监听器；与仓库其余 16 个文件的「成对注册/注销」口径不一致 | 保留 mediaQueryList 引用并导出 `dispose()`，或在 `App.vue` `onUnmounted` 里移除 |

### 3.4 性能隐患（P2 部分，9 项）

| # | 编号 | 类别 | 位置 | 问题 | 影响 | 修法 |
|---|---|---|---|---|---|---|
| 78 | NEW-18 | 性能 | `pilotstd/announcement/matcher.py:82-87` | `for anno in announce_nos: self._db.execute("UPDATE announcements ...")`——**逐条 UPDATE**（同一函数上方 `_bulk_insert_records` 已做批量，这里没跟上） | 一次入库 N 个公告 = N 次写事务 | `executemany` 或 `WHERE announce_no IN (...)` 一条 UPDATE |
| 79 | NEW-19 | 性能 | `pilotstd/query/daily_quota.py:63-74` | `_ensure_today_rows()` 对每个站点 `fetchone` + 条件 `INSERT`；且被 `get_remaining()`（每次查询都调）间接触发 | 每次跨天后的首批查询放大为 2×站点数次往返 | 一条 `INSERT OR IGNORE ... SELECT` 批量补齐 |
| 80 | NEW-20 | 性能 | `pilotstd/tasks/date_reminder.py:101-109` | 对每个 `uid` 单独 `SELECT 1 FROM date_reminder_log` 做去重判定 | 收藏数多时 N 次查询 | 一次 `SELECT user_id ... WHERE record_id=? AND remind_type=?` 拿全量已发集合 |
| 81 | NEW-21 | 性能 | `pilotstd/core/notification/_suppression_queue.py:168-169` | `expire()` 对每条过期行单独 `UPDATE` | 队列积压时（上限 100/次 × 多轮）写放大 | 一条 `UPDATE ... WHERE id IN (...)` |
| 82 | NEW-22 | 性能 | `pilotstd/core/notification/_manager_ops.py:322-332` | `mark_logs_read(ids)` 对每个 id 单独 `UPDATE`（或 `mark_one` 再查一次） | 「全部已读」100 条 = 100 次往返 | 有 `user_id` 时用 `WHERE id IN (...) AND <scope>` 一条搞定，返回 `rowcount` |
| 83 | NEW-23 | 性能 | `pilotstd/manager/scheduled_service.py:76-140` | `scan_and_index` 对每个文件做 `hash_file_content()`（读全文）+ `SELECT ... WHERE sha256=?` + `UPDATE`；**825 个 skipped 文件也全部算了哈希** | 每次扫描 = 全量读盘 + 全量查库，实测 indexed 0 但耗时不低（G-27 现场） | 先按「路径/大小/mtime」快速排除；哈希只在四要素可能命中时算 |
| 84 | NEW-24 | 性能 | `docker/api/upload.py:77-89` | `async def upload_file()` 里 `await file.read()` 后**同步** `open(path,"wb").write(content)`（最大 10MB） | 大图上传时阻塞事件循环 | 改 `await anyio.to_thread.run_sync(...)` 或 `aiofiles` |
| 85 | NEW-25 | 性能 | `pilotstd/wechat_ip/detector.py:43-54` | `for url, extractor in srcs: requests.get(url, timeout=TIMEOUT)`——**串行**请求多个检测源，全部失败才返回 `None` | 最坏 N × TIMEOUT 秒阻塞调用方（IP 检查在定时任务里） | `ThreadPoolExecutor` 并发取 + 取众数；或至少给总预算超时 |
| 86 | NEW-26 | 性能 | `pilotstd/core/_file_index_query.py:43-48`、`pilotstd/manager/adapter_manager.py:76-85`、`pilotstd/manager/pending_service.py:141-145` | **无分页全表读**：`get_all()` 无 `LIMIT`、`get_all_health()` `SELECT * FROM adapter_state` 无 `LIMIT`、`get_pending_items()` 无 `LIMIT` | 表增长后单次请求返回全表（file_index 可达万级） | 加 `limit/offset` 参数（默认 500）；API 层改分页 |

### 3.5 文档漂移（P2 部分，9 项）

| # | 编号 | 类别 | 位置 | 问题 | 影响 | 修法 |
|---|---|---|---|---|---|---|
| 87 | NEW-27 | 文档漂移 | `docs/debt/04-watch.md:27`（V-8 行） | 记「有效行 399 / 线 400」，**实测 475**（G-010 口径），早已越线 | 按此判断「还有余量」是错的 | 更新为 475，并把状态从「逼近」改为「已越警告线」 |
| 88 | NEW-28 | 文档漂移 | `docs/debt/04-watch.md:28`（V-9 行） | 记「417 有效行」，**实测 457** | 同上 | 更新为 457 |
| 89 | NEW-29 | 文档漂移 | `docs/debt/02-accepted.md:16-20`、`:111`（「三、维持现状」与「五 #5」） | 5 个文件行数**全部漂移**：`_settings.py` 371→**434**、`_file_tree_ops.py` 209→**210**、`_export_ops.py` 116→**118**、`_theme_ops.py` 109→**115**、`_file_dialog_ops.py` 39→**40**；另 `AppLayout.vue` 记 420→实测 **367**、`NotificationConfig.vue` 记 438→实测 **297** | 「均 <400 不进警告区」的结论**对 `_settings.py` 已不成立**（434 已进警告区） | 重测后整体刷新；`_settings.py` 的「纯 UI 不拆」决策需重新评估 |
| 90 | NEW-30 | 文档漂移 | `docs/technical-debt.md:156-157`、`:160-162` | 导航表计数**三重过时**：① 「可动作项 3 条」实际 6→5→当前口径 11 项；② 「观察中 13 条」实际 **15 条**（V-2/3/6/7/8/9/10/11/13/14/16/17/18/19/20）；③ 「正式存续债 3 条（T-40/T-42/T-43）」中 T-42/T-43 在 00-global 已标闭合 | 主档导航把读者引向错误的工作量估计 | 每次改台账同批重算这三处；建议加脚本从 03/04 提取编号数做校验 |
| 91 | NEW-31 | 文档漂移 | `docs/migrations/README.md:3` | 头部写「最新迁移：v69 / `CURRENT_SCHEMA_VERSION = 69`」，**实测 `_constants.py:7` = 76**（差 7 个版本） | 按此判断 schema 版本会错；回滚/备份决策依据错 | 改「以 `_constants.py` 为准，不写具体值」（文件内已有该警告，但头部仍写死） |
| 92 | NEW-32 | 文档漂移 | `docs/**`（52 条相对链接 + 95 条反引号路径） | **死链**：52 条相对链接里 **49 条是「仓库根相对」写法错误**（如 `docs/architecture/overview.md:98` 写 `docker/app.py`，从 `docs/architecture/` 解析必死，但文件本身存在）；95 条反引号路径**全部指向已删除/改名文件**（`scripts/check_docs_sync.py`、`pilotstd/core/db.py`、`tests/gui/test_e2e_*.py` 等） | 下一个人按链接跳转必 404；G-032 只 warn 不拦 | ① 49 条改 `../../docker/app.py` 形式（或全改根相对 `/`） ② 95 条逐条改指或标「历史已不可考」 ③ 建议 G-032 对「文件存在但解析错」单独给一类错误 |
| 93 | NEW-33 | 文档漂移 | `docs/architecture/overview.md` | 27 条死链（最大单文件）；且头部写「最后更新 2026-11-07 / schema v76 / 21 查询适配器」——版本号对但链接全漂 | 新人第一份架构文档就点不开 | 与 NEW-32 同批；建议把该文件的模块表改成「目录 + 生成脚本」而非逐文件链接 |
| 94 | NEW-34 | 文档漂移 | `docs/governance/gates.md:703`、`docs/debt/01-archive-closed.md:1668`、`docs/governance/ACCEPTANCE_CASES.md:43` | 三处引用 **`docs/architecture/architecture.md`（文件不存在）**；G-032 实测就报这一条 warning | 门禁自身文档引用死文件 | 改指 `docs/architecture.md`（已存在） |
| 95 | NEW-35 | 文档漂移 | `docs/technical-debt.md:6,162`、`docs/debt/03-open.md:39`（A-52） | design token 计数**三处不一致**：主档写「B=115」、A-52 写「B=150 / C=559」、`design_token_baseline.json` 实测 **B=155 / C=621**、`audit_design_tokens.py --check` 报 **B=148 / C=588** | 四个数字四个来源，无法判断「还剩多少」 | 定唯一事实源（`design_token_baseline.json` 的 `counts`），其余三处改「见基线文件」 |

### 3.6 资源泄漏（6 项）

| # | 编号 | 类别 | 位置 | 问题 | 影响 | 修法 |
|---|---|---|---|---|---|---|
| 96 | NEW-36 | 资源泄漏 | `pilotstd/query/adapters/{ahbz,csres,dbba,hbba,iso_gov,mee,njbz365,std_gov,ttbz}.py`、`pilotstd/download/adapters/{base,openstd_download}.py`、`pilotstd/announcement/base.py` | **13 个文件**创建 `requests.Session()`，全库 `session.close()` **0 处**（实测 `'session.close()' in src` 全为 False） | 连接池与 fd 不释放；长跑进程累积 | 适配器基类加 `close()/__exit__`，或在 `safe_request` 末尾 `session.close()`（仅对「每次新建」的调用点） |
| 97 | NEW-37 | 资源泄漏 | `pilotstd/announcement/base.py:118` | `session = self._http if self._http is not None else requests.Session()`——**每次 `_fetch_list()` 都新建**，方法结束不关闭 | 每抓一个公告源泄漏一个 Session | 提到 `__init__` 复用，或 `finally: session.close()` |
| 98 | NEW-38 | 资源泄漏 | `pilotstd/query/network.py:165,173` | `safe_raw_get` / `safe_raw_post` 每次调用 `requests.Session()` 后**直接 return，不关闭** | 公告附件下载 / OCR 路径高频调用 | 用 `with requests.Session() as s:`（注意调用方是否还持有 resp） |
| 99 | NEW-39 | 资源泄漏 | `pilotstd/ui/main_window/parts/_file_tree_ops.py:45-47` | `self._drive_thread = DriveEnumerator()` + `drives_ready.connect(...)` + `.start()`，**无 `finished.connect(deleteLater)`、无 `wait()`**（全仓仅 6 处 `deleteLater`，不含此处） | 每次树重建泄漏一个 QThread 对象；Qt 侧 C++ 对象生命周期不可控 | `self._drive_thread.finished.connect(self._drive_thread.deleteLater)` |
| 100 | NEW-40 | 资源泄漏 | `pilotstd/ui/workers/_common.py:124-127`、`:129-147` | `LogHandler` 持有 `QTimer` 并 `start()`，但 `close()` **只置 `_closed` / 清 `widget`，不 `stop()` 定时器** | 定时器在 handler 关闭后仍可能触发一次（`_flush` 已防 `_closed`，但对象不释放） | `close()` 里 `self._buf_timer.stop()` |
| 101 | NEW-41 | 资源泄漏 | `pilotstd/core/db/database.py:30-35,258-269` | `_all_conns` 累积所有线程本地连接（`threading.local` 连接在线程结束后**不会自动关闭**），仅 `close_all()` 统一关 | 线程 churn 场景（`_batch_dispatcher`/worker 线程）会累积 SQLite 连接 | 在 `close_all()` 之外提供「线程退出时关闭」；或用 `contextvars`/`weakref` 回收 |

### 3.7 安全健壮性（P2 部分，1 项）

| # | 编号 | 类别 | 位置 | 问题 | 影响 | 修法 |
|---|---|---|---|---|---|---|
| 102 | NEW-42 | 安全 | `docker/middleware.py:24-32` | CSP 含 `script-src 'self' 'unsafe-eval'` 与 `style-src 'self' 'unsafe-inline'`（注释说明是 PrimeVue + Vue 运行时需要）；`X-XSS-Protection` 现代浏览器已废弃 | `unsafe-eval` 让 XSS 从「只能读」升级为「可执行任意代码」 | 生产构建去掉 `unsafe-eval`（Vue 3 生产包不需要）；`style-src` 可用 nonce/hash 收窄；删除 `X-XSS-Protection` |

### 3.8 测试缺口（4 项）

| # | 编号 | 类别 | 位置 | 问题 | 影响 | 修法 |
|---|---|---|---|---|---|---|
| 103 | NEW-43 | 测试缺口 | `pilotstd/**`、`docker/**` | ~~**30 个后端模块**在 `tests/` 里无任何文本引用~~ → **已归零**（实测 446 模块中，除 8 个一次性迁移脚本与 1 个 Jinja 模板外全部有测试引用） | 已解决 | **已闭合**（2026-11-24）：本轮补 9 批共 **176 例**，覆盖 `_builders_common`、`_channel_registry`、`validity_replacement`、`_shared_ssl`、`_text_cleaner`、`_language_detector`、`renderer_links`、`validity_log`、`notification_deps`、`announce_lookup`、`_topic_index`、`_announce_detail_*`、`_builders_system_security`、`_profiles`、`_core_adapters`、`protocols`、`group_std_orgs`、`diagnose_announce`、`_table_io` |
| 104 | NEW-44 | 测试缺口 | `web/src/**` | **84 个前端源文件**无同名测试（133 源 / 62 测试）→ 已补 3 个（**api/http.ts** 8 例、**composables/useNotificationLogs.ts** 20 例、**useQueryAdapters.ts** 12 例），剩 81 个 | 核心路径已保护；其余为视图/组件层 | **部分闭合**（2026-11-24）：`api/*.ts` 剩 13 个、`views/`、`components/dashboard/widgets/*` 持续补测 |
| 105 | NEW-45 | 测试缺口 | `scripts/check_g_010_code_size.py` | **G-010 只拦 >500 阻断档，>400 警告档不阻断**：实测 **20 个文件 >400**（最高 `docker/scheduler.py` 494），全部 PASS | 20 个文件在 400~500 区间缓慢增长，任一破 500 即阻断 CI（且历史上已多次靠「拆分证据」豁免） | 警告档加「棘轮」：登记当前 20 个文件与行数，只拦「新增或增长」 |
| 106 | NEW-46 | 测试缺口 | `scripts/check_g_012_comment_density.py` | `[LANG]` 注释语言警告 **27 条**长期挂着（不阻断）；V-17 记的是同一族问题的另一种表现 | 注释质量门禁形同虚设 | 与 V-17 同批处理：要么清 27 条，要么改判定口径 |

---

## 四、已接受不做（标注理由）

> 来源：`docs/debt/02-accepted.md`（维持现状 / 已跳过测试 / 已接受的设计决策 / 审计结论固化）+ 03-open 里明确「暂不处理」项。
> 判据：受语言/框架/外部系统限制，或成本 > 风险 ⇒ 写明限制 + 记下不还的代价 + 绑定重评触发条件，**不排期**。

| # | 编号 | 类别 | 位置 | 问题 | 已接受理由 | 重评触发 |
|---|---|---|---|---|---|---|
| A1 | 02-accepted §三 | 已接受·代码结构 | `pilotstd/ui/core/handlers/_settings.py`（434）、`_theme_ops.py`（115）、`_file_tree_ops.py`（210）、`_export_ops.py`（118）、`_file_dialog_ops.py`（40） | 5 个纯 Qt 控件构建文件停止拆解 Engine，仅 E2E 兜底 | 只做控件构建与信号接线，无业务算法；拆解收益低于碎片化成本 | 若沉淀出业务逻辑（动态对比度/复杂联动校验）再局部提取。**注意**：`_settings.py` 已 434 行进 G-010 警告区，见 NEW-29 |
| A2 | 02-accepted §四 | 已接受·测试 | `tests/test_e2e_adapters.py:40-41,97`、`tests/test_ocr_fallback.py:38`、`tests/test_manager.py:96/114/132/244/375`、`tests/test_file_utils.py:62/77/249`、`tests/gui/test_file_tree.py:31`、`tests/unit/manager/organize/test_mirror.py:166`、`tests/stress_winui.py:107` | 环境依赖跳过（外部站点不可达 / 无 OCR provider / 平台不支持 sparse file 或长路径 / CI 无外网），共 102 处跳过点 | 代码侧无解；E2E 保留本地手动跑，CI 自动跳过 | 外部站点恢复 / 引入 OCR provider / 平台变更 |
| A3 | 决策 #1 | 已接受·通知 | `pilotstd/core/notification/channels/` | 邮件渠道列入黑名单（仅 wechat/feishu/dingtalk/telegram + base） | 邮件依赖外部 SMTP 凭据与可达性，维护成本高于收益；4 个 IM/Push 渠道已覆盖场景 | 只有邮件可达（服务器网络屏蔽 IM 渠道）时重新评估 |
| A4 | 决策 #2 | 已接受·安全 | `docker/_static_token.py`（`api_keys.key_id='pst_static'`） | 静态 API 令牌不支持过期 / 无 TTL | 令牌由环境变量注入、供仓外脚本调用，加 TTL 会引入「脚本半夜失效」运维面；落库存哈希 | 令牌一旦泄露即永久有效 ⇒ 对外开放前必须先补 TTL/轮换 |
| A5 | 决策 #3 | 已接受·代码规模 | G-010 治理策略 | 分批渐进式治理 400+ 行文件（触及即拆 + 到期必拆） | 一次性拆 400+ 行会引入大面积行为风险 | 警告区文件破 500 阻断线时（当前 20 个警告档、0 个阻断档） |
| A6 | 决策 #5 | 已接受·代码结构 | 同 A1 的 5 文件 | 纯 UI 编排文件不再拆解 Engine | 同上 | 同上 |
| A7 | 决策 #7 | 已接受·架构 | `docker/session_store.py` | 内存会话存储（无持久化） | 简单够用；重启后需重新登录是预期行为 | 多副本部署（横向扩容）前必须先引入 Redis 等外部会话存储 |
| A8 | 决策 #9 | 已接受·通知 | `DingtalkMenuClient` | 钉钉无持久菜单（官方群机器人/互动卡片无服务端持久菜单 API） | `dd.showActionSheet` 是客户端 JSAPI，不属于机器人菜单；A-27 对钉钉显式 `unsupported` | 需要「卡片按钮替代」时另立需求 |
| A9 | V-15 | 已接受·测试 | `web/src/components/NotificationConfig.test.ts:364` | 「策略读取失败」用例标 `30_000`（其余默认 5s） | 隔离跑仅 1.185s；全量 45 文件并发 + v8 插桩时才超 5s；属资源竞争，fake timers 无效 | ① CI 超 30s 或被 skip ② vitest 支持按文件设 timeout ③ 全量覆盖率耗时优化到不需并发 |
| A10 | A-41 | 已接受·功能 | `docker/api/notification_logs.py`（failed-items） | failed-items 无 admin 跨用户视图（明确不做） | 不需要专门 admin 排障界面；现有 `notification_log` 按用户查 + 服务端日志 + `/diagnostics` 已够 | 出现「必须跨用户排障且现有手段不够」的真实工单 |
| A11 | A-54 | 已接受·UI | `pilotstd/ui/`（QMainWindow + mixin） | Win 端主窗口/侧边栏/内容区布局未与 Web 的 `PageContainer`/`AppCard` 对齐 | 2026-11-23 用户裁定暂不处理：Qt 父子关系与 Web DOM 层级**不同构**，没有等价「页面级容器」概念 | 有具体业务需求（新增 Win 页面 / 用户反馈 Win-Web 观感差异明显）时先出方案 |
| A12 | 02-accepted §五·A/C | 已接受·i18n | 全库 AST 扫描 | 中文参与逻辑分支 27 处（中危 12 处「措辞耦合」+ 低危 15 处）不专项收敛 | 两侧皆本仓常量，当前可用，非功能缺陷；给编号会诱导「为了消编号而做」 | 所在文件因其他改动被触碰时顺手收敛；若在非中文语言下被证实失效 ⇒ 升级高危立即处理 |

---

## 五、分批执行计划建议

> 排序原则：先 P0 后 P1 后 P2；同优先级内先「改一处收益多处」。
> 每批均要求：独立提交、独立验证、可回滚。
> **覆盖面：8 个批次合计 106 项 = 全部 P0(25) + P1(15) + P2(66)，无遗漏（见末尾核对表）。**

### 批次 1 · P0-A：生产部署验证批（22 条）
- **范围**：G-14/15/17/18/19/20/21/22/23/29/34/36/37/38/39/40/41/42/44/46/47/48
- **预估改动文件数**：0（纯部署 + 验证脚本）
- **可独立验证**：是（每项都有生产侧判据）
- **完成判据**：22 项逐条在生产按各自判据复验通过并回写 `00-global-issues.md` 状态为「已闭合」；`/api/health` 的 `version`/`schema_version` 与本次镜像一致
- **风险**：需维护窗口；G-40 需真实外发一条通知

### 批次 2 · P0-B：数据方向治理 + 台账 P1 收口（11 条）
- **范围**：
  - P0（3）：G-27（`scan-and-index` indexed 0）/ G-28 / G-33（`superseded_by` 方向）
  - P1（8）：T-42（渠道限流按码）/ A-40（残余 89 行）/ A-44（monitor 新目录）/ A-45（站内渠道）/ G-03 + G-25（探针）/ G-35（迁移脚本授权）/ G-43（日志计数口径）
- **预估改动文件数**：6~9（`scheduled_service.py`、`migrate_superseded_by_direction.py`、`channels/base.py`、`monitor/scheduler.py`、探针配置）
- **可独立验证**：是（33 条试点 → 回滚验证 → 全量；每项有独立判据）
- **完成判据**：① `scan-and-index` 在受控目录上 `indexed > 0` ② 迁移全量后「方向倒退」从 92% 降到 0 且目标行无覆盖 ③ `notification_log` 残余 `user_id=1` 归零 ④ 探针 pending 数下降 ⑤ 限流改为按码判定（至少一家取证）
- **前置**：批次 1 已部署（G-22 归档统计可核对备份是否落盘）
- **说明**：G-25 与 G-27 同源（「查询链没结果」），一起看

### 批次 3 · P1-A：门禁盲区 + 健壮性 + 安全（7 条）
- **范围**：
  - NEW-01（G-050 `continue`/`break` 盲区，29 处存量）
  - NEW-02（`database.py:80` 锁超时死循环）
  - NEW-03（`system.py` async 阻塞 300s）
  - NEW-04（`record_pending` N+1）
  - NEW-05（`validate_paths` 全表 stat）
  - NEW-06（SVG 上传存储型 XSS）
  - NEW-07（03-open ↔ 00-global 5 项状态冲突）
- **预估改动文件数**：9（`check_g_050_silent_errors.py` + `silent_errors_baseline.json`、`database.py`、`system.py`、`pending_service.py`、`file_index.py`、`upload.py`、两个台账文件）
- **可独立验证**：是（门禁自测 + 受控注入 + mock）
- **完成判据**：① `check_g_050` 新增 `continue`/`break` 两档且基线冻结 29 条存量，`--emit` 与基线一致 ② `database.py` 锁超时分支有单测（模拟 `OSError` 必须返回 `False`） ③ `/update` 期间 `/api/health` 仍 200 ④ `record_pending(200)` 往返 ≤2 次 ⑤ `validate_paths` 分批且内存可控 ⑥ `.svg` 被拒或强制 `attachment` ⑦ 5 项编号两文件状态一致
- **收益**：NEW-01 一处改动防住 29 个存量吞错的「新增面」；NEW-07 决定后续所有排期的工作量估计

### 批次 4 · P2-A：债务台账 P2 收口（27 条）
- **范围**：T-40 / T-43 / A-5 / A-22 / A-27 / A-27.1 / A-27.2 / A-32 / A-42 / A-43 / A-46 / A-52 / V-2 / V-3 / V-6 / V-7 / V-8 / V-9 / V-10 / V-11 / V-13 / V-14 / V-16 / V-17 / V-18 / V-19 / V-20
- **预估改动文件数**：不定（多数是「等触发」或「观察中」，本批动作是**逐条重新定性**：确认仍成立 / 降级为已接受 / 关闭）
- **可独立验证**：是（每条给「保留/关闭/转接受」的裁定 + 依据）
- **完成判据**：27 条全部有明确去向并回写台账：① 能做的做掉（A-52 按类补令牌、A-42 传上下文、A-46 核销、V-8/V-9 拆分）② 做不了的转 `02-accepted` 并写理由 ③ 纯观察的确认触发条件仍有效
- **建议**：先做「改一处收益多处」的 A-42（两个调用点传 `get_current_user_id()`）与 V-18（与 G-42 同批改指标键）

### 批次 5 · P2-B：后端性能批（9 条）
- **范围**：NEW-18（`matcher.py` 逐条 UPDATE）/ NEW-19（`daily_quota` 逐站点）/ NEW-20（`date_reminder` 逐 uid）/ NEW-21（`_suppression_queue.expire`）/ NEW-22（`mark_logs_read`）/ NEW-23（`scan_and_index` 全量哈希）/ NEW-24（`upload` 同步写）/ NEW-25（`wechat_ip` 串行探测）/ NEW-26（3 处无分页全表读）
- **预估改动文件数**：10（`matcher.py`、`daily_quota.py`、`date_reminder.py`、`_suppression_queue.py`、`_manager_ops.py`、`scheduled_service.py`、`upload.py`、`detector.py`、`_file_index_query.py`、`adapter_manager.py`）
- **可独立验证**：是（每处改完跑对应单测 + 受控数据比对查询次数）
- **完成判据**：① 6 处循环写全部改批量且行为等价（有单测锁定）② `scan_and_index` 先按「路径/大小/mtime」快速排除再算哈希 ③ `upload` 写盘走 `run_sync` ④ `wechat_ip` 并发取或总预算超时 ⑤ 3 处全表读加 `limit` 且 API 默认 500
- **建议**：先做 NEW-22（前端「全部已读」高频，用户可感知）

### 批次 6 · P2-C：异常静默 + 无主 TODO（10 条）
- **范围**：
  - 静默（7）：NEW-11（`_attachment_parser`）/ NEW-12（`energy`）/ NEW-13（`jjg`+`energy` break）/ NEW-14（`main.py` 三处 pass）/ NEW-15（`docker/scheduler.py` 备份清理）/ NEW-16（前端 54 处，先修 3 个组件 12 处）/ NEW-17（`stores/app.ts` 监听器）
  - 无主 TODO（3）：NEW-08（`ci.yml:864` 覆盖率 58）/ NEW-09（`HomeView.vue:18` 与 V-10 合并）/ NEW-10（`design-tokens.css:11` 闭环条件）
- **预估改动文件数**：14（7 个后端文件 + `FileMonitor.vue`/`CacheManager.vue`/`TaskManager.vue`/`stores/app.ts` + `ci.yml`/`HomeView.vue`/`design-tokens.css`）
- **可独立验证**：是（日志断言 + 组件测试断言 toast 被调用）
- **完成判据**：① 7 处后端吞错全部补日志/留痕（有单测断言 `caplog`）② 3 个组件的失败分支弹 toast（有组件测试）③ `stores/app.ts` 监听器可 dispose ④ 3 个无主 TODO 全部有主（挂债号或删除）
- **收益**：NEW-16 的 3 个组件同时改善 V-16 覆盖率

### 批次 7 · P2-D：文档漂移与死链批（9 条）
- **范围**：NEW-27 / NEW-28 / NEW-29（行数漂移）/ NEW-30（导航计数）/ NEW-31（migrations 版本）/ NEW-32（147 条死链）/ NEW-33（`overview.md` 27 条）/ NEW-34（3 处 `architecture/architecture.md`）/ NEW-35（token 计数三处不一致）
- **预估改动文件数**：10~15（`04-watch.md`、`02-accepted.md`、`technical-debt.md`、`migrations/README.md`、`architecture/overview.md`、`gates.md`、`ACCEPTANCE_CASES.md`、`01-archive-closed.md` 等）
- **可独立验证**：是（`check_g_032_doc_health.py` + 自写死链扫描脚本）
- **完成判据**：① 所有行数/计数与实测一致（用 `check_g_010` 输出比对）② 死链扫描 0 条（或全部标注「历史已不可考」）③ `check_g_032` 的 3 条 warning 清零 ④ token 计数定唯一事实源
- **建议**：把「死链扫描」固化成脚本并接进 G-032（现在只 warn 且只查部分引用）

### 批次 8 · P2-E：资源泄漏 + 测试缺口（11 条）
- **范围**：
  - 资源（6）：NEW-36（13 文件 Session 无 close）/ NEW-37（`announcement/base.py` 每次新建）/ NEW-38（`network.py` 两处）/ NEW-39（`DriveEnumerator` QThread）/ NEW-40（`LogHandler` QTimer 未停）/ NEW-41（DB 连接累积）
  - 安全（1）：NEW-42（CSP `unsafe-eval`）
  - 测试（4）：NEW-43（30 后端模块无测试）/ NEW-44（84 前端文件无测试）/ NEW-45（G-010 警告档无棘轮）/ NEW-46（G-012 `[LANG]` 27 条）
- **预估改动文件数**：15~20
- **可独立验证**：是（Session 用 mock 断言 `close()`；QThread 用 `qtbot` 断言 `deleteLater`；门禁用 `--emit` 比对）
- **完成判据**：① 13 个 Session 创建点全部有配对 `close()`/`with`（单测断言）② `DriveEnumerator` 有 `finished→deleteLater` ③ `LogHandler.close()` 停定时器 ④ CSP 生产构建去掉 `unsafe-eval` ⑤ `api/http.ts` 有测试覆盖池泄漏/取消语义 ⑥ G-010 警告档棘轮上线（20 文件登记，只拦新增/增长）⑦ `[LANG]` 27 条清零或改判定口径

### 批次顺序总览

| 批次 | 优先级 | 条目数 | 改动文件 | 关键收益 |
|---|---|---:|---:|---|
| 1 部署验证 | P0 | 22 | 0 | 生产上 22 个已修 bug 真正生效 |
| 2 数据方向 + 台账 P1 | P0/P1 | 11 | 6~9 | 92% 反向关系修正 + 台账 P1 收口 |
| 3 门禁/健壮/安全 | P1 | 7 | 9 | 一处改动防住 29 个吞错 + 堵存储型 XSS |
| 4 台账 P2 收口 | P2 | 27 | 不定 | 27 条悬项逐条定性（做/转接受/关闭） |
| 5 后端性能 | P2 | 9 | 10 | 批量入库/查询提速，消除 N+1 |
| 6 异常静默 + TODO | P2 | 10 | 14 | 失败可见 + 3 个无主 TODO 有主 |
| 7 文档漂移与死链 | P2 | 9 | 10~15 | 文档可跳转、数字可信 |
| 8 资源泄漏 + 测试 | 11 | **10** | 🔶 部分 | 5 类泄漏已修；NEW-45 棘轮、NEW-46 [LANG] 清零完成；**NEW-43 已归零**（后端模块无测试引用 30→0，补 176 例）；NEW-44 已补 api/http.ts + 2 个 composables，剩 81 文件持续补测 |
| **合计** | | **106** | | 覆盖全部 P0/P1/P2 |

### 覆盖率核对（机械校验）

| 来源 | 条目数 | 落入批次 |
|---|---:|---|
| P0 表（第一节 25 行） | 25 | 批次 1（22）+ 批次 2（3） |
| P1 表（第二节 15 行） | 15 | 批次 2（8）+ 批次 3（7） |
| P2 表（第三节 66 行） | 66 | 批次 4（27）+ 批次 5（9）+ 批次 6（10）+ 批次 7（9）+ 批次 8（11） |
| **合计** | **106** | **8 批，无遗漏** |

> 核对方法：`22+3=25`、`8+7=15`、`27+9+10+9+11=66`、`25+15+66=106`。
> 已接受不做（12 条）**不排期**，不进入任何批次。

## 附、已核实无需处理（防下次重复排查）

> 这些项在扫描中被标记为「疑似问题」，逐条读源码后确认**不是债**。列出来避免下一轮重复花时间。

| # | 位置 | 疑似问题 | 核实结论 |
|---|---|---|---|
| V1 | `docker/api/logs.py:300-308`、`docker/api/backup.py:145-164`、`docker/api/upload.py:93-102`、`docker/api/scan.py:55-63`、`docker/api/archive.py:47-60`、`docker/api/organize.py:27-43` | 路径穿越 | **均已校验**：logs/backup 用 `realpath` + `startswith(dir + os.sep)`；upload 用 `os.path.basename`；scan/archive/organize 用 `validate_path_in_root` + `get_allowed_roots`（含 realpath 规范化）。**无路径穿越** |
| V2 | `docker/api/admin_db.py:114-142,230-231` | 管理员任意 SQL 执行 | **可控**：AST 级校验（DROP DATABASE 拒绝、DROP TABLE 需 `confirm_dangerous` + 表白名单、DELETE/UPDATE 必须带 WHERE）+ SELECT 自动包 `LIMIT 1001` + `progress_handler` 超时 + 仅 admin。**属设计内能力** |
| V3 | 52 处 f-string SQL 拼接（`docker/api/announce_detail.py:533`、`pilotstd/core/cache_manager.py:258`、`pilotstd/announce/crawler_service.py:183`、`docker/diagnose_announce.py:97` 等） | SQL 注入 | **已逐条核实**：插值对象均为 ① 常量表名（`_MANAGED_TABLES`/`FILE_INDEX_TABLE`）② 白名单键名（`allowed` 集合过滤后的列名）③ 静态 SQL 片段（`referenced` 是常量字符串）④ SQL 字面表达式（`date('now','localtime')`）。**无用户输入直接进 SQL** |
| V4 | 全库硬编码凭证扫描（48 处命中） | 硬编码密钥 | **4 处生产命中全是测试夹具**：`web/e2e/dashboard/quick-actions.spec.ts:12`（`Admin@123` E2E 测试账号）、`web/src/views/SettingsView.test.ts:25-26`（`pst_mock_token`）、`web/eslint-plugin-custom/rules/no-raw-input.js:32`（规则里的属性名）。其余在 `tests/` 与 `docs/.local/bandit-report.json`。**无生产硬编码密钥** |
| V5 | `config/docker_creds.json` 存在 | 凭证入仓 | **未入 git**：`git ls-files config/` 只有 `site_capabilities.yaml`；`.env` 同理（只跟踪 `.env.example`，`.gitignore:6` 忽略 `.env`）。**安全** |
| V6 | 前端 16 个文件的 `setInterval` / `addEventListener` | 定时器/监听器泄漏 | **全部成对**：13 处 `setInterval` 全有 `clearInterval`，10 处 `addEventListener` 全有 `removeEventListener`（`AppHeader.vue:48/51`、`useAppLayout.ts:99/101,198/199`、`useNotification.ts:150/156`、`LogBar.vue:128-139` 等）。**唯一例外是 `web/src/stores/app.ts:84`**（模块级 store，已列入 NEW-17） |
| V7 | 05-audit 记的「3 个真门禁零调用且必 FAIL」 | 门禁失效 | **已修**：`check_g_034_coverage_threshold.py` / `check_property_proxy.py` / `check_signal_connect.py` 实测**全部 EXIT=0**；`check_g_030/031` 也已接 `_gate_git.ChangeScope`（git 不可用即 `ChangeSetUnavailable`，不再假绿） |
| V8 | 05-audit 记的「`.pre-commit-config.yaml` 31 hook 从未执行」 | 门禁幽灵 | **已收口**：`core.hookspath = .husky`，`.husky/pre-commit` 调 `check_all.sh --fast --guards --local` 并接回 3 项原死在配置里的检查（`check_decorator_order.py`/`check_g_013_test_coverage.py`/`check_mixin.py`）；`.husky/commit-msg` 补齐 R-014 校验；`.pre-commit-config.yaml` 已归档到 `docs/archive/` |
| V9 | 全库 `except:`（裸 except） | 裸异常 | **0 处**（AST 扫描确认） |
| V10 | `pilotstd/query/__init__.py` 的 21 个 `_get_*_adapter` getter | 死代码 | **已删**（A-33，2026-11-14）：现文件 22 行，getter 0 个，改为 `adapters/registry.py` 单一真相源 |
| V11 | `pilotstd/ui/main_window/parts/_query_ops.py:25` `_on_query_result_ready` | 死代码 | **仍是死代码但已裁定保留**：生产信号已删、仅 8 处测试直接调用（p2-03 triage §四 已定性为「测试债务」并给到期机制）。**不重复登记**，见 p2-03 批 3 动作清单 |

---

## 附、扫描方法与可复现命令

```bash
# 门禁现状（全部 EXIT=0，2026-11-23 实测）
python scripts/check_g_050_silent_errors.py      # pass=46 return=46 debug=66 / 基线 46/47/69
python scripts/check_docs_drift.py               # 违规 0
python scripts/check_g_032_doc_health.py         # 3 warning
python scripts/check_design_tokens.py            # 36 条 [STALE]
python scripts/check_g_010_code_size.py          # 警告档 20 个 >400
python scripts/check_g_012_comment_density.py    # [LANG] 27 条
python scripts/check_i18n_hardcoded.py           # PASS
python scripts/check_i18n_hardcoded_python.py    # PASS（10 文件低于基线）
python scripts/check_terminology.py              # PASS（未覆盖 509 键）
python scripts/audit_design_tokens.py --check    # A=0 B=148 C=588 D=0
```

扫描脚本（临时，位于 `%TEMP%/debt_scan/`，未入库）：
`scan_markers2.py`（TODO/FIXME/中文债务词，区分注释与代码）、`scan_silent.py`（AST 异常处理器）、`verify_g050_gap.py`（复现 G-050 口径盲区）、`scan_perf.py`（async 阻塞 / 循环查询 / `SELECT *` 无 LIMIT）、`scan_res.py`（`open()` 未 `with` / Session 创建点）、`scan_sec.py`+`scan_sec2.py`（凭证/SQL 拼接）、`scan_deadlinks.py`+`classify_links.py`（死链分类）、`scan_tests.py`+`scan_fe_tests.py`（测试缺口）、`scan_qt.py`（QThread/deleteLater/QTimer）、`scan_catch_fe.py`（前端空 catch）、`verify_lines.py`（台账行数核对）、`cross_status.py`（台账状态冲突）、`global_status.py`（00-global 状态统计）。

---

*本清单为只读扫描产出，未修改任何源码、未 commit、未 push。*

## 执行进度（2026-11-24 更新）

| 批次 | 条目数 | 已完成 | 状态 | 说明 |
|---|---:|---:|---|---|
| 1 部署验证 | 22 | 0 | ⏳ 待部署 | 代码已修；**判据已一键化**（scripts/ops/probe_batch1.py，11 项自动 + 11 项人工如实标 unverified）；需部署窗口执行 |
| 2 数据方向 + 台账 P1 | 11 | 4 | 🔶 部分 | G-27 可诊断化；**G-43 取证端点已上线**（/notification/logs/stats/distribution）；**G-25/G-03 探针死循环已破**（加 ile_index 第二数据源）；其余需部署或授权 |
| 3 门禁/健壮/安全 | 7 | 7 | ✅ 完成 | G-050 补 continue/break、迁移锁死循环、SVG XSS、台账互斥 |
| 4 台账 P2 收口 | 27 | 18 | 🔶 部分 | A-42 关闭、V-3 转 02-accepted、15 条 V-* 全量核查回写（含 8 处漂移订正）、A-43/A-46/A-5/A-22/A-27/A-32/A-52/T-40/T-43 确认终态 |
| 5 后端性能 | 9 | 9 | ✅ 完成 | NEW-18~26 全部落地（批量写、并发探测、廉价预筛、可选分页） |
| 6 异常静默 + TODO | 10 | 10 | ✅ 完成 | 7 处后端吞错 + 3 组件失败提示 + 监听器可 dispose + 3 无主 TODO 认领 |
| 7 文档漂移与死链 | 9 | 9 | ✅ 完成 | 新增 G-056 门禁，死链 529→0 |
| 8 资源泄漏 + 测试 | 11 | 9 | 🔶 部分 | 5 类泄漏已修；NEW-45 棘轮、NEW-46 [LANG] 清零完成；NEW-43/44 已补 pi/http.ts（8 例）+ _log_scope（7 例）核心路径，其余 28+82 文件属持续补测 |
| **合计** | **106** | **67** | | 4 批完成 / 4 批部分 / 1 批待部署 |

### 本轮（2026-11-24）新增完成项

- **批次 5 补齐 4 项**：NEW-19（daily_quota 批量补行）、NEW-20（date_reminder 批量去重）、
  NEW-23（先廉价排除再算哈希）、NEW-26（`get_all` 可选分页）
- **NEW-25 确定性回归修复**：并发化后 `ips.append` 按完成顺序追加，
  导致 `Counter.most_common` 平票结果漂移；改为按源索引顺序回填（CI 两个 job 实测抓出）
- **批次 4**：A-42 关闭（两端点均已传 `NotificationContext`）、V-3 转 `02-accepted`、
  15 条 V-* 全量核查（12 保留观察 / 1 转接受 / 2 需生产数据）+ 订正 8 处文档漂移
- **V-16 补测试**：`web/src/components/TaskManager.test.ts`（6 例），
  兑现「随功能变更补失败分支用例」

### 明确无法在本地完成的部分（需你决策）

| 项 | 缺什么 |
|---|---|
| 批次 1（22 项） | **部署窗口**：代码已修，需部署到 `192.168.1.18:9028` 才生效 |
| G-28/G-33/G-35 | **数据迁移授权**：脚本已就绪（演练/备份/回滚齐全），需你确认规则后 `--apply` |
| G-43 | **生产两时点数据**：`event_type × level` 分布 |
| V-7 | **平台侧信号**：GitHub runner 镜像是否已切 Ubuntu 26 |
| V-18 | **部署后真实批次**：P3-16 修复后的 `query_metrics` 行 |
| A-52 | **产品确认**：视觉收敛会改变外观，需接受变化 |

## 附二、TODO / 临时兼容逻辑深度扫描（2026-11-24）

目标要求「扫描全库 TODO/FIXME/临时兼容逻辑」。本节记录**实测口径与结论**，
避免下次重复排查。

### A. TODO / FIXME / HACK

`git grep -E "TODO|FIXME|HACK"` 于 `pilotstd/ docker/ scripts/ web/src/` 命中 **125 行**。

| 类别 | 行数 | 结论 |
|---|---:|---|
| 已有债号（A-x/V-x/NEW-x/T-x/G-x） | 14 | 无需处理 |
| `TODO: [Design Debt]`（本属 A-52） | 103 | **已补 A-52 债号**（2026-11-24） |
| 脚本自身词表/正则（误报） | 4 | 不改 |
| 非真 TODO（note 文案、已删除说明） | 2 | 不改 |
| **真正的无主 TODO** | **0** | ✅ 已清零 |

**误报识别要点**（下次扫描直接排除，省时间）：
- `T/XXX`、`TXXX` —— 团体标准号格式，不是待办标记
- `EVENT_XXX`、`EVENT_X` —— 通知事件符号名
- `G-XXX` —— 门禁占位符
- `'TODO'`、`"TODO"` —— 脚本自身的词表条目
- `\uXXXX` —— Unicode 转义说明

**处置**：103 处 `[Design Debt]` 统一补上 `A-52 —` 前缀，使其可被台账追踪
（此前 grep 才知道有多少令牌债，现在 `docs/debt/03-open.md` 的 A-52 与代码双向可查）。

### B. 临时兼容逻辑

四类关键词扫描结果：

| 类别 | 行数 | 结论 |
|---|---:|---|
| 临时方案 / workaround | 3 | `HomeView.vue` 2 处已挂 V-10；其余为词表 |
| deprecated / 废弃 | 35 | **均有明确兼容理由**，非技术债 |
| 旧版兼容 / backward compat | 60 | 均为历史数据/签名兼容，属设计内 |
| 过渡 / 灰度 / feature flag | 9 | 均为配置项，非临时代码 |

**逐项核实结论**：

- **`/api/user/settings`（GET/PUT）** —— 前端 `web/src/` 与 Win 端 `pilotstd/ui/`
  **均零引用**（git grep 实测），唯一消费方是验证废弃告警的测试。
  属「设计内保留」而非债，但已补**移除计划**注释（移除条件、连带删除项、
  需同步的文档行号），使其可被审计。
- **`/api/announcements?sync=true`** —— 前端零引用，已由异步端点替代；
  `[DEPRECATED]` 告警保留（外部脚本可能仍用）。
- **`bypass_aggregation` 参数**（`notification/events.py`）—— 恒为 False，
  保留字段仅为兼容旧签名；v1.1 起所有事件均聚合。属设计内兼容。
- **`NotificationChannel` / `EVENT_EXPIRED`** —— 模块级 `__getattr__` 抛
  `DeprecationWarning`，是**主动的迁移引导**，不是遗留代码。
- **`validity.frequency`**（config/defaults.py）—— `@deprecated` 标记，
  用 `frequency_weeks` 替代；保留供旧配置文件读取。属设计内兼容。

**结论：未发现「该删未删」的临时代码**。所有 deprecated 项都有明确兼容对象
（旧前端、旧配置、外部脚本、旧签名），删除会造成真实破坏。

### C. 异常未捕获 / 性能 N+1

这两项已在批次 3（G-050 补 `except: continue|break` 识别，26 处吞错冻结）
与批次 5（9 项 N+1 全部消除）中系统性处理，本清单第三/五节有完整记录，
本节不重复。

## 附三、过期注释深度扫描（2026-11-24）

目标要求「深度排查 ... 过期注释」。本节记录**实测口径与结论**，避免下次重复排查。

### 检测口径（四类）

| 类型 | 检测方法 | 结果 |
|---|---|---|
| ① 注释里的**日期已过期**（如「2026-08-09 前处理」） | 正则提取 `20XX-XX-XX` 与今天比较 | **0 处** |
| ② 无期限的**临时标记**（临时/暂时/先这样） | 关键词 + 排除技术术语 | 47 处命中 → **真待办 1 组**（已清理） |
| ③ 注释里的**数量与实际不符** | 由 `G-052`（`check_docs_drift.py`）覆盖 | 0 违规 |
| ④ 注释说「已废弃/待移除」但代码仍在 | 已在「附二 B. 临时兼容逻辑」处理 | 见附二 |

### ② 的甄别：47 处里绝大多数是**技术术语**，不是待办

排除以下技术术语后只剩 1 组真待办：

- `临时文件` / `临时表` / `临时目录` / `临时变量` / `临时对象` / `临时态` / `临时值`
  / `临时占位` / `临时缓存` —— 描述**原子写入模式**（先写临时文件再 `os.replace`）
- `临时性错误` / `临时性失败` —— 描述**可重试的错误类别**（超时/5xx/限流）
- `临时渠道实例` —— 描述 `security_notifier` 的**运行时构造**（用旧凭证临时构造）
- `临时高亮` / `临时状态` —— 描述 **UI 瞬时状态**

### ① 真待办：A-35 的临时诊断日志（已清理）

`docker/api/favorites.py` 有 5 处 `[A35-DIAG]` 日志，注释明写
「临时诊断（**A-35 定位后**降级 debug/删除）」。

**核实 A-35 状态**：`docs/debt/01-archive-closed.md` 已登记 A-35 **闭合**
（事件发送路径参数化完成）⇒ 这批诊断日志的清理条件已满足，属**真过期**。

**清理结果**：

| 原日志 | 处置 |
|---|---|
| `[A35-DIAG] enter favorite_created block` | 删除（纯定位用） |
| `[A35-DIAG] enter _notify_favorite_created` | 删除（纯定位用） |
| `[A35-DIAG] before send favorite_created` | 删除（纯定位用） |
| `[A35-DIAG] send completed` | 删除（正常路径不需 INFO 噪声） |
| `[A35-DIAG] send failed` | **保留**，改为正常措辞 `favorite_created 事件发送失败`（真实失败必须可见，G-050 口径） |

清理后 `git grep A35-DIAG` 在代码侧为 **0**（仅剩 `docs/plans/` 的历史验收记录，属历史快照不改）。

**验证**：`pytest tests -k "favorite"` → 122 passed。

### 结论

**过期注释已清零**：① 0 处过期日期、⑤ 0 处失效路径引用、② 唯一真待办（A-35 诊断日志）已清理（5 处 [A35-DIAG] 删 4 改 1，git grep 代码侧归零，	ests/test_favorite_event_logging.py 4 例锁定日志契约）。
③④ 由现有门禁（G-052）与附二覆盖。

### 下次扫描可直接复用的排除清单

```
临时文件 临时表 临时目录 临时变量 临时对象 临时态 临时值 临时占位 临时缓存
临时性错误 临时性失败 临时渠道实例 临时高亮 临时状态
```

## 附四、批次 1 真实部署自检结果（2026-11-24 18:39 实测）

对局域网部署实例 `http://192.168.1.18:9028` 跑 `scripts/ops/probe_batch1.py` +
`probe_all.py` 的实测结果。**这是批次 1 的第一次真实取证**。

### 部署身份

| 项 | 值 |
|---|---|
| 版本 | `v0.206.0` |
| 镜像 | `ghcr.io/leanmore/pilotstd:v0.206.0` |
| `APP_VERSION`（git sha） | `f433c633` = **main HEAD** |
| `schema_version` | 76（与迁移链一致） |
| 健康状态 | `ok`（database / monitor / parser 三服务均 true） |

> ⚠️ **重要**：本次部署的镜像是 **main 分支**（CI 的 docker job 硬约束
> `if: github.ref == 'refs/heads/main'`，且 `ref: main` 检出构建）。
> 特性分支 `feat/ds-phase3-microinteractions` 的改动**不在镜像内** ——
> 要部署方向 A/B/C 的成果，需先把 PR #26 合入 main，CI 才会构建新镜像。

### 批次 1 判据自检（22 项）

| 项 | 结果 | 证据 |
|---|---|---|
| G-21 公告服务端分页 | **PASS** | `/api/announce/results → 200，total=784` |
| G-22 归档统计端点 | **PASS** | `/api/system/archive-stats → 200`，字段 `by_type/exists/root/samples/total_bytes` |
| G-36 隔离区统计 | **PASS** | `/api/system/quarantine-stats → 200` |
| G-29 菜单配置写入口 | **PASS** | `OPTIONS /api/notification/menu/config → 405`（端点存在） |
| G-37 飞书群发现入口 | **PASS** | `OPTIONS /api/notification/menu/chats → 405`（端点存在） |
| G-48 mark_missing 入口 | **PASS** | `OPTIONS /api/pending/mark-missing → 405`（端点存在） |
| G-42 query_metrics 落表 | **PASS** | `query_metrics` 行数 = **411**（>0，found/not_found 已落表） |
| G-44 通知日志可见 | **PASS** | `/api/notification/logs → 200，total=2608` |
| G-46 / G-14 / G-47 | 进程内实现 | 无独立端点 → `unverified`（本地测试锁定） |
| G-15/17/18/19/20/23/34/38/39/40/41 | 需人工 | 11 项如实标 `unverified` 并注明原因 |

**合计：10 通过 / 0 失败 / 14 无法验证（11 人工 + 3 进程内）**

结论：**批次 1 中所有「可自动化判定」的判据已在生产验证通过**。
剩余 11 项需人工按各自判据确认（渲染类 / 目录类 / 真实外发）。

### 完整部署自检（4 个 probe + 批次 1）

| 探测 | 通过 | 失败 | 无法验证 | 阻断项 |
|---|---:|---:|---:|---|
| health | 8 | 0 | 0 | — |
| pending_paths | 8 | 1 | 0 | `pending.mass_delete_guard` |
| credentials | 5 | 0 | 3 | `feishu.credentials` |
| db_counts | 12 | 1 | 0 | `favorite_downloads.orphan` |
| batch1 | 10 | 0 | 14 | — |

### 3 条生产阻断项（真实数据，非本地推测）

1. **`pending.mass_delete_guard`（fail）**：按抽样外推缺失约 **61/61**，
   触发挂载保护阈值 ⇒ `mark_missing` **整轮跳过**（定时任务与端点跑完都不标记任何行）。
   探测已确认挂载可列、路径都在配置扫描根下 ⇒ **保护误报**（数据真的缺失）。
   处置：管理员在维护窗口内以 `protect=False` 执行一次，或先清理这批 pending。
2. **`feishu.credentials`（unverified）**：飞书凭证不齐全（webhook 缺 `webhook_url`；
   app 缺 `app_id` / `app_secret` / `receive_id`）。渠道当前**未启用**，
   如需启用需补齐字段，或加 `--allow-unconfigured-channels` 忽略。
3. **`favorite_downloads.orphan`（fail）**：**3 条孤儿行**（`favorite_id` 指向不存在的收藏）。

> 这 3 条与方向 B 首次实测（2026-11-23）结论完全一致 —— 说明探测脚本可复现，
> 不是一次性偶然。
