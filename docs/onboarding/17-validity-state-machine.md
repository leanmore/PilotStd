# 17 · 有效性 L1/L2/L3 状态机

> 来源：`pilotstd/core/validity_checker.py`、`pilotstd/core/_validity_pipeline.py`，2026-11-07 实测。  
> 一句话：**L1 公告、L2 实时查询、L3 历史**；只有 L2 + `auto_move_expired=true` 才有资格搬文件。

---

## 一、三层检查

| 层 | 数据源 | 命中条件 | evidence | 副作用 |
|---|---|---|---|---|
| **L1** | `announcement_match.result_json.status` / `announcement_record.std_name` 关键词 | 只信**否定**（废止/作废/被代替）；名称含废止类词 | `L1` | **不允许**搬文件/入下载队列 |
| **L2** | `QueryEngine.query_standards()` 实时/缓存查询 | 查到结果 `is_found()`；`status` 空则按“现行” | `L2` | 只有 `validity.auto_move_expired=true` 才允许搬文件/入队 |
| **L3** | `standard_validity` 历史行 | 有历史行就返回其 `status`/`last_status` | `L3` | **不允许**搬文件/入队 |

### 关键细节

- L1 **不把“公告里出现过”当现行证据**，否则 L2 永远没机会查真实状态；
- L1 名称关键词只作为“废止”的**正证据**，保守判定；
- L2 的 `query_engine` 为空时不可达（只剩 L1/L3）；
- L3 是“自我确认”：如果历史一直是未知，下一轮仍返回未知，不会自己变成废止；
- L2 查询会走 `QueryEngine` 缓存，**缓存不新鲜会直接影响有效性判断**（见 Q7）。

---

## 二、状态更新

`update_status(standard_number, new_status, evidence)`：

| 场景 | 行为 |
|---|---|
| 无历史行 | `INSERT`：status、last_checked_at、next_check_at、last_changed_at、check_count=1 |
| 状态未变 | `UPDATE`：last_checked_at、next_check_at、check_count+1、updated_at |
| 状态变化 | `UPDATE`：status、last_checked_at、next_check_at、last_status=旧状态、last_status_updated_at、last_changed_at、check_count+1、updated_at；发 `standard_status_changed` |
| 变成废止且允许副作用 | **先搬文件**；全部成功才写库；任一失败则回滚并保持原状态 |
| 变成废止但不允许副作用 | 只写状态；日志说明“需 L2 + auto_move_expired” |

### 下次检查时间

```text
next_check_at = now + validity.total_weeks * 7 天
```

- 默认 `total_weeks=4`（28 天）；
- 线上 `total_weeks=8`（56 天）；
- 归档新标准 `register_new_standard` 时 `next_check_at=now`，所以会立即进入抽查。

---

## 三、采样与批次

| 项 | 事实 |
|---|---|
| 候选 | `next_check_at <= now`，排除 `file_index` 中已在“过期作废”的路径 |
| 采样 | `ceil(total_due * check_ratio / 100)`，数据库 `ORDER BY RANDOM() LIMIT` |
| 默认 `check_ratio` | 25 |
| 线上 `check_ratio` | 12 |
| 批次 | `batch_size=50`、`batch_interval=5s`、`l2_concurrency=3` |
| 并发 | 只并发网络查询；DB 写入主线程串行 |
| 锁 | `_VALIDITY_LOCK` 非阻塞；并发触发返回“检查正在执行中” |

---

## 四、副作用

`should_apply_side_effects(evidence)`：

```text
evidence == "L2"
AND validity.auto_move_expired == true
```

满足时：

1. 把 `file_index` 中该标准（按 code/number/year/part）的文件移到“过期作废”；
2. 排除修改单/已在过期目录的文件；
3. 任一文件移动失败 → 回滚已移动文件，返回失败，**不写废止状态**；
4. 全部成功 → 回写 `file_index.file_path/status`；
5. 若是 GB 替代标准 → `_enqueue_gb_replacement` 写入 `download_queue`。

---

## 五、通知

| 事件 | 时机 |
|---|---|
| `standard_first_registered` | 归档后首次注册 |
| `standard_status_changed` | 状态变化；废止/被代替都走它，`is_expired` 区分 |
| `validity_batch_report` | 每批结束；`_apply_validity_result` 每 10 条变化还会发一次 |
| `validity_round_summary` | `checked_count >= 合法标准总数` 时 |
| `validity_standard_failed` | 单条检查异常 |
| `validity_system_failed` | 整轮异常 |

> `validity_batch_report` 的“每 10 条变化”分支里 `count=0, changed=10` 是硬编码，和最终批次报告不一致；记录为细节。

---

## 六、当前已知问题

1. **`validity_check_queue` 表不存在**：`/api/validity/enqueue` 实际不可用；
2. **`checked_count` 只有定时任务 `update_counters=true` 才增加**；手动 `/api/validity/run` 不增加，所以线上可能“历史有记录、计数为 0”；
3. **畸形键**：`' 11120-2011'` 这类行无法解析，L1/L2 都不会真正处理；`_finalize` 的分母只统计 `GLOB '[A-Z]*'`，避免被它们卡住；
4. **L3 自证循环**：历史未知 → L3 未知 → 继续未知；没有 L1/L2 证据就不会自行变废止；
5. **L2 受查询缓存影响**：Q7 的 stale cache 会让 L2 拿到旧状态。

---

## 七、一句话记忆

> L1 看公告（只信坏消息）→ L2 问网站（唯一能搬文件）→ L3 看历史（不改命）；  
> 搬文件必须 L2 + 开关；否则只更新状态。
