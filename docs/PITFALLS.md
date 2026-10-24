# 运维陷阱记录（PITFALLS）

> 记录"踩过一次、下次换机器/上 CI 还会再踩"的环境级陷阱。每条给：现象、机制、证据、正确做法。
> 与 `docs/debugging` 类文档不同：这里只收**环境/操作**陷阱，不收业务缺陷。

---

## P-01 空库原地重建停在 v37（2026-10-24）

### 现象

删除 `data/pilotstd.db` 后让程序重建，迁移链停在 **v37**：`_schema_version` 最大版本 37、只有 33 张表、
`announcement_record` 缺 `language`/`foreign_name` 列。随后任何用到该库的测试/命令都报
`no such table` 或 `checksum 不匹配`。

### 机制（为什么停在 v37）

`Database._run_migrations()` 按版本号**逐个**执行；任一迁移抛异常即 `raise DatabaseError` 并终止：

```python
for v in range(current + 1, target + 1):
    MIGRATIONS[v](self)      # 失败 → DatabaseError，后续版本不再执行
    INSERT INTO _schema_version ...
```

所以"停在 v37"等价于"**v38 没跑成 / 初始化被中断**"，不是 v37 本身有问题。

### 当时环境（与干净重建的差别）

| 项 | 当时 | 干净条件 |
|---|---|---|
| `data/pilotstd.db-wal` | 残留 1.8 MB（旧库的 WAL） | 不存在 |
| `data/pilotstd.db-shm` | 残留 | 不存在 |
| `data/pilotstd.db.migration_lock` | 存在（5 字节） | 不存在 |
| 后台任务 | 刚跑完全量测试（大量 `Database` 实例） | 无 |

### 复现结论（重要）

**未能稳定复现**，三次对照均到达 v70：

1. 临时目录空库 → 70；
2. `data/` 目录新路径空库 → 70；
3. 带旧 `-wal`/`-shm`、只删主库 → 70（SQLite 检测 salt 不匹配会丢弃旧 WAL）。

故判定为**一次性环境异常**（残留锁 + 并发打开），不是迁移脚本缺陷、也不是必然断点。
但这不改变下面两条做法——它们能同时覆盖"必然"和"偶发"。

### 正确做法（重建本地库的标准顺序）

```powershell
# 1) 先备份到项目外固定位置（不要用 C:\Temp 作为最终备份点）
$bak = "D:\PilotStd-archive\db-backup\pilotstd-$(Get-Date -Format yyyyMMdd-HHmm).db"
Copy-Item data\pilotstd.db $bak

# 2) 删库必须连 WAL/SHM/锁文件一起删——只删 .db 会留下半套状态
Remove-Item data\pilotstd.db, data\pilotstd.db-wal, data\pilotstd.db-shm, data\pilotstd.db.migration_lock -Force -ErrorAction SilentlyContinue

# 3) 在临时路径造一个"已知完好"的库，校验后再复制回来
python -c "from pilotstd.core.db import Database; Database(r'C:\Temp\seed.db')"
# 校验四要素：版本 == CURRENT_SCHEMA_VERSION、表数、关键列、checkpoint 后主文件非 4KB
Copy-Item C:\Temp\seed.db data\pilotstd.db
```

### 验收四要素（少一条都不算重建成功）

| 检查 | 期望 |
|---|---|
| `SELECT max(version) FROM _schema_version` | 等于 `CURRENT_SCHEMA_VERSION`（当前 70） |
| `SELECT count(*) FROM sqlite_master WHERE type='table'` | 40 |
| `PRAGMA table_info(announcement_record)` | 含 `language`、`foreign_name` |
| 主文件大小 | 非 4096（4096 = 只有表头，schema 还在 WAL 里未 checkpoint） |

> 最后一条是本轮踩到的"假成功"：库其实建好了，但主文件只有 4 KB，容易误判为失败。

### 防再犯

- 重建库期间**不要**同时跑测试/应用（迁移锁是跨进程排他，并发会互相打断）。
- 看到"停在某个中间版本"时，先查该版本**下一条**迁移的失败原因，不要盯着当前版本。
- 重建后先跑 `pytest tests/test_docker_api.py -q`（最快暴露 `no such table` 的一组）。

---

## P-02 `data/pilotstd.db.bak` 是**退出备份的产物**，不是夹具

### 事实

- 用例位置：`docs/guides/人工测试方案.md` 5.12「托盘右键退出后，`data/pilotstd.db.bak` 存在」。
- 写入点：`pilotstd/ui/main_window/_window_lifecycle.py::_quit_app` → `self._mgr.db.backup()`；
  `Database.backup()` 默认目标就是「同目录 `.bak`」⇒ 每次正常退出都会重写。

### 陷阱

该文件**预先存在**时，5.12 的「存在」断言**恒真**（假绿）；它也不是任何测试的输入夹具。
清理 `data/` 时容易被误当成"要保留的备份"。

### 做法

1. 手动跑 5.12 之前先删除 `data/pilotstd.db.bak`，退出后确认它被**重新生成**；
2. 清理时可直接删（应用下次退出会重建）；
3. 不要把「它存在」当作数据安全的证据——真正的回滚锚点是迁移前备份与 git 历史。

---

## P-03 迁移 checksum 不匹配是**预期噪音**（当迁移脚本被改过）

### 现象

大批测试同时失败，签名一致：`DatabaseError: 迁移 vN 的脚本逻辑已变更，checksum 不匹配`。
本次实测 52 个失败都是这一条（v70）。

### 机制

迁移源码的规范化哈希在首次执行时写入 `_schema_version`。之后只要改动该迁移文件（哪怕只是防护性改动），
旧库启动即红——这是 P-106「已执行迁移不可变」的守门机制，**不是 bug**。

### 判断方法（先定性，再决定动库）

```bash
git log -1 --format="%h %ad %s" -- pilotstd/core/db/_migrate_vN_*.py
git show <commit> -- pilotstd/core/db/_migrate_vN_*.py
```

- diff 只涉及**重入/并发/FK 包裹**等防护，不碰列定义与数据语义 ⇒ 旧库数据仍有效，属噪音；
- 若真的改了表结构/数据语义 ⇒ 必须按迁移设计走，不能只重建库了事。

### 处理

按 P-01 流程重建本地库（**不要**手改 `_schema_version` 里的 checksum——那会掩盖真实不一致）。

---

## P-04 站点代号带噪音后缀（`API STD`）导致 exact 被判 mismatch

### 现象

站点返回 `API STD 610-2004`（名称 `Centrifugal Pumps…` 完全正确），
`match_status` 却是 `mismatch`，e2e 用例长期红。

### 机制

`_parse_result_number` 把 `API STD` 解析成代号 `APISTD`，与本地 `API` 不等；
`_exact_parse_match` 在**顺序号相等但代号不等**时直接 `return False, "mismatch"`，
**跳过了后面的模糊文本回退**（否则模糊匹配本可判 exact）。

### 做法

- 比对前剥掉代号尾部噪音：`_strip_code_noise`（`STD` / `STANDARD`）；
- 顺序号仍严格判等（`API STD 609` 依旧 mismatch）；
- 回归用例：`tests/unit/query/test_search_strategy_code_noise.py`（3 例）。

### 可复用模式

**「代号归一化」应当发生在等值判断之前**；凡是 early-return 的分支，先确认它没有吞掉本可回退的路径。
