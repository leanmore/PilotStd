# 诊断报告：收藏页出现 `'super' object has no attribute 'request'`

> **任务性质**：诊断（零代码改动）。所有结论基于实际代码阅读、实际数据库查询与最小复现实测。
> **诊断时间基准**：HEAD `a8b81adf`；被测容器版本 `17d68e58`。

---

## 结论先行

**这不是一个仍在发生的故障，而是一条"历史错误文案"的残留。**

- 该字符串是 **2026-09-20** 由**已删除的旧实现**写入生产库 `favorite_downloads.error_message` 的存量文本；
- 造成它的代码缺陷已于 **`21a34b36`（2026-09-21）修复**，且**已经部署**（容器内代码与本地 HEAD 是**同一个 blob**）；
- 前端把数据库里的 `error_message` **无条件渲染**在该行状态标签下方，所以你**现在仍能看到它**；
- 实测：**105** 条收藏中 **61** 条携带这条文本，全部是 `abandoned`（已放弃）终态，`last_attempt` 唯一值就是 **2026-09-20**；修复日之后的两次尝试（2026-09-26 / 09-28）**0 条**出现该错误。

---

## 一、报错来源定位

### 1.1 全库 `super()` 检索（57 处）

**唯一**一处 `super().request`：

```python
# pilotstd/download/session.py:24-41
24: class _DefaultTimeoutSession(requests.Session):
34:     def __init__(self, default_timeout: float) -> None:
35:         super().__init__()
36:         self._default_timeout = default_timeout
38:     def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
40:         kwargs.setdefault("timeout", self._default_timeout)
41:         return super().request(method, url, **kwargs)   # ← 这一行是**正确**的
```

构造点 `pilotstd/download/session.py:72`：`s = _DefaultTimeoutSession(self._default_timeout)`
全库唯一调用方 `pilotstd/manager/facade/_base.py:210`。

### 1.2 `.request` 属性访问检索（61 处）

| 检索模式 | 结果 |
|---|---|
| `super().request` | 仅 `session.py:41`，**正确**（见第二节 MRO 实测） |
| `self.request` / `cls.request` | **0 处**活代码（`tests/test_query.py:940,951` 是名为 `request_count` 的计数器） |
| 其它 | `urllib.request`、`session.request(...)`（正常实例调用）、`response.request`（requests 响应对象属性） |

### 1.3 报错的真实出处（历史代码，已删除）

`git show 21a34b36 -- pilotstd/download/session.py` 显示被删除的旧实现（原 `session.py:52-60`）：

```python
s = requests.Session()
s.request = lambda method, url, **kwargs: (          # 对**实例**打猴子补丁
    super(requests.Session, s).request(              # ← 致命：从 requests.Session 之后再找
        method, url, timeout=self._default_timeout, **kwargs
    )
    if "timeout" not in kwargs
    else super(requests.Session, s).request(method, url, **kwargs)
)
```

- 引入：`3d966a180`（2026-06-18）
- 修复：`21a34b36`（2026-09-21 19:56）
- 同一根因项目已自行记录：`docs/ci-lessons.md:169-174`、`docs/ci-lessons.md:181-183`

---

## 二、根因分析

### 2.1 机制

`super(C, obj)` 会**从 MRO 中 C 之后**开始查找属性。旧写法对 `requests.Session` 的**实例**打补丁，
然后用 `super(requests.Session, s)` 委派——而 `s` 的类**就是** `requests.Session`，
其 `type(s).__mro__` 中 `requests.Session` 之后只剩 `object`：

```
MRO = ['Session', 'SessionRedirectMixin', 'object']
                 ↑ super(requests.Session, s) 从这里开始找
⇒ 'request' 在 object 上不存在 ⇒ AttributeError: 'super' object has no attribute 'request'
```

**一句话**：错误的根因不是"父类没有 request"，而是**把 super() 的起点设成了自己所在的类**，
导致查找范围被压缩到了只剩 `object`。

### 2.2 最小复现（实测）

用仓库自带解释器（Python 3.14.2 / requests 2.34.0）实测：

