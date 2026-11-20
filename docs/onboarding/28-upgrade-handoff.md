# 升级交接报告（PilotStd · 2026-11-19）

> 用途：DSH/环境升级后继续本任务。仓库 `D:\PilotStd`，分支 `main`，交接时 HEAD `8228fa78`。
> 生产：`http://192.168.1.18:9028`，版本 **v0.195.5**。
> 总表：`docs/debt/00-global-issues.md`（唯一状态源）。

## 一、已完成（代码已推）

| 项 | 内容 | 提交 | 验证 |
|---|---|---|---|
| G-10 铃铛弹层偏左 | 真因 `topbar-right v-show=isHovered` 在鼠标移入弹层后隐藏铃铛，锚点变 0；改为 Popover 打开期间保持顶栏显示 | `b6357ba9` | Playwright 真实复现 `x=623→11.5`，修复后位移 8px（dev 构建+生产 API） |
| G-09 铃铛渠道副本 | 同一事件 wechat/telegram 行按内容+分钟去重 | `2d5f5e68` | 真实 UI 2 条→1 条 |
| U-1 有效性旧状态 | `_record_change` 补 `old_status`，输出“旧→新” | `c322c1c0` | 单测 2 例 |
| U-1 降级替代 | `validity_replacement.is_backward_replacement()` 忽略年份倒退的 `superseded_by` | `4d9e3b7d` | 单测 |
| U-1 通知级别 | 日志 API `level`（security_alert→warning、task_failure→error），铃铛着色 | `63613598` | 单测+前端 21 例 |
| U-3 掩码覆盖 | GET `***` 不再覆盖真实 CookieCloud key/password | `c322c1c0` | 单测 |
| U-3 失败降噪 | 同 IP Cookie 失败只通知一次 | `05113127` | 单测 |
| U-3 状态误报 | CookieCloud 模式显示“已配置/未配置 Key”，不再误报“未配置密钥” | `5d3d7aa5` | 单测 7 例 |
| G-03 探针自动发现 | `discover_probes()` 从 exact 缓存补 `probe_pending` | `66e0b8b4` | 测试 4 例；**已随 v0.195.5 部署** |
| A-43 表数 | 生产表数与迁移链一致；schema 一致性 0 处 | `1fa92c28` | 真实库检查 |
| A-44 monitor 热更新 | PUT 配置 stop→start；catchup e2e | `f7dd5bae` | 5 例 + 7 例 |
| V-16 TaskManager | failed 归一/终态/防御测试 | `680ef275` | 测试 |
| T-42 限流 | 码优先+429/5xx+Retry-After+关键词 | `562ae73a` | 3 例 |
| A-45 dry-run | `notification.dry_run=true` 只留痕不投递（仅显式 true） | `82bbabd1`、`e02c615e` | 单测；修复 MagicMock 误判 |

另有分析文档：`docs/analysis/notification-stage2.md`、`docs/analysis/superseded-by-migration-plan.md`（`8228fa78`）。

## 二、正在进行 / 未完成

1. **CI 红（最高优先）** — 2026-11-19 已修复，定位与证据见 `27-implementation-log.md` #80
   - 最新 run `44432226468`（HEAD `8228fa78`）：`test-backend` 的 `Run backend tests` 失败；
   - GitHub 日志返回 `BlobNotFound`，本地 `pytest tests -x -q` 未定位到失败点（跑到日志输出但退出 1）；
   - 已按指示暂停该单项；**升级后第一步是复现/定位，不能带红交付**。
2. **A-27 四家自定义菜单：全做（未开始）**
   - 企微（应用菜单 API）、飞书（机器人菜单/事件）、Telegram（setMyCommands/菜单按钮）、钉钉（工作台/机器人菜单）各自规范、层级、样式；
   - 需要新增各渠道 menu adapter + API + 配置 + 测试，工作量大，尚未落代码。
