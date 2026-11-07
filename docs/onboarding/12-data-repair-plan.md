# 12 · 历史数据修复方案（仅方案，不执行）

> 对象：`standard_validity` 中 `' <number>-<year>'` 形态的畸形键。  
> 状态：**方案已批准（2026-11-07）；v74 迁移已实现并在 prebatch 副本 dry-run**。  
> 生产执行仍需验证环境演练 + 维护窗口；本文不包含生产执行命令，也不代表生产已修复。

---

## 一、事实基线

数据源：`C:\Temp\pilotstd_live_logs\prebatch.bak`（批次前备份，只读分析）。

| 项 | 数量 |
|---|---:|
| `standard_validity` 总行数 | 803 |
| 畸形键 `' <number>-<year>'` | 709 |
| 可由 `file_index` 唯一还原 | 705（704 唯一改名 + 1 冲突合并） |
| 其中与已存在的规范键冲突 | 1（`NB/T 47014-2011`） |
| 无法唯一还原 | 4（3 无匹配 + 1 分部歧义） |
| 状态分布 | 未知 746 / 现行 43 / 即将实施 14 / 废止 0 |

无法唯一还原的 4 条：

| 畸形键 | 原因 |
|---|---|
| `' 19001-2020'` | 只有 `GB/T 19001-2016` |
| `' 47008-1947'` | 只有 `NB/T 47008-2010/2017` |
| `' 47019-2011'` | 只有 `NB/T 47019-2021` |
| `' 47013-2015'` | `file_index` 同时有 `part=-1` 与 `part=2`，分部歧义 |

**结论**：不能按“同 number 的最新版本”自动猜，否则会把旧标准的状态挂到新标准上。这 4 条只能人工判断或保留。

### 第二轮只读核对（2026-11-07）

| 检查 | 结果 |
|---|---|
| 可还原 | 705 = 704 唯一改名 + 1 冲突合并 |
| 无法唯一还原 | 4（3 无匹配 + 1 分部歧义） |
| 歧义 | 0 |
| 映射后重复键 | 0 |
| 模拟合并后总行数 | **802**（803 − 1 合并删除） |
| `file_index` 同 `(number, year, part)` 重复 | 12 组，但同组代号一致，不造成键歧义 |

> 这 12 组 `file_index` 重复是“同一标准多副本/多路径”，不是映射歧义；按“唯一 `logical_code`”判定仍是唯一的。

### 2026-11-07 v74 副本 dry-run

| 项 | 结果 |
|---|---|
| 输入 | `C:\Temp\pilotstd_v74_dryrun.bak`（prebatch 副本） |
| schema | 73 → 74 |
| 行数 | 803 → 802 |
| 畸形键 | 709 → 4 |
| 保留 | `' 19001-2020'`、`' 47008-1947'`、`' 47019-2011'`、`' 47013-2015'`（分部歧义） |
| 合并 | `NB/T 47014-2011`（check_count 取 max、last_checked 取较新） |

> 没有在生产库上执行；生产仍需维护窗口。

---

## 二、修复目标

1. 把 705 条可还原键改为规范标准号（含 1 条冲突合并）；
2. 1 条冲突行合并到已有规范行，不丢检查历史；
3. 4 条无法唯一还原的行保持原样，输出清单人工处理；
4. 全程可 dry-run、可回滚、可审计；
5. 不在生产直接 `UPDATE`；先方案批准，再按迁移/脚本流程执行。

---

## 三、映射规则

### 1. 解析畸形键

```text
^\s+(\d+)(?:\.(\d+))?-(\d{4})$
```

得到 `(number, part, year)`。

### 2. 用 file_index 还原代号

按 `(number, year, part)` 查 `file_index`：

- 只有一个不同 `logical_code` → 还原为 `"{logical_code} {number}[.part]-{year}"`；
- 多个不同代号 → 歧义，停下人工处理；
- 没有记录 → 无法还原，保留。

### 3. 规范键生成

必须复用项目已有的标准号归一化逻辑，不另写一套字符串拼接；生成后再与 `standard_validity.standard_number` 比对。

---

## 四、合并策略（仅 1 条冲突）