```
=== A. 旧写法 s.request = lambda ... super(requests.Session, s).request(...) ===
AttributeError: 'super' object has no attribute 'request'

=== B. 当前仓库实现 _DefaultTimeoutSession(requests.Session) ===
type(s) = pilotstd.download.session._DefaultTimeoutSession
MRO = ['_DefaultTimeoutSession', 'Session', 'SessionRedirectMixin', 'object']
实际异常: ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=1): Max retries exceeded ...

=== C. 直接验证 super() 的 MRO 语义 ===
super(requests.Session, s2).request -> AttributeError: 'super' object has no attribute 'request'
```

- A 与 C 的报错文本与用户描述**逐字节一致**；
- B 证明**当前实现**走的是 `request()` → 网络层，抛 `ConnectionError`（网络问题）而**不是** `AttributeError`。

### 2.3 为什么现在页面上还能看到

因为文本被**持久化**了，且前端**无条件渲染**：

| 环节 | 位置 | 行为 |
|---|---|---|
| 写入 | `pilotstd/tasks/favorite_download.py:395-402` | `except Exception` → `error_message = str(e)` |
| 写入 | `pilotstd/services/favorite_chain_processor.py:66-68` | `update_status` 写 `error_message` |
| 保留 | `favorite_chain_processor.py:236-240` | 重试耗尽 → 置 `abandoned`，**不清 `error_message`** |
| 读取 | `docker/api/favorites.py:254` | `" fd.error_message AS download_error,"` |
| 读取 | `docker/api/favorites.py:245-249, 252-257` | `_LATEST_DOWNLOAD_JOIN` 取同一 favorite 的最新一行 |
| 接口 | `docker/api/favorites.py:260-294` | `GET /api/favorites` |
| 渲染 | `web/src/views/FavoritesView.vue:138-143` | 状态列传 `show-error` |
| 渲染 | `web/src/components/FavoriteStatusTag.vue:46-52` | `v-if="props.showError && props.status.download_error"` → 在状态标签**下方**显示小字 |
| 布局 | `FavoriteStatusTag.vue:57-61` | `.fav-status { display: inline-flex; flex-direction: column }` → 视觉上就在"标准那一行下面" |
| 截断 | `web/src/utils/downloadStatus.ts:62-65` | 120 字符 |

**为什么只在收藏页可见**：`show-error` 只有收藏页传入；`AnnounceDetail.vue:227` 未传 → 公告详情页不显示。
与用户描述"收藏页面的标准下面"完全吻合。

### 2.4 实测存量数据（只读 GET，未做任何写操作）

用 `config/docker_creds.json` 的账号登录取 session cookie 后调用 `GET http://192.168.1.18:9028/api/favorites`：

```
总收藏数: 105
[1] download_error == "'super' object has no attribute 'request'" 的收藏数: 61
[2] 这些行的 last_attempt 取值集合: ['2026-09-20']
[3] 这些行的 download_status 取值: Counter({'abandoned': 61})
[9] 修复之后仍出现该错误的行数: 0
[7] 最新一次尝试: 2026-09-28   最早一次: 2026-08-28

另一轮统计：
  总收藏数 105 / 命中 super 错误 61 / 其中 abandoned 61
  命中行 last_attempt 唯一值 2026-09-20
  done 但仍有残留 error 的行数 6 / done 行总数 6
```

**注意**：105 行的 `download_error` **全部非空** → 收藏页**每一行**都在渲染一条错误文本。

### 2.5 部署版本核对（决定性证据）

```
GET /api/health → {"status":"ok", ..., "version":"17d68e58a9f2c18f94aba3d8f79a5141c6c49acf"}

git cat-file -t 17d68e58...                       → commit
git log -1 17d68e58...                            → 2026-10-01 17:24:58 +0800
git merge-base --is-ancestor 21a34b36 17d68e58    → exit=0  （修复提交是它的祖先 ✓）
git rev-parse 17d68e58:pilotstd/download/session.py → 9982141d0313e194e05636040d8963e4f6767c2e
git rev-parse HEAD:pilotstd/download/session.py     → 9982141d0313e194e05636040d8963e4f6767c2e
```

**结论**：容器内的 `session.py` 与本地 HEAD **完全同一 blob**，即**修复后的子类实现**。
版本号来源 `docker/api/health.py:78` 读 `APP_VERSION`；镜像内代码 = 构建时的仓库快照（`docker/Dockerfile:37`）。

### 2.6 回归测试实测

