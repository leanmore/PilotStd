# 28 · A 阶段完成情况与部署手册

> A 阶段定义：**本地代码 + 测试 + 迁移 + dry-run + 部署/执行手册；不碰生产。**  
> 本文是 A 阶段的收口记录；生产动作属于 B 阶段，需维护窗口。

---

## 一、A 阶段已完成

| 项 | 状态 | 关键文件 |
|---|---|---|
| Web 下载成功件进入归档 | 已改 | `web/src/views/TaskView.vue` |
| 通知未读数/全部已读按用户隔离 | 已改 | `_manager_ops.py`、`notification_logs.py` |
| monitor manager 锁 + 空目录清理 | 已改 | `monitor/scheduler.py` |
| hcno 历史注释 | 已改注释 | `query/models.py` |
| 查询缓存 stale 不命中 + put 置 fresh | 已改 | `query/cache.py` |
| v74 修复 709 条 validity 畸形键 | 已实现 + 副本 dry-run | `_migrate_v74_repair_validity_keys.py` |
| v2 采样 `v2_skipped` | 已加 | `router_v2_metrics.py`、`_single.py` |

---

## 二、测试结果

| 检查 | 结果 |
|---|---|
| `pnpm run type-check` | 通过 |
| `pnpm run lint` | 0 errors，283 warnings（存量） |
| `pnpm test` | 352 passed |
| `pnpm run build` | 通过 |
| 通知 + monitor + query + v2 + v74 组合 | 94 passed |
| 迁移链测试 | 134 passed |
| `ruff` 改动 Python | 通过 |

---

## 三、v74 数据迁移（部署时自动执行）

### 行为

- 只修复能由 `file_index` 唯一确定的行；
- 705 条修复（704 改名 + 1 合并）；
- 4 条无法唯一还原保留：
  - `' 19001-2020'`
  - `' 47008-1947'`
  - `' 47019-2011'`
  - `' 47013-2015'`（part=-1/.2 歧义）
- 幂等：第二次执行不再匹配畸形正则。

### 副本 dry-run 结果

```text
schema 73 -> 74
行数 803 -> 802
畸形键 709 -> 4
```

> 只在 `C:\Temp\pilotstd_v74_dryrun.bak` 副本上执行；生产未执行。

---

## 四、B 阶段部署步骤（需维护窗口）

### 1. 部署前

1. 备份生产 `data/`（SQLite backup API，不要只 copy WAL 状态）；
2. 记录 `/api/health` 的 `version` 和 schema；
3. 准备回滚：旧镜像 tag + 备份 DB；
4. 通知用户维护窗口。

### 2. 更新镜像

```text
停止旧容器
替换为 A 阶段 commit 构建的新镜像
启动
```

### 3. 启动后必查

```text
GET /api/health
- version = 新版本
- schema_version = 74
- database_rw = true
- scheduler heartbeat 正常
```

再查：

```sql
SELECT COUNT(*) FROM standard_validity WHERE standard_number GLOB ' *';  -- 应为 4
SELECT standard_number, COUNT(*) FROM standard_validity GROUP BY standard_number HAVING COUNT(*)>1; -- 应为 0
```

### 4. 缓存注意

- 线上 `standard_info_cache` 当前 517 条全部 stale；
- 新代码会跳过 stale，首次查询会回源；
- 预计首日网络查询量上升，观察日志与适配器配额；
- 如回源压力过大，先暂停批量查询，不要回滚“stale 当命中”。

### 5. 回滚

```text
停新容器
恢复旧镜像 tag
用部署前 DB 备份替换
启动
GET /api/health 确认
```

> v74 没有 down migration；回滚 = 恢复 DB 备份，不写反向 UPDATE。

---

## 五、B 阶段验证（Docker 更新后）

1. 用局域网 Docker 的验证实例，不要用生产；
2. 跑 1 条已知标准查询，确认 v2 / v1 路由；
3. 跑 20 条小样本，确认无 `chain_exhausted`；
4. 确认 `logs/router_v2_decisions.jsonl` 有 v2/v2_skipped 记录；
5. 再跑 ≥1000 条真实查询（ADR-015 阈值）；
6. 生产数据修复在维护窗口执行，不在验证环境做生产库。

---

## 六、A 阶段未做 / B 阶段处理

- D-04 通知聚合：未读数已修；11/7 批次日志缺失、聚合批次键待查；
- D-02 monitor：只加锁 + 空目录清理，未扩查询/下载/兜底；
- D-01 后端重复/覆盖策略：前端已去重，后端仍需确认；
- D-05 真实 1000 条 v2 样本：本地查询 `chain_exhausted`，待 Docker 验证环境；
- D-03 “过期作废”实际产出：迁移修键，但不等于自动产生废止状态；B 阶段用真实数据验证；
- 生产部署、生产数据库修复：**未执行**。