3. **G-012 `[LANG]` 语言警告：已清到 0（2026-11-19，见 `27` #81）**
   - 编号澄清：交接单把这条记作“V-17”，但 `04-watch.md` 的 V-17 实为“注释密度对新脚本反复红”，是另一件事；本条只处理语言警告，V-17 本身仍在观察。
   - 路径：先补规则盲点（`# i18n-allow:` 未算工具指令，1511→1402）→ 改按词判定（代码标识符不再误报，1402→504）→ 504 行分 6 批改写（叙事词译中文、裸标识符加反引号）→ 0。
4. **superseded_by 迁移：方案已出，未执行**
   - 约 49,306 行；方向纠正、回滚、备份、锁影响见 `docs/analysis/superseded-by-migration-plan.md`；
   - 等授权 + 维护窗口，未跑任何写库。
5. **R-3 真实操作重验（进行中，2026-11-20 首批已做）**
   - 生产已部署 **v0.196.1（`286a4ed2`）**，已确认含 U-1/U-3/G-03/铃铛/V-17 全部提交。
   - 已做（只读，登录后仅 GET，见 `27` #83）：`/api/system/version`=0.196.1；`/api/wechat-ip/config` 掩码 `***` 生效且带 `cookie_status`/`cookie_source`；通知正文出现 `现行 → 新标准：GB 30871-2014`。
   - **抓到假闭合 1 例并已修**：`63613598` 的“铃铛告警着色”没生效——`NotificationLogItem` 漏声明 `level`，FastAPI 过滤后前端恒 `info`。修复 `d9a29db1`；**2026-11-20 生产 v0.196.3 已实证**：`GET /api/notification/logs` 返回 `level`，100 条里 info 68 / warning 32。
   - **G-10 已真闭合**（Playwright 生产复验：弹层右缘距铃铛 8px，无左跳、铃铛盒不塌）；顺带修掉 `.topbar.collapsed` 在弹层打开时仍收缩造成的 8/10px 锚点位移（`AppHeader` 判据加 `!notificationOpen`，待部署）。
   - **G-09 已真闭合**（生产 v0.196.3）：日志里 telegram/wechat 同分钟成对（100 条 → 去重 45），铃铛只渲染去重后 10 条，与接口去重结果 10/10 对齐。
   - **顶栏锚点位移已归零**（`bee0add4` 部署后实测 0px）。
   - **IP 失败重复通知：根因已定位**——`docker/scheduler.py` 5 处 `ConfigManager()` 各持快照、save 整文件覆盖，`wechat_ip.last_fail_key` 被冲掉；复现脚本 `ci.tmp/probe_config_race.py`。修复需统一共享实例或改合并写，属写盘模型改动，下批单独立项。
   - 仍待真实操作：U-1 `_record_change` 的“旧 → 新”需真实跑一次时效检查（要写库窗口）。
6. **A-46 33 文件：不重开**
   - 结论：33 条 `file_missing` 原件在 `/standards` 未索引，30 份副本在 `/app/data/_quarantine/__replay_b62`；
   - 缺的是“重扫 /standards 并写 file_index”的生产写窗口，不是新线索；不重开，等维护窗口。
7. **D-3 事件键 vs 关键词**
   - 结论：**事件键优先，关键词仅兜底**；事件键可枚举、可测试，关键词易误判；落地前需在 `topic_index` 明确优先级并补测试。
8. **D-2 阶段 2：分析已完成，等定实现**
   - 见 `docs/analysis/notification-stage2.md`：统一语义层存在，渠道渲染分散；建议先做“渠道能力声明+统一 renderer”和“delivery/business 状态分离”。

## 三、等待外部条件

- 生产部署/重启（已到 v0.195.5，但 `b6357ba9` 等是否包含需核对）；
- superseded_by 迁移授权 + 备份 + 窗口；
- A-46 重扫窗口；
- A-27 平台侧菜单权限/应用配置（企微/飞书/钉钉后台）。

## 四、升级后恢复步骤

1. `cd D:\PilotStd && git status && git log --oneline -3`，确认 HEAD/工作区；
2. 读本文件与 `docs/debt/00-global-issues.md`；
3. 查 CI：`gh run list -L 3 --repo leanmore/PilotStd`，先定位 `test-backend`；
4. 查生产版本：`GET /api/system/version`；
5. 按优先级：CI 绿 → A-27 → V-17 分批 → R-3 重验 → 迁移（授权后）→ A-46（窗口）。

