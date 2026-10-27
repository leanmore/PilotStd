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

---

## P-05 `.fernet_key` 存在但内容损坏时：报错，不重新生成

### 行为（2026-10-24 核对 `pilotstd/core/config/crypto.py`）

| 情况 | 行为 |
|---|---|
| 文件存在且可解析 | 直接使用 |
| 文件缺失 + DB 有旧密文 | **显式报错**，拒绝生成新 key（防静默丢数据） |
| 文件缺失 + DB 无旧密文 | 生成新 key 并写入（首次初始化） |
| **文件存在但内容损坏**（长度不对 / 非合法 base64） | **直接使用 → 在 `Fernet(key)` 处抛 `ValueError`**，不会重新生成 |

### 为什么这样是安全的

损坏的 key 若被"自动重建"，等于把已有密文永久变成不可解；报错至少保留了人工修复的机会。

### 风险与待办

- 报错发生在**使用点**（解密/加密时），可能被上层包装成"配置问题"或"解密失败"，让使用者误判；
- 待办（阶段三顺手）：确认 `ValueError` 能否透出"`.fernet_key` 损坏"这一层，必要时在 `_get_fernet` 包一层更明确的错误文案；
- 备份要求：`.fernet_key` 必须**独立于 `data/` 目录**备份（2026-10-24 已复制到 `D:\PilotStd-archive\secrets\`，并同步到 `E:\PilotStd-archive\secrets\`）。

---

## P-06 测试标记文件不要写进某个具体工具的配置目录

### 现象

`tests/conftest.py` 的 `pytest_sessionfinish` 会把"测试通过"标记写入 `.claude/.test_pass`（含 commit hash / 用例数）。
这是 Claude Code 时代的"三位一体"机制。

### 后果

- 工具换成 DSH 后，该标记没有任何消费方，但**每次跑测试仍会重建 `.claude/` 目录**；
- 只删目录不删写入点 = 下次测试又长出来（本轮实测：删钩子前文件 mtime 19:35，删钩子后跑 47 个用例未再生成）；
- 目录名绑定工具，工具一换就成为孤儿目录与孤儿标记。

### 做法

- 标记/缓存**写到工具无关的路径**（系统临时目录或仓库外），或干脆不写；
- 删除某个"工具目录"前，先 `git grep` 找**写入点**——只删目录是治标；
- 本案例处理（2026-10-24）：删除 `pytest_sessionfinish` 钩子（含不再使用的 `json/subprocess/datetime` 导入）→ 删除 `.claude/` → `.gitignore` 保留 `.claude*` 防再生。

### 可复用模式

**"临时状态"要按生命周期管，不按工具目录管**。凡是 `tests/` 或脚本写入 `.<tool>/` 的，都视为会在下一次运行时复活的隐患。

---

## P-07 `'super' object has no attribute 'request'`：多重继承下的父类解析

### 现象

容器内报 `'super' object has no attribute 'request'`；核对容器 `session.py` 与本地 HEAD 为**同一 blob**，
说明**不是"部署了旧代码"**，而是运行期父类解析问题。

### 根因

多重继承场景下 `super()` 解析到的父类不是预期的 requests 基类（MRO 顺序受 mixin 影响），
调用链在错误父类上找 `request` 属性。

### 修复与避免

- 修复落在**子类实现**（显式指定父类/调整 MRO），不在调用点打补丁；
- 避免：新增 mixin 时检查 MRO（`Cls.__mro__`），并对多继承类补一条最小回归用例；
- 关联：`docs/DECISIONS.md` D-24 附近的下载/会话链结论。

---

## P-08 公告"头完整、详情缺"：解析器前缀/分隔符覆盖不足

### 现象

源站列表与部署 API 逐条对照（2026-10-18，v0.142.1）显示：**公告头完整，缺口全在公告详情记录**，
GB / DB / HB 三类都有。

### 根因

解析器对标准号**前缀/分隔符**的覆盖不足（如 `NB/SH/T`、`DB52T`、`DB11/` 等变形），
导致详情记录在 matcher 阶段被跳过——**不是抓取没抓到，而是解析没认出来**。

### 修复与避免

- 修复方向：`parse_std_number` 增加变形前缀兜底、与提取层共用同一 token 语法；
- 避免：新增标准来源时，先拿 3 条真实样本跑"提取 → 解析"闭环，再上线；
- 审计方法：源站列表/详情 ↔ 部署 API 逐条对照（本次方法可复用）。

---

## P-09 `if not blocks` 兜底把正文原样返回：MarkdownV2 保留字符导致 400

### 现象

`POST /api/notification/test` 发 Telegram，正文含 `.` 或 `(`/`)` 时返回 `{"ok":false,"error":"投递失败"}`；
纯字母/连字符正常。真实环境实测（2026-10-27，局域网 Docker）。

### 根因

`renderer_base.py::render()` 在 `message.blocks` 为空时走兜底：

```python
if not blocks:
    text = message.body if message.body else ""   # 原样返回，没走 _escape；标题也不渲染
