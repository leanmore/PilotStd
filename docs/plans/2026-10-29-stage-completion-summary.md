# 阶段完成总结（2026-10-29）

> 目的：一页看清"停在哪、验证到哪、下一步是什么"。
> 详细条目仍以 `docs/debt/`、`docs/ROADMAP.md`、`docs/DECISIONS.md` 为准。

## 一、已完整验证（代码 + 证据 + 文档）

| 项 | 证据 | 文档/提交 |
|---|---|---|
| A-20 静音配置写服务端 | 端点 200/400；UI 开关调新端点 | `7bde4efb`；debt A-20 |
| N1 静音三段（B2） | 窗口 21:49–21:55：warning 21:49:53 success；info 窗口内无 log；info 21:58:55 补投 success | `ab219160`（test-event）；ROADMAP S4 |
| Q6 记录/投递解耦 | 关闭期间 logs 389→394 仍写；页面 394 条可翻/可筛（headless Chromium） | ROADMAP S4 |
| A-13 telegram + A-17 | 部署后 ASCII 与含标点两条 `ok:true` | `9c23a940` 环境实测 |
| A-9 日志四段化 | 29 定向 + 全量 5818 | `9ab006ff`/`70c3725a` |
| A-10 Tab data-tab | 前端四件套 0/0/336/0 | `05ae773d` |
| A-16 MagicMock 根因 | 全量跑完不再生成目录 | `915b3f0f` |
| A-18 历史 hash | 9 映射 + 10 不可考；宽扫 0 未标注 | `f25b41d1` 等 |
| A-23 `/test` 绕过 dispatcher | 新增 test-event 并经 B2 验证 | `ab219160` |

## 二、挂起项（触发条件，不主动推进）

| 项 | 触发条件 |
|---|---|
| Q7 Windows 托盘（A-22） | 用户在 Windows 本机跑一次 |
| dingtalk/feishu/wechat 真发（A-13/T-40） | docker 配置批次提供凭证 |
| T-42 限流码 / T-43 回调报文 / A-6 429 统计 / D-14 阈值 | 拿到真实报文/分布 |
| A-21 按用户静音 | 出现多用户需求 |
| 阶段六三项 | 下次发版或 CI 增加 smoke |
| A-3 / A-5 / A-19 | 字段漂移 / hooks 变更 / 改 G-013 |
| 3-3 supports_callback / 3-4 S1 术语 / P-06 | 用户拍板 / 用户选择 / 数据样本 |

## 三、下一里程碑：S5 生产部署

| 需要 | 内容 |
|---|---|
| 版本 | `9c23a940`（v0.154.0）或其后；构建需 `--build-arg APP_VERSION=$(git rev-parse --short HEAD)` |
| 部署前 | `git pull` → 确认含 `ab219160`；CI 13/13（`ab219160` 已 success） |
| 风险 | requests 迁移（dingtalk/feishu 未真实验证）；回滚到旧镜像即可 |
| 验收 | `/api/health` version 匹配；发一条 ASCII + 一条含标点 `ok:true` |
| 已知未验 | Q7 Windows 托盘；三渠道真发中 dingtalk/feishu；静音按用户 |

## 四、待核小尾巴（不阻塞）

1. ✅ **日志 +4 已结案（2026-10-29）**：B2 两条（B2W 21:49:53、B2I 21:58:55）+ **两条定时 security_alert（IP 更新部分失败，wechat failed / telegram success，21:49:25）** = 4；同一任务在 09:49/15:49 也各出现一次，确认是周期性检查，不是测试残留。
2. **quiet-hours 验证前原值未快照**：恢复为默认 `enabled=false`。若验证前曾手动开启，需要重新打开一次（UI 开关或 `PUT /api/notification/quiet-hours`）。

## 五、决策记录（2026-10-29）
- **S5 部署时机**：随发版（B），不单独提前部署。
- **B4 `supports_callback`**：单独立项（A-24）。
- **B5/A-19**：采用方案①——G-013 接受 `web/src/**/*.test.ts`（已实现并加测试）。
- **B6/S1 术语 6 项**：待用户对 F-1～F-6 逐项确认（建议 A/A/B/A/A/A）。
- **quiet-hours**：用户确认原为开启状态，当前 v0.154.0 也保持开启；B2 验证结束时曾恢复为关闭，需以当前实际状态为准。
- **P-06**：单独立项（A-25）。
- **三渠道真发**：等 docker 配置后处理。
