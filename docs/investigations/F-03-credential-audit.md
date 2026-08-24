# F-03 双源凭证审计报告（只读审计 · 留档）

> **审计日期**：2026-08-24
> **审计性质**：Step 1 只读审计（零代码修改），作为 F-03 统一凭证源方案的设计依据
> **Scope 限定**：Telegram 渠道（Token / ChatID）；其他渠道同类问题列入 §2.3.6 范围外发现
> **关联**：《事件通知全链路审计报告》F-03 条目；`pilotstd/core/notification/_format_utils.py` 改造依据

---

## 2.3.1 凭证读取点清单

| # | 凭证读取点 | 文件:行号 | 读取源 | 读取时机 | 配置热更新响应 | 服务路径 | Mock/Stub 证据 |
|---|-----------|----------|--------|---------|---------------|---------|---------------|
| R1 | `do_test_send` Telegram 分支 | `_format_utils.py:60-71`（改造前） | **config.json**（`mgr._cfg.get(...)`） | 每次调用动态读（仅当 `_channels` 未命中） | ✅ 即时 | 测试路径 | `tests/test_format_utils.py:112-159` 注入 config 值，未覆盖 DB 源 |
| R2 | `_init_channels` Telegram 分支 | `manager.py:172-176` | **DB**（`cred_helper.get_all`） | 启动缓存 + PUT 后重建 | ✅ 重建生效 | 事件路径 | `tests/test_notification_manager_extended.py:26,37` mock CredentialHelper |
| R3 | `GET /api/notification/config` | `docker/api/notification.py:46-47` | **DB** | 每次 API 动态读 | ✅ 即时 | 双重服务 | — |

## 2.3.2 凭证传递链路差异

- **路径 A（do_test_send）**：`POST /api/notification/test` → `test_send` → `do_test_send` → L53 查 `_channels` 缓存 → 未命中 → **config.json 直读** → `TelegramChannel(token, chat_id)` → send
- **路径 B（事件路径）**：`send_event` → `_do_send` → 聚合 → `_send_now` → `_channels.get("telegram")`（启动时 R2 从 **DB** 初始化）→ send

| 维度 | 路径 A | 路径 B | 一致性 |
|------|--------|--------|--------|
| 凭证源 | config.json | DB | ❌ 不一致 |
| 读取时机 | 每次动态读 | 启动缓存 + 重建 | ⚠️ 部分不一致 |
| 传递方式 | 即时构造（用完即弃） | 缓存复用 | ❌ 不一致 |
| 热更新 | ✅ 即时 | ✅ 重建生效 | ✅ |

**【P0-时序不一致】**：R1（动态读 config）与 R2（缓存 DB）不同步，触发条件 = "渠道未在 `_channels` + config 有值 + DB 有不同值"三条件同时成立。

## 2.3.3 根因推断（两层）

| 层级 | 内容 |
|------|------|
| 直接原因 | `_format_utils.py:62,65`（config 直读）vs `manager.py:163`（DB 读取）两处独立读取；PUT 只写 DB 不写 config（`docker/api/notification.py:112-116`）导致两源必然不一致 |
| 根本原因 | 缺少统一凭证提供者；DB↔config 仅单向空表回退（`_credentials.py:43-48`），无双向同步；测试只覆盖 config 源（O-5） |

## 2.3.4 凭证存储位置与优先级链

```
1. [最高] user_credentials 表（DB，Fernet 加密）——事件路径唯一来源（manager.py:163）、
          Web 保存唯一写入目标（docker/api/notification.py:116）
2. [次高] config.json notification.channels.telegram——仅 DB 空表回退（_credentials.py:43-48）
          + 改造前 do_test_send config 直读（_format_utils.py:62,65）
3. [最低] FACTORY_DEFAULTS（defaults.py:57-59）
（环境变量：无 Telegram 通道，审计确认）
```

## 2.3.5 审计结论与建议摘要

两条路径核心差异是凭证源分离（DB vs config.json），PUT 只写 DB 导致两源可长期不一致；最大风险点是 `_format_utils.py:62,65` config 直读绕过 `CredentialHelper` 统一抽象。建议以 DB 为 SSOT，`do_test_send` 改用 `CredentialHelper.get_channel()`，config.json 降级为首次启动引导源（保留空表回退），删除 config 运行时直读。

## 2.3.6 范围外发现

| # | 渠道/模块 | 文件:行号 | 问题 | 级别 | 处理 |
|---|----------|----------|------|------|------|
| O-1 | 钉钉/飞书/企微 | `_format_utils.py:72-110` | 同 R1 config 直读模式 | P2 | **纳入方案一并修复** |
| O-2 | 通知模块 | `manager.py:86-89` | CredentialHelper 初始化异常被吞 | P2 | 不纳入（F-04 已知） |
| O-3 | Web 配置 | `docker/api/notification.py:49-50` | mask() 回显靠 set_channel 掩码过滤兜底 | P3 | 不纳入 |
| O-4 | CredentialHelper | `_credentials.py:43-48` | get_all 空表回退含写操作副作用 | P3 | 不纳入 |
| O-5 | 测试 | `tests/test_format_utils.py` | 测试仅覆盖 config 源 | P2 | **纳入方案**（新增 DB 源交叉测试） |
| O-6 | 配置模块 | `priority.py` | PriorityConfigManager 与通知凭证脱节 | P3 | 不纳入 |

---

*本报告为只读审计留档，实施依据见设计方案（Step 2）与改动清单。*
