# 批次 2 数据迁移授权包（G-28 / G-33 / G-35）

> **状态**：脚本已就绪，**等授权**。本文件给出「演练 → 取证 → 授权 → 全量 → 回滚」的完整可执行流程。
> **风险等级**：中（写生产库）。**必须**先演练、看数据、再授权。
> 关联台账：`docs/debt/03-open.md` 的 G-28 / G-33 / G-35；实施记录 `docs/onboarding/27` #97。

---

## 一、问题是什么

`announcement_record.superseded_by` 现在的语义写反了：

- **现状**：`新标准.superseded_by = 旧标准`（"本行替代了谁"）
- **应然**：`旧标准.superseded_by = 新标准`（"本行被谁替代"）

2026-11-21 生产抽样 4,000 行实测：**方向倒退 3,695 行（92%）**，已是正向仅 1 行。

**影响面**：DB 内 92% 的「被替代」关系失效 —— 查「这条标准是否已被替代」会得到错误结论。

---

## 二、为什么不能直接改

100 条抽样里，**67 条目标旧标准行的 `superseded_by` 已经有值**（且实测无一条正向，
本身也是乱的）。直接覆盖会**丢掉原信息**。

所以脚本的规则是：

| 情形 | 动作 |
|---|---|
| `sup` 为空 | 跳过 |
| `year(sup) < year(std)`（方向倒退） | 把 `std.superseded_by` 里**这一条**去掉 |
| 目标旧标准行 `superseded_by` **为空** | 写入 `std`（仅空才写） |
| 目标旧标准行 `superseded_by` **已有值** | **不动**（交给清洗流程，不覆盖） |
| `year(sup) >= year(std)`（已正向） | 保持不动 |
| 多值（逗号分隔） | 逐条拆分，只去掉倒退的那几条 |

---

## 三、执行流程（在**部署主机**上跑，不是开发机）

> 部署目录假设为 `/opt/pilotstd`（`docker-compose.yml` 与 `data/` 同级）。
> 生产库在宿主机的 `data/pilotstd.db`（compose 挂载 `./data:/app/data`）。

### 第 0 步：确认库路径与备份

```bash
cd /opt/pilotstd
ls -la data/pilotstd.db
cp data/pilotstd.db data/pilotstd.db.before-superseded-migration   # 文件级备份
```

### 第 1 步：只读统计（**不写库**）

```bash
python3 scripts/migrate_superseded_by_direction.py \
  --db data/pilotstd.db --check-existing
```

**看什么**：输出「目标旧标准行统计：总数 N｜方向正确 x｜本身倒退 y｜无法判年 z｜为空 w」。

- `为空` 的数量 = 本次能安全写入的目标行数
- 若 `总数 = 0` → 该库没有可迁移数据（可能是空库/开发库，**停止，确认连对库了**）

### 第 2 步：小批量演练（**不写库**，`--limit 100`）

```bash
python3 scripts/migrate_superseded_by_direction.py \
  --db data/pilotstd.db --limit 100
```

**看什么**：输出「待处理行 N，将清掉倒退值 M 条」+ 前 5 条样例
（形如 `样例 #123 GB 50011-2016: GB 50011-2010 -> (空)`）。

**判据**：样例必须符合「清掉倒退、保留正向」的预期。若样例看起来不对，**停止**并回报。

### 第 3 步：全量演练 + 写出计划（**不写库**）

```bash
python3 scripts/migrate_superseded_by_direction.py \
  --db data/pilotstd.db --json /tmp/superseded-plan.json
```

`/tmp/superseded-plan.json` 是**完整变更计划**（含每行的 before/after/dropped/targets），
也是后续回滚的依据。**先把这个文件发给负责人审阅**。

### 第 4 步：授权后执行（**写库**）

```bash
python3 scripts/migrate_superseded_by_direction.py \
  --db data/pilotstd.db --json /tmp/superseded-apply.json --apply
```

**脚本会自动**：
1. 先建列级备份表 `announcement_record_bak_<yyyymmdd>`
2. 再按计划写库
3. 输出「列级备份表: <表名>」「已清理 N 行，补写空值目标 M 行」

**立即记录备份表名**（回滚要用）。

### 第 5 步：验证

```bash
# 5.1 方向倒退应显著下降（脚本重跑演练，看「将清掉倒退值」是否接近 0）
python3 scripts/migrate_superseded_by_direction.py --db data/pilotstd.db --limit 0

# 5.2 目标行被覆盖数应为 0（本次规则是「仅写空值」）
python3 scripts/migrate_superseded_by_direction.py --db data/pilotstd.db --check-existing
```

**验收判据**：
- 方向倒退从 **92% → 接近 0%**
- `check-existing` 的「为空」数应明显下降（说明空值被补写了）
- 「本身倒退」不应增加（没有引入新的乱值）

### 回滚（若发现问题）

```bash
python3 scripts/migrate_superseded_by_direction.py \
  --db data/pilotstd.db --rollback /tmp/superseded-apply.json --apply
```

回滚依据是**计划 JSON**（含每行原始值），按 `id` 还原。

---

## 四、为什么需要你授权（而不是我直接跑）

1. **写生产库** —— 项目红线：涉及生产写库需维护窗口。
2. **67% 目标行有既有乱值** —— 脚本选择「不覆盖」，但**哪些该保留、哪些该清洗**
   属业务判断，需要你（或数据 owner）确认口径。
3. **生产库在另一台机器**（`192.168.1.18`）—— 本机是开发机，无该库的完整数据，
   无法在本地做有意义的演练（本地 `data/pilotstd.db` 实测「目标旧标准行总数 0」）。

---

## 五、给授权决策的最小信息集

跑完第 1~3 步后，把这三项发我/负责人即可决策：

1. `--check-existing` 的五个数字（总数 / 方向正确 / 本身倒退 / 无法判年 / 为空）
2. 全量演练的「待处理行 N，将清掉倒退值 M 条」
3. 计划 JSON 的前 5 条样例

---

## 六、脚本不在镜像内（注意）

`docker/Dockerfile` **不 COPY `scripts/`**，所以迁移脚本**不在容器里**。
必须在**部署主机的仓库目录**执行（compose 挂载了 `./data:/app/data`，宿主机能直接访问 DB）。

若部署主机没有仓库代码，用：
```bash
docker cp scripts/migrate_superseded_by_direction.py pilotstd:/tmp/
docker exec -it pilotstd python /tmp/migrate_superseded_by_direction.py \
  --db /app/data/pilotstd.db --check-existing
```
（`--apply` 时同理，注意 `--json` 路径在容器内，需 `docker cp` 出来留档。）
