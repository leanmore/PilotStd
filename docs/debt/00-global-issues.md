# 全局问题总表（唯一问题基线）

> 维护规则：每批收口只改状态/增删条目，不重列全表；状态仅三种：待做 / 等触发 / 已闭合。
> 闭合判据必须可复核（测试、数据核对、日志行、部署确认）。

## 一、本轮新产生（2026-11-17 批）

| ID | 事项 | 状态 | 判据/触发 |
|---|---|---|---|
| G-01 | csres 晚到结果被丢弃（`_collect_csres_results` 不覆盖既有 NG） | 待做 | 已修 + 单测；判据：部署后重查 GB 50016-2014 `stats.found>=1` 且日志评分 100 |
| G-02 | 61 条重查可信度（单站链） | 待做 | 判据：低峰用多站代码重跑，日志 `tried=` 出现 ≥2 站，且 `stats` 与日志一致 |
| G-03 | 健康检查探针 11 站 `probe_pending` | 等触发 | 触发：对应站点出现 `exact` 缓存；判据：自动纳入并输出 found/no_result |
| G-04 | 健康检查生产首轮样本 | 等触发 | 触发：v0.194.x 部署；判据：`POST /api/adapters/health/run` 返回 21 站分布 + 日志 |
| G-05 | 30 个 62 批副本（`/app/data/_quarantine/__replay_b62`） | 待做 | 判据：确认均为 standards 副本后删除或留存；28 条 pending 已标 `copy_quarantined` |
| G-06 | 28 条空分类 pending 回填 | 已闭合 | 已回填 `chain_exhausted` + `reason=copy_quarantined`；manifest/rollback 见 `C:\Temp\pending28_*` |
| G-07 | `health_probe.json` 轮转/上限 | 已闭合 | 单文件每次覆盖写，不增长；无需轮转（2026-11-17 确认） |
| G-08 | v0.192.1 审计 patch 是否含在 v0.194.1 | 已闭合 | `git merge-base --is-ancestor 2986acde 5e43c66b` 通过 |

## 二、之前悬着未闭合

| ID | 事项 | 状态 | 判据/触发 |
|---|---|---|---|
| A-44 | monitor 实时：新目录半残，必须 restart | 等触发 | 触发：有人依赖实时触发或换 PollingObserver；规则已写入 08 + 用户帮助 |
| A-45 | 无 dry-run/站内通知渠道 | 等触发 | 触发：新增渠道系统或 AC-6 复验触发链路 |
| A-46 | 33 个 file_missing 文件重取 | 等触发 | 触发：公告记录/下载链可重取；取到后归档并核销 |
| A-47 | 无结果转 pending 分类 | 已闭合 | `_finalize_batch` 默认 pending+chain_exhausted；单测锁定（待部署生效） |
| P3-16 多站链 | `_build_chain_for_item` 对 NB 仅 energy（能力模型单站）；SHB 运行时被过滤为 njbz365 | 待做（G-02） | 判据：确认是能力模型配置还是过滤；低峰重跑 |
| P2-08 | Organize/Pending 失败/恢复分支 | 已闭合 | 既有测试覆盖（见 27 #63）；后续为覆盖率棘轮 |
| A-40 | 旧数据 user_id 归属 | 已闭合（部分记录） | 452+67 行订正；残余 89→0（除用户动作 22 行）；queue 未改 |

## 三、定触发

| ID | 事项 | 触发 |
|---|---|---|
| A-44 | 实时缺陷修复 | 依赖实时/换 PollingObserver |
| A-45 | dry-run 渠道 | 新增渠道或 AC-6 复验触发 |
| A-46 | 33 文件重取 | 可重取来源出现 |
| A-47 | 已修待部署 | 部署后核验 |
| V-16 / V-17 / A-5 / A-32 / T-42 / A-43 | 见 03-open | 各自触发（改 TaskManager、G-012 第 3 次红、脚手架频繁、升级 cookiecutter、官方限流码、表数质疑） |
| P2-08 转阻断 | diff coverage 1~2 个月数据后 |

## 四、明确不做

| ID | 事项 | 理由 |
|---|---|---|
| FK×4 | `favorite_downloads`/`user_favorites` → `announcement_record` 4 条既有违规 | 与当前功能无关、无用户反馈；文档“已知不修” |

## 五、等外部条件

| ID | 事项 | 条件 |
|---|---|---|
| G-04 | 健康检查生产首轮 | 部署 v0.194.x（当前生产 0.192.0） |
| G-01 | stats 修复验证 | 部署后重查 |
| AC-6 触发链路 | 真实触发验证 | 需第二真实 admin 或 dry-run 渠道 |

## 六、已闭合（累计）

- M1（11 项）、M2（A-40 订正 + P2 双用户隔离）、M3（AC-6 读隔离、quarantine 路径、62 批演练、A1/A2/A3/B）；
- 62 批缩小版（10 目录/202 文件）；825 不做；
- 33 文件扫 API 可见根 0 命中（`/inbox`、`/standards`）；30 副本留隔离区；
- user5 2 条通知、a35_user2（测试账号）已清理。