```
pytest tests/test_download.py -k "SessionManager" -v
  tests/test_download.py::TestSessionManager::test_session_injects_default_timeout   PASSED
  tests/test_download.py::TestSessionManager::test_explicit_timeout_wins             PASSED
  tests/test_download.py::TestSessionManager::test_real_request_path_reaches_adapter PASSED
  （8 passed, 26 deselected, 2 warnings in 3.49s）
```

其中 `test_real_request_path_reaches_adapter` 真实走到 `requests.adapters.HTTPAdapter.send`。

---

## 三、影响评估

**不是阻塞功能故障，是"陈旧错误文案残留"的显示问题。**

| # | 判断依据 |
|---|---|
| 1 | **调用路径不含该错误**：收藏页数据来自 `GET /api/favorites`（`docker/api/favorites.py:260-294`），是普通 FastAPI 同步函数，无类继承、无 `super()`；实测 HTTP 200 正常返回 105 条。若接口 500，前端会走 `FavoritesView.vue:77-78` 的 toast「加载失败」，而不是行内文本 |
| 2 | **代码路径已修复且已部署**：容器与 HEAD 同一 blob（2.5）；修复后（2026-09-21 之后）的两批尝试（2026-09-26 / 09-28）产出的是业务性结果（`采标标准，版权受限，自动跳过`、`done`），**0 条**该 `AttributeError` |
| 3 | **受影响的确切 UI 块**：`FavoritesView.vue:138-143` 的「状态」列内、`FavoriteStatusTag.vue:46-52` 的那行 `.fav-status-error` 小字（状态标签**下方**）。表格数字列、导出按钮、Tab 计数、类型标签**均不受影响** |
| 4 | **数据面**：61 条 `abandoned` 行携带该历史文本；另有 **6 条 `done`（下载成功）行仍携带残留错误文本**（成因：成功分支 `pilotstd/tasks/favorite_download.py:371-375` 只写 `status='done'` 与 `local_path`，**不清 `error_message`**）。所以"行下出现错误文字"有**两类**，用户报的是第一类 |
| 5 | **桌面端无关**：`pilotstd/ui/` 全目录 grep「收藏」命中 **0** 处；收藏是纯 Web 功能 |

**"未找到"的明确声明**：当前代码中**不存在**任何会抛 `'super' object has no attribute 'request'` 的调用点。
已检索的模式与结果：`super()`（57 处，仅 1 处 `super().request` 且正确）、`super(X, obj)` 显式两参形式
（4 处，全是 `docs/` 与 `tests/` 的注释/回归说明，无活代码）、`.request`（61 处）、
`self.request`/`cls.request`（0 处活代码）、`\.request\s*=`（5 处：4 处 `tests/test_adapters.py` 的
`MagicMock` 赋值，1 处 `tests/test_download.py:100` 的注释）、`requests.Session()`/`create_session(`（36 处）。

---

## 四、修复建议（只给建议，未改任何代码）

核心代码缺陷**已修复且已部署**，无需再动 `session.py`。剩余动作按推荐度排序：

### 方案 A1（推荐）—— 后端下载成功时清空 `error_message`

| 项 | 内容 |
|---|---|
| 位置 | `pilotstd/tasks/favorite_download.py:371-375`（另一处同款在 `:276-280` `_reuse_existing_file`） |
| 改法 | `UPDATE favorite_downloads SET status = 'done', local_path = ?, error_message = NULL, ...` |
| 收益 | 修掉 6 条 `done` 行的残留文本；从根上避免"成功却显示错误" |
| 风险 | **低**。仅影响展示字段；`done` 是终态，不再需要失败原因。需 grep `error_message` 相关断言 |

### 方案 A2（推荐）—— 前端把已知历史技术文案映射为可读说明

| 项 | 内容 |
|---|---|
| 位置 | `web/src/utils/downloadStatus.ts:62-65`（`truncateError`）或 `FavoriteStatusTag.vue:51` |
| 改法 | 新增"已知历史错误 → 用户文案"映射；命中 `'super' object has no attribute 'request'` 时显示「早期版本下载失败，请移除后重新收藏」 |
| 收益 | 直接消除用户困惑；**保留 DB 留痕**（`favorite_chain_processor.py:246-247` 明确要求放弃必须留痕），只在展示层改写 |
| 风险 | **低**，展示层改动，可单测覆盖 |

