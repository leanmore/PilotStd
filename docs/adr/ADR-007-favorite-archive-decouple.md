# ADR-007: 收藏与归档下载解耦

> 日期：2026-07-20
> 状态：✅ Accepted
> 关联：[[ADR-004]]

---

## 背景

Phase 4a 收藏功能最初设计为：用户收藏标准 → 后端立即通过 `BackgroundTasks` 触发 `download_to_inbox` 后台下载 → 前端轮询下载状态 → 成功则归档，失败则弹 Toast 报错。

实际运行中发现两个问题：
1. **用户体验差**：收藏操作的预期是"标记感兴趣"，但实际行为包含了即时下载。下载失败时用户看到"归档失败"Toast，误以为收藏操作本身失败了。
2. **无重试机制**：下载失败后无自动重试，用户需手动取消再收藏才能重新触发。

---

## 决策

**收藏 = 预定关系，与下载/归档完全解耦。**

### 新模型

```
收藏 API (POST /api/favorites)
  → 仅创建 user_favorites 记录（status='pending'）
  → 写入 publish_date 用于冷却期计算
  → 不触发任何下载任务

定时任务 (APScheduler, 每天 04:00)
  → 扫描 status IN ('pending','failed') 的记录
  → 冷却期判断：publish_date + 28 天（可配置）
  → 每批最多 20 条，公平调度
  → 每条最多重试 7 次（可配置）
  → 7 次后标记 abandoned 并通知用户
```

### 配置参数（环境变量）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ARCHIVE_COOLDOWN_DAYS` | 28 | 发布后冷却天数 |
| `ARCHIVE_MAX_RETRIES` | 7 | 最大重试次数 |

### 状态机

```
pending ──(冷却期满)──→ downloading ──(成功)──→ done
   │                        │
   │                        └──(失败, retry<7)──→ failed ──(下次定时)──→ downloading
   │                        └──(失败, retry≥7)──→ abandoned ──→ 通知用户
   │
   └──(冷却期内)──→ 前端显示"等待上线"
```

### 前端展示规则

| 状态 | Tag 文案 | 颜色 |
|------|---------|:---:|
| 冷却期内 | 等待上线 | info |
| pending | 待归档 | info |
| downloading | 下载中 | info |
| archiving | 归档中 | info |
| done | （星标实心，无Tag） | — |
| failed | 归档失败 | danger |
| abandoned | 归档已放弃 | warn |

### 用户操作限制

- 已收藏（任意非 failed/abandoned 状态）：不可重复收藏，点击无效
- failed/abandoned 状态：允许重新点击星标触发一次新收藏（重置状态）
- 取消收藏：仅在 done 状态时可用，直接删除记录

---

## 影响范围

| 层次 | 文件 | 变更 |
|------|------|------|
| API | `docker/api/favorites.py` | 移除 BackgroundTasks + download_to_inbox；status 端点返回 in_cooldown/abandoned |
| 服务 | `pilotstd/manager/archive_retry_service.py` | **新建** — 定时重试调度 |
| 调度器 | `docker/scheduler.py` | 新增 auto_archive_retry cron job |
| 门面 | `pilotstd/manager/facade/_base.py` | 初始化 + @property |
| 数据库 | `user_favorites` 表 | 新增 publish_date/last_archive_attempt/archive_retry_count |
| 前端 | `useFavorite.ts` | 删除轮询、归档 Toast；favLabel 补 already_exists |
| 前端 | `AnnounceDetail.vue` | 5 种状态 Tag 展示；悬浮按钮纯图标化 |
| 前端 | `AdapterStatusCard.vue` | console.warn 兜底日志 |

---

## 后果

**正面**：
- 收藏操作即时响应，不再受下载速度/失败影响
- 标准化产品发布后 28 天才归档符合业务逻辑（避免下载草案版本）
- 自动重试降低运维成本

**负面**：
- 用户收藏后最长需等 28 天 + 下次定时任务才完成归档
- 定时任务失败需人工排查日志（已有 abandoned 通知兜底）

---

## 现状注记（2026-09-13）

本 ADR 的决策仍然有效；实现位置与参数有变动，以现状为准：

- 实现已从 `pilotstd/manager/archive_retry_service.py`（死代码，2026-09-13 删除，见 commit `fa597af6`）迁至
  `pilotstd/services/favorite_chain_processor.py`（APScheduler `auto_archive_retry` cron → `process_chain()`）。
- 重试上限：活跃链自 2026-08-22（`2af79a3d`）建立时取 3 次，2026-09-13 改回本 ADR 的 7 次
  —— `MAX_RETRIES = 7`（模块常量，7 天兜底窗口）。
- `ARCHIVE_MAX_RETRIES` 环境变量已随死代码移除，**不再是配置项**；`ARCHIVE_COOLDOWN_DAYS`（默认 28）仍生效。
- 上面"每批最多 20 条"已取消：一轮处理全部到期记录，节流改由下载引擎节奏（batch_size / max_workers / long_rest）负责。