以 `NB/T 47014-2011` 为例：

| 字段 | 畸形行 | 规范行 | 建议 |
|---|---|---|---|
| `status` | 未知 | 未知 | 保留非未知；都未知则保留规范行 |
| `last_checked_at` | 2026-09-09 | NULL | 取较新非空 |
| `next_check_at` | 2026-11-04 | 2026-10-01 | 取“最近一次检查行”的下次时间，避免把已检查进度退回 |
| `check_count` | 1 | 0 | 取 max，不求和 |
| `created_at` | 2026-07-20 | 2026-10-01 | 取更早 |
| `updated_at` | 2026-09-09 | 2026-10-01 | 取较新 |
| `data_state` | stale | stale | 任一 fresh 则 fresh；否则 stale |
| `last_status` | NULL | NULL | 取非空 |

**通用规则**：

1. 身份字段以规范键为准；
2. 状态优先非未知；两个都已知且不同，取 `last_checked_at` 较新者，仍相同则保留规范行并记冲突；
3. 时间字段：`last_checked_at`/`updated_at`/`last_changed_at` 取较新；`created_at` 取较早；
4. `next_check_at`：优先跟随 `last_checked_at` 较新的行；没有检查记录时取较早者（更早复检更安全）；
5. `check_count` 取 max；
6. 合并后删除畸形行，保留规范行 id；
7. 全过程写审计日志 + 映射 CSV。

---

## 五、执行步骤（批准后才做）

### Step 0：冻结与备份

- 停写或进入维护窗口；
- 备份当前 DB（SQLite backup API，不是直接 copy WAL 状态）；
- 记录 schema 版本、行数、max(id)。

### Step 1：Dry-run

输出：

```text
total_malformed=709
recoverable=705（704 改名 + 1 合并）
unrecoverable=4（3 无匹配 + 1 分部歧义）
```

并输出 `mapping.csv`：

```text
old_key,new_key,action,source_id,target_id,reason
```

**dry-run 不写库。**

### Step 2：事务执行

- 单事务；
- 704 条 `UPDATE standard_number`；
- 1 条合并：先更新规范行字段，再删除畸形行；
- 4 条跳过（3 无匹配 + 1 分部歧义）；
- 提交前断言：
  - 畸形键只剩 4 条；
  - 规范键无重复；
  - 总行数 = 803 - 1（合并删除）= 802；
  - 无 `UNIQUE constraint failed`。

### Step 3：验证

```sql
SELECT COUNT(*) FROM standard_validity
WHERE standard_number GLOB ' ?*-*';  -- 应为 3

SELECT standard_number, COUNT(*)
FROM standard_validity
GROUP BY standard_number
HAVING COUNT(*) > 1;  -- 应为 0
```

再抽样 10 条，和 `file_index` 对照。

### Step 4：回滚

- 保留备份 + mapping.csv；
- 回滚 = 停服务、替换备份、启动校验；
- 不写“反向 UPDATE”脚本，避免二次污染。

---

## 六、防复发（比修数据更重要）

1. **归档入口**：写 `standard_validity` 前必须用规范标准号；禁止直接用前端传入的 `logical_code` 拼键；
2. **Word 重解析**：修空 `scan.code_mapping`，避免 `TSG → T/SG`；
3. **唯一键冲突**：`register_new_standard` 用 `INSERT OR IGNORE` / `ON CONFLICT`，不要 `SELECT + INSERT`；
4. **迁移校验**：新增迁移必须带 dry-run 断言和 `_migration_checksum` 保护；
5. **测试**：补“畸形键修复/冲突合并/无法还原保留”三类测试。

---

## 七、已确认的决策（2026-11-07）

1. 4 条无法唯一还原的行：**保留，人工处理**，不按“同 number 最新版本”猜；
2. 1 条冲突行：**接受合并策略**（检查次数多、时间新优先）；
3. 修复方式：**v74 迁移**，必须支持 dry-run；
4. 执行环境：**先验证环境演练，生产另排维护窗口**。

> 执行前仍需：备份、dry-run、`mapping.csv`、提交前断言、回滚方案。