## 五、注意事项

- 不改生产库、不重启服务；写操作需窗口；
- 文档与代码同批；提交信息 `type(scope): 描述`，scope 小写/连字符；
- 前端改动跑四件套：type-check / lint / test / build；
- 生产凭据在 `config/docker_creds.json`，不打印/不提交；
- Playwright 真实 UI 验证使用临时用户，测完删除（已在 2026-11-18 做过）。

## 六、勘误（2026-11-19 复工核对）

1. 表内两个 SHA 是 rebase 前的孤儿提交（无任何分支包含），main 上的实际提交为同 patch-id 的另一 SHA：
   - `c322c1c0`（U-1/U-3）→ 实际 `4003372e`；
   - `66e0b8b4`（G-03）→ 实际 `0e2ff79b`。
   其后查证一律用 `git merge-base --is-ancestor` 判定，不要凭交接单里的短 SHA 下结论。
2. 生产 v0.195.5 = `5db18501` 的实际内容：**包含** `b6357ba9`、`2d5f5e68`、`0e2ff79b`（G-03 已上线）；**不含** `4003372e`（U-1“旧→新”、U-3“掩码不覆盖真实值”）以及此后全部提交（`4d9e3b7d`/`05113127`/`5d3d7aa5`/`63613598`/`1fa92c28`/`f7dd5bae`/`680ef275`/`562ae73a`/`82bbabd1`/`e02c615e`/`8228fa78`/`9e884970`）。
   → 因此 R-3 逐项复验里，U-1/U-3 在部署前一定表现为“未修好”，属未上线而非假闭合。
3. 交接所述“本地 pytest 未定位失败”有两个干扰因素：GitHub job 日志 404（只能走 annotations），以及 `2>&1 | Tee-Object` 管道让全绿运行也返回 exit 1。判定退出码用 `*> 文件` 再读 `$LASTEXITCODE`。
4. 本次修复未改生产、未动数据；生产仍为 v0.195.5，等待部署窗口。

## 七、暂停记录（2026-11-20 18:07，补执行 13:55 的暂停指令）

> 指令：北京时间 13:55 暂停所有作业。排程到点时本会话已离线，18:07 上线后补执行。

- **作业状态**：后台作业 0 个（`job_list` 为空）；子代理 6 个均为 inactive（昨日语言批次的产物），无运行中任务。
- **代码状态**：HEAD `2402c29c`，工作区干净，与 `origin/main` 同步；未提交任何东西（本文件本次改动按指令保留在工作区）。
- **生产状态**：已部署 **v0.196.3**（`2402c29c`，镜像 `ghcr.io/leanmore/pilotstd:v0.196.3`），包含今天的 `d9a29db1`（通知日志 level）与 `bee0add4`（顶栏 collapsed 判据）。
- **今日闭环**：
  - 通知日志 `level` 假闭合 → 已修并**生产实证**（100 条：info 68 / warning 32）；
  - G-10 弹层偏左 → Playwright 生产复验真闭合（弹层右缘距铃铛 8px，无左跳）；
  - 顶栏 collapsed 造成的 8/10px 锚点位移 → 已修（待用真实 UI 复核一次）；
  - CI `2402c29c` 全绿。
- **下一步（复工按此顺序）**：
  1. 用 Playwright 复核 `bee0add4` 后锚点位移是否归零（预期 0~2px）；
  2. G-09 去重：构造“同事件同分钟双渠道”样本再验，别用“看着没重复”判闭合；
  3. IP 失败重复通知：查 `wechat_ip/scheduler.py:83` 成功分支清空 `last_fail_key`、以及 `last_fail_key`/`last_ip` 跨重启持久化；
  4. U-1 `_record_change` 的“旧 → 新”：需真实跑一次时效检查（写库窗口）；
  5. `superseded_by` 迁移（等授权+备份窗口）、A-46 重扫（等窗口）。