```

Telegram 用 `parse_mode=MarkdownV2`，正文里的 `.` `(` `)` 未转义 → API 返回 400 `can't parse entities`。

**与 A-13 的 requests 迁移无关**：`renderer_base.py` 在迁移期间零改动，所以"部署新代码也会失败"。

### 修复

- 基类新增可覆盖钩子 `_render_plain_text(message)`，默认逐字返回正文（其它渠道行为不变）；
- `TelegramRenderer` 覆盖：`_escape` 正文与标题，输出 `*标题*\n\n正文`；
- 回归：`tests/unit/core/test_renderer_plain_text.py`（3 例：转义+标题、带 blocks 走原路径、非 Telegram 逐字不变）。

### 可复用模式

**"兜底分支"最容易绕过安全/格式处理**——任何 `if not X: return raw` 的降级路径，都要问一句
"这条路上有没有本该施加的转义/校验/日志"。本次是转义，下次可能是鉴权或脱敏。

---

## P-10 i18n 全局状态未隔离：测试顺序依赖（`_("key")` 回退成 key）

### 现象

单独跑 `tests/unit/test_i18n.py` 全绿；插进全量套件后，
`test_switch_to_unknown_language_falls_back_to_default` 断言
`i18n._("hello") == "你好"` 失败，实际得到 `"hello"`。删除/新增测试文件改变执行顺序后红点出现或消失。

### 根因

`pilotstd/i18n/__init__.py` 的翻译状态是**模块级全局**：

- `_translations`（dict，全部语言表）
- `_loaded`（bool，懒加载标志）
- `_lang_var`（ContextVar，当前语言）

`_()` 的实现是 `_translations.get(_lang_var.get(), {}).get(key, key)`。
某个用例把 `_translations` 改成精简表（如只留 `{"zh_CN": {"hello": "你好"}}`）后没有还原，
后续用例在默认语言下取不到键 → 静默回退成 key 本身。
`tests/conftest.py` 原有 autouse fixture 只恢复**语言**，不恢复翻译表与懒加载标志，所以污染仍然穿透。

### 修复与回归

- `tests/conftest.py::_restore_i18n_language`：进入时快照 `_translations`（浅拷贝）与 `_loaded`，
  退出时还原，再恢复语言；
- `tests/unit/test_i18n.py::test_switch_to_unknown_language_falls_back_to_default`：
  把"写精简表"改到 `set_language()` 之后，按当前语言写入，避免切换过程中被懒加载覆盖；
- 浅拷贝的边界：现有用例都是 `_translations = {...}` 整体重新赋值，浅拷贝足够；
  若未来出现 `_translations[lang][key] = ...` 的**嵌套原地写**，必须升级为 `copy.deepcopy`。

### 可复用模式

**模块级可变全局状态 = 跨测试污染源**。判断一个 autouse fixture 是否"根治"，
要看被测代码实际读了哪些全局量（本例是三个：语言、翻译表、加载标志），而不是只看最显眼的那个（语言）。
