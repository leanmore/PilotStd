# 模块：项目/核心/标准名称解析
"""标准名称的「最高可得阶段」解析——回退链 ③ → ② → ①。

为什么需要本模块
----------------
同一个标准在库里有**多份名称副本**，分属不同处理阶段：

* **① 解析名**：``announcement_record.std_name`` / ``file_index.std_name``
  （扫描文件名或公告附件解析时写入；2026-06-20「名称决策」专项之前的既有字段）
* **② 查询名**：``standard_info_cache.result_json`` 内的 ``standard_name``
  （网站查询适配器产出，读取时映射为 ORM 的 ``found_name``）
* **③ 决策名**：``announcement_record.final_name``
  （名称决策比较 ① 与 ② 后的结果；**自 v66 迁移起落库**，此前仅在内存对象上回写）

历史实现（``pilotstd/tasks/favorite_download.py::_fetch_std_meta``）**只读 ①**，
于是"①没有对应行、或 ① 是过期文件名"时，通知里的名称就会**为空或过期**——这正是
"下载通知族拿不到标准名"的根因。

取值口径（2026-10-05 裁定 D1/D7）
--------------------------------
按**质量降序**取第一个非空值：**③ 决策名 → ② 查询名 → ① 解析名**；全空返回空串。
该口径与既有写法 ``manager/pending_service.py:100``（``found_name or std_name``）同源，
只是把 ③ 提到最前。**不保证**一定有 ③——批次一（无 v66 迁移）阶段会自然回退到 ②/①，
这是**预期行为**，不是缺陷。

命名约定（2026-10-05 裁定 D8/D3）
--------------------------------
对外边界（API 响应键、通知载荷键、前端、spec/契约）**统一全写** ``standard_name``；
**DB 存储层列名本轮不动**（仍为 ``std_name``/``found_name``/``final_name``），
由本模块做**单点转换**，避免命名统一与业务修复混在同一批里。
"""

from __future__ import annotations

import json
from typing import Any

# 名称阶段的质量降序：既作文档、也是实现的唯一口径（新增阶段只改这一处）。
NAME_STAGE_ORDER: tuple[str, ...] = ("final_name", "found_name", "std_name")

# 站点优先级默认值：国标站点字段最全，同名多站点时优先取它。
DEFAULT_PREFERRED_SITE = "std_gov"


def resolve_name(*candidates: Any) -> str:
    """按传入顺序返回**第一个非空**名称（调用方须按 ③→②→① 的质量降序传参）。

    为什么做成纯函数：阶段优先级是本模块的**唯一业务规则**，纯函数便于单测穷举
    （含 None/空白串/非字符串），也避免把"取值顺序"散落到各调用点。
    """
    for value in candidates:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _row_get(row: Any, key: str) -> Any:
    """兼容取列：``Database`` 返回字典行，测试替身可能返回元组行。"""
    if row is None:
        return None
    if hasattr(row, "get"):
        return row.get(key)
    return None


def _has_column(db: Any, table: str, column: str) -> bool:
    """探测表是否存在某列（``PRAGMA table_info``）。

    为什么要探测而不是直接 SELECT：``announcement_record.final_name`` 由**后续迁移（v66）**
    引入。批次一必须在该列**尚不存在**时也能正常工作（自然回退到 ②/①），
    且**批次二加列后本模块无需再改**。
    先例：``pilotstd/core/db/_migrate_v54.py`` 同样用 ``PRAGMA table_info`` 做列名探测。

    探测失败（表不存在/DB 异常）一律返回 False——降级为"没有该列"，绝不抛错。
    """
    try:
        rows = db.fetchall(f"PRAGMA table_info({table})") or []
    except Exception:  # noqa: BLE001 - 探测失败不得影响通知链路
        return False
    for row in rows:
        if _row_get(row, "name") == column:
            return True
    return False


def _cached_query_name(db: Any, standard_number: str, preferred_site: str) -> str:
    """从**阶段②**缓存（``standard_info_cache.result_json``）取名称。

    为什么按"优先站点 + cached_at 倒序"：同一标准号可能有**多个站点**的缓存行，
    国标站点（默认 ``std_gov``）字段最全 ⇒ 先取它；同一站点有多行时取最新。
    为什么 JSON 解析要兜异常：缓存内容是**外部写入**的 JSON，损坏时不得让通知链路抛错。
    """
    try:
        row = db.fetchone(
            "SELECT result_json FROM standard_info_cache WHERE standard_number = ? "
            "ORDER BY (source_site != ?), cached_at DESC LIMIT 1",
            (standard_number, preferred_site),
        )
    except Exception:  # noqa: BLE001 - 缓存表可能尚未建表（懒建）
        return ""
    raw = _row_get(row, "result_json")
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    return resolve_name(data.get("standard_name"))


def fetch_resolved_name(
    db: Any,
    standard_number: str,
    *,
    preferred_site: str = DEFAULT_PREFERRED_SITE,
) -> tuple[str, str]:
    """取「最高可得」名称与标准分类，返回 ``(名称, standard_type)``。

    取值顺序（每一级都可能在真实数据里缺席，故逐级回退）：

    1. **③ 决策名**：``announcement_record.final_name``（列不存在则跳过，见 ``_has_column``）；
    2. **② 查询名**：``standard_info_cache.result_json`` 内的 ``standard_name``；
    3. **① 解析名**：``announcement_record.std_name``。

    ``standard_type`` 仍**只**取自 ``announcement_record``（分类没有阶段副本，沿用既有口径）。
    任何一步异常都降级为空串：**通知链路不得因元信息缺失而失败**。
    """
    if not standard_number:
        return "", ""

    final_name: Any = None
    parsed_name: Any = None
    standard_type = ""

    has_final = _has_column(db, "announcement_record", "final_name")
    columns = "std_name, standard_type" + (", final_name" if has_final else "")
    try:
        row = db.fetchone(
            f"SELECT {columns} FROM announcement_record WHERE standard_number = ? LIMIT 1",
            (standard_number,),
        )
    except Exception:  # noqa: BLE001 - 表缺失/DB 异常一律降级
        row = None
    if row is not None:
        parsed_name = _row_get(row, "std_name")
        standard_type = str(_row_get(row, "standard_type") or "")
        if has_final:
            final_name = _row_get(row, "final_name")

    # ③ 决策名 > ② 查询名 > ① 解析名：逐级回退，第一个非空即返回。
    name = resolve_name(final_name)
    if not name:
        name = _cached_query_name(db, standard_number, preferred_site)
    if not name:
        name = resolve_name(parsed_name)
    return name, standard_type
