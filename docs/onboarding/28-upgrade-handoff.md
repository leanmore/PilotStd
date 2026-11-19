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

1. **CI 红（最高优先）**
   - 最新 run `44432226468`（HEAD `8228fa78`）：`test-backend` 的 `Run backend tests` 失败；
   - GitHub 日志返回 `BlobNotFound`，本地 `pytest tests -x -q` 未定位到失败点（跑到日志输出但退出 1）；
   - 已按指示暂停该单项；**升级后第一步是复现/定位，不能带红交付**。
2. **A-27 四家自定义菜单：全做（未开始）**
   - 企微（应用菜单 API）、飞书（机器人菜单/事件）、Telegram（setMyCommands/菜单按钮）、钉钉（工作台/机器人菜单）各自规范、层级、样式；
   - 需要新增各渠道 menu adapter + API + 配置 + 测试，工作量大，尚未落代码。
3. **V-17 G-012 1507 条语言警告：清到 0（未开始）**
   - 决定已下：分批清理、每批跑测试；当前 0 阻断、1507 警告；需逐文件分批。
4. **superseded_by 迁移：方案已出，未执行**
   - 约 49,306 行；方向纠正、回滚、备份、锁影响见 `docs/analysis/superseded-by-migration-plan.md`；
   - 等授权 + 维护窗口，未跑任何写库。
5. **R-3 真实操作重验（未完成）**
   - 生产已升 v0.195.5；需逐项真实 UI 复验（铃铛、通知内容、设置保存等），产出“真闭合/假闭合”表；
   - 注意：`b6357ba9` 顶栏修复是否已包含在 v0.195.5 需按版本核对。
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
