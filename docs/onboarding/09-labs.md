# 09 · 上手实验（7 个安全 Lab：5 个核心 + 2 个可选）

> 目标：把“看懂”变成“做过”。  
> 所有 Lab 都在**开发/验证环境**进行；不要对生产库/生产容器做写操作。

---

## Lab 0：准备

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements-dev.txt
```

确认：

```bash
python -c "import pilotstd; print('ok')"
```

---

## Lab 1：文件名 → 标准号（解析器）

### 目标

理解 `StandardParser.parse()` 的输出，知道哪些文件名会失败。

### 步骤

在仓库根目录执行（PowerShell 可用 `@' ... '@ | python -`）：

```python
from pilotstd.scan.parser import StandardParser
from pilotstd.organizer.industry_lookup import build_code_mapping

p = StandardParser(build_code_mapping())
names = [
    "GB/T 1234-2020 某某技术规范.pdf",
    "GBT 1234-2020 某某技术规范.pdf",
    "TSG 8002-2022 特种设备检验人员考核规则 第1号修改单.docx",
    "特种设备无损检测机构鉴定评审指南.pdf",
    "T/CECS 001-2019 某团体标准.pdf",
]
for n in names:
    info = p.parse(n)
    if info:
        print(n, "->", info.logical_code, info.number, info.year, info.file_kind)
    else:
        print(n, "-> PARSE_FAIL")
```

### 期望

- `GB/T` 与 `GBT` 都能归一；
- `TSG ... 第1号修改单` 解析出 `file_kind="第1号修改单"`；
- 无标准号的指南 `PARSE_FAIL`；
- 团体标准 `T/CECS` 能解析。

### 问题

1. `logical_code` 与 `number` 为什么要分开？
2. 为什么无标准号文件不会进 `parsed_results`？
3. `file_kind` 对“修改单”有什么用？

---

## Lab 2：Word 归档与 `T 未知行业(T)`

### 目标

亲眼看到 Word 重解析的空 `scan.code_mapping` 如何把 `TSG` 变成 `T/SG`。

### 步骤

```python
from pilotstd.scan.parser import StandardParser
from pilotstd.organizer.industry_lookup import get_folder_name, get_base_code

empty = StandardParser({})   # 模拟 OrganizerCore._std_parser
info = empty.parse("TSG 3001-2009 压力管道安装许可规则.doc")
print(info.logical_code, get_base_code(info.logical_code))
print(get_folder_name(info.logical_code))
```

### 期望

```text
T/SG T
T 未知行业(T)
```

### 再跑现有单测

```bash
python -m pytest tests/unit/manager/organize/test_organizer.py -q
```

### 问题

1. 为什么 `TSG` 会匹配成 `T/SG`？
2. 为什么 PDF 不进 T 目录，只有 Word 进？
3. 如果要修，应该改解析器构造，还是改 Word 分支？

---

## Lab 3：监控 `_on_file` 的真归档

### 目标

理解“监控只 scan + archive”的行为，以及它和 `auto_run` 的差异。

### 步骤

```bash
python -m pytest tests/integration/test_monitor_archive_e2e.py -q
```

阅读：

```text
tests/integration/test_monitor_archive_e2e.py
```

重点看：

- `_on_file` 如何扫描 `dirname`；
- 合规文件如何离开 Inbox；
- 不合规文件如何留在 Inbox；
- `auto_archive=false` 时什么都不做。

### 问题

1. 这个测试是否覆盖查询/下载？
2. 为什么无标准号文件留在 Inbox？
3. `_on_file` 与 `auto_run` 差哪些阶段？

---

## Lab 4：通知聚合

### 目标

理解聚合器的分组键、窗口、批量发送。

### 步骤

```bash
python -m pytest tests/test_aggregate_buffer.py -q
```

阅读：

```text
pilotstd/core/notification/aggregate_keys.py
pilotstd/core/notification/aggregate_buffer.py
```

重点看：

- `correlation_id` 批次键；
- `notify_event × target_id` 日常键；
- 窗口/最大条数；
- `bypass_events`。

### 问题

1. 为什么 Web 五段式的下载/归档通知不共享同一个批次键？
2. 为什么 `standard_first_registered` 能聚合，而 `archive_complete` 有时不能？
3. 如果一次批量归档 500 个文件，你希望发几条通知？

---

## Lab 5：前端四件套

### 目标

验证前端改动的基本质量；理解 CI 的顺序。

### 步骤

```bash
cd web
pnpm run type-check
pnpm run lint
pnpm test
pnpm run build
```

Windows 如果 PowerShell 拦截：

```bash
pnpm.cmd run type-check
pnpm.cmd run lint
pnpm.cmd test
pnpm.cmd run build
```

### 期望

四条都退出码 0。

### 问题

1. 为什么只跑 `build` 不够？
2. 改组件后至少要跑哪几条？
3. `vitest` 与 `playwright` 分别覆盖什么？

---

## Lab 6：看数据库（只读）

### 目标

会用 SQL 看 `file_index` / `standard_validity` / `notification_log`。

### 步骤

用 Python 只读打开 `data/pilotstd.db`：

```python
import sqlite3
con = sqlite3.connect("file:data/pilotstd.db?mode=ro", uri=True)
for row in con.execute(
    "SELECT file_path, logical_code, number, year, status "
    "FROM file_index ORDER BY id DESC LIMIT 10"
):
    print(row)
```

再看：

```sql
SELECT standard_number, status, last_checked_at, next_check_at
FROM standard_validity
ORDER BY updated_at DESC
LIMIT 10;

SELECT event_type, channel, status, error_msg, sent_at
FROM notification_log
ORDER BY id DESC
LIMIT 10;
```

### 问题

1. 文件已归档，`file_index` 一定有记录吗？
2. `standard_validity` 的 `status` 和 `file_index.status` 为什么可能不同？
3. `notification_log.failed` 说明什么？

---

## Lab 7（可选）：本机 Docker 走一遍

> 只在本机/验证环境做；不要对生产执行。

```bash
docker compose up -d
curl -s http://localhost:9028/api/health
```

然后：

1. 把一个样例 PDF 放进 `./inbox`；
2. 看 `logs/app.log` 的 `[MONITOR]`、`扫描完成`、`归档完成`；
3. 看 `./standards` 是否出现分类目录；
4. 看 `data/pilotstd.db` 的 `file_index`。

### 注意

- 如果没有样例 PDF，用测试里的 fake PDF 字节即可（只有文件名参与解析）；
- 不要把生产 `docker-compose` 和本机实验混用；
- 实验结束可 `docker compose down`，但不要删生产卷。

---

## Lab 完成标准

- [ ] Lab 1 能解释 `GB/T`/`GBT`/`TSG`/无标准号/团体标准；
- [ ] Lab 2 能复现 `T 未知行业(T)`；
- [ ] Lab 3 能说出 `_on_file` 与 `auto_run` 的差异；
- [ ] Lab 4 能解释“为什么有时聚合失效”；
- [ ] Lab 5 四条命令全绿；
- [ ] Lab 6 能用 SQL 查三张核心表。

完成后进入 [`10-assessment.md`](10-assessment.md)。
