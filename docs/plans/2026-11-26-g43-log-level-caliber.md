# G-43 核实结论：通知日志 level 计数口径（两时点分布定论，2026-11-26）

> 台账原疑点（`docs/debt/03-open.md` G-43）：「通知日志 info/warning 计数口径是否偏差，待核实（缺两时点分布）；
> 上批『新增 2 条 info』解释自相矛盾」。
> 核实方式：**只读**生产库聚合 + 复用 `docker/api/notification_logs.py::_business_level` 同款规则。

## 1. 取数（生产只读）

SQL（`POST /api/query`，`2026-11-20` 起）：

```sql
SELECT substr(sent_at,1,10) AS d, event_type, notify_event, channel, status, COUNT(*) AS c
FROM notification_log WHERE sent_at >= '2026-11-20'
GROUP BY d, event_type, notify_event, channel, status
```

共 **61** 个聚合行；按 `_business_level` 归并后按天分布：

| 日期 | info | warning | error | 合计 |
|---|---:|---:|---:|---:|
| 2026-11-26 | 2 | 0 | 0 | 2 |
| 2026-11-25 | 12 | 2 | 0 | 14 |
| 2026-11-24 | 8 | 0 | 0 | 8 |
| 2026-11-23 | 10 | 0 | 0 | 10 |
| 2026-11-22 | 8 | 3 | 0 | 11 |
| 2026-11-21 | 10 | 0 | 0 | 10 |
| 2026-11-20 | 12 | 6 | 0 | 18 |

## 2. 事件 → 级别映射（全量，无歧义）

| event_type | notify_event | 级别 | 条数 |
|---|---|---|---:|
| `announce_fetch_summary` | user_activity | info | 12 |
| `announcement_fetch_complete` | user_activity | info | 12 |
| `auto_backup` | task_result | info | 2 |
| `batch_summary` | batch_summary | info | 2 |
| `daily` | user_activity | info | 18 |
| `scan_empty` | task_result | info | 14 |
| `schedule_reminder` | schedule_reminder | info | 2 |
| `security_alert` | security_alert | warning | 11 |

**关键判定**：窗口内**每个 `event_type` 只对应一个级别**（无「同一事件按分支产生 info/warning/error」的情况）
⇒ 级别推导无歧义，`info` 计数不可能因推导顺序而漂移。

## 3. 结论（三条定论）

1. **口径一致**：列表 `/api/notification/logs` 与分布 `/api/notification/logs/stats/distribution`
   共用同一个 `_business_level` 函数（代码注释与实现均在案），不存在两套计数；
2. **两时点可解释**：11-23（info=10、warning=0）与 11-25（info=12、warning=2）的差异可由
   `security_alert`（11-25 出现 2 条）与 `daily`/`scan_empty` 的当日执行次数解释，**无异常跳变**；
3. **「新增 2 条 info」不再矛盾**：该数字对应 `batch_summary` + `schedule_reminder` 两条真实事件；
   旧口径把聚合行 `event_type` 与类别名比较导致 level 恒 info（D7-3 已修），现按「唯一级别直取」判定。

## 4. 已知边界（不改数据，登记即可）

`notification_log` **无 level 列**，级别在读取时推导；若将来出现「同一事件多级别」的写法，
推导只能落到类别映射（`task_failure→error` / `security_alert|anomaly_alert→warning`）。
彻底消除需加列迁移——当前数据无此形态，不为此单独迁移。

## 5. 状态

**G-43 已核实闭合**（口径无偏差，两时点分布已取证；无需代码改动）。