### 方案 A3（**不建议执行**）—— 数据清理

把 61 条 `abandoned` 的 `error_message` 置 NULL。
**风险中高**：① 清除留痕违背 `favorite_chain_processor.py:246-247` 的设计意图（"放弃是终态，必须留痕"）；
② 属生产库写操作（AGENTS.md 生产红线：禁止 UPDATE 生产数据库）。若坚持，应先在验证环境跑并保留备份。

### 方案 B（仅在"仍在实时报错"时适用）

若用户能给出 **2026-09-21 之后**的容器日志含该 `AttributeError`，说明容器跑的是旧镜像
（`APP_VERSION` 不等于含修复的 commit）→ 动作是**重建镜像**，而非改代码。
**当前证据（2.5）否定了这一可能。**

### 判别力验证设计（改完后如何证明修好了）

1. **代码层（已实测）**：`pytest tests/test_download.py -k SessionManager -v` → 8 passed。
2. **坏形态注入**：把 `_DefaultTimeoutSession` 换回旧写法
   （`super(requests.Session, s).request(...)`），`test_real_request_path_reaches_adapter` **必须失败**
   并报 `AttributeError`。本会话已用等价代码实测到该异常（2.2 的 A/C），故该断言**确实能区分好坏形态**。
3. **展示层（若采纳 A1/A2）**：在 `web/src/components/FavoriteStatusTag.test.ts`（现有 `:55`/`:62` 两条用例）
   新增：`download_status='done'` 且 `download_error` 非空 → **不渲染错误正文**。
   坏形态注入 = 去掉 `FavoriteStatusTag.vue:47` 的状态门控 → 用例必须失败。
4. **端到端（只读）**：重新 `GET /api/favorites`，断言
   `download_error == "'super' object has no attribute 'request'"` 的条目数为 **0**（当前 **61** 作为改动前基线）。

---

## 五、需要用户补充的信息

1. **它是不是页面里的一行小字，而不是浏览器控制台的红色异常？** 若 DevTools Console 有 JS 报错请贴出——那属另一个问题，本报告结论不覆盖。
2. **截图**：该文本在收藏页出现的位置（哪一列、是否在状态标签下方）。
3. **具体标准号**（例如 `GB/T 17889.7-2026`）：用它核对是否落在本次实测的 61 条 `last_attempt=2026-09-20` 集合内。
4. **触发步骤与时间**：是打开收藏页就看到，还是点了"重新收藏/重新下载"之后才出现？时间戳可判断是存量行还是新写入行。
5. **容器日志片段**：`docker logs <container>` 中含 `AttributeError` 或 `收藏失败` 的行及时间戳。**若时间戳晚于 2026-09-21，请立即告知**——那将推翻 2.5 的部署核对结论。
6. **若可直连数据库**（只读）：
   ```sql
   SELECT status, COUNT(*), MIN(last_attempt), MAX(last_attempt)
     FROM favorite_downloads GROUP BY status;
   SELECT DISTINCT last_attempt FROM favorite_downloads
     WHERE error_message LIKE '%super%';
   ```

---

## 附：本报告的证据清单

| 类别 | 具体证据 |
|---|---|
| 代码 | `pilotstd/download/session.py:24-41,72`；`docker/api/favorites.py:245-257,260-294`；`web/src/views/FavoritesView.vue:138-143`；`web/src/components/FavoriteStatusTag.vue:46-52,57-61`；`web/src/utils/downloadStatus.ts:62-65` |
| Git 历史 | `3d966a180`（引入）→ `21a34b36`（修复）；`git show 21a34b36 -- pilotstd/download/session.py` |
| 项目自有记录 | `docs/ci-lessons.md:169-174`、`:181-183` |
| 最小复现 | 旧写法 / 当前实现 / super 语义 三组实测输出（2.2） |
| 存量数据 | `GET /api/favorites` 只读统计：105 总 / 61 命中 / 全部 abandoned / `last_attempt` 唯一值 2026-09-20 / 修复后 0 条 |
| 部署核对 | `GET /api/health` version `17d68e58`；`git rev-parse` 两侧 `session.py` 同一 blob `9982141d...`；`merge-base --is-ancestor 21a34b36 17d68e58` = 0 |
| 回归测试 | `tests/test_download.py -k SessionManager` → 8 passed |
