# 模块：脚本/门禁公共/覆盖摘要脚本
"""门禁公共输出：`[覆盖摘要]` 统一格式。

存在理由：门禁的 `PASS` 只说明"已检查项都通过"，不说明**检查了什么、豁免了什么、
没检查什么**。后者会让 PASS 掩盖空洞（例：G-044 只覆盖 18.1% 的键空间，却与全量
覆盖同样打印 PASS）。三处门禁若无统一格式，摘要结构必然各自漂移，故抽为公共函数——
**只负责格式，不负责数据收集**（数据由各门禁在自己的作用域内提供）。

格式约定（三处门禁完全一致，改动须同步 `check_sensitive_endpoint_audit.py` /
`check_terminology.py` / `audit_notification_coverage.py`）：

    [覆盖摘要]
      范围: <扫描对象描述>
      检查项: 总计 N ｜ 通过 P ｜ 阻断 F ｜ 豁免 E
      检查口径: <逐项说明每个检查覆盖多少对象；仅当传入 notes>   # 防"总计/通过"被误读
      <豁免明细 | 跟踪项明细>: <逐条列出；仅当传入非空 exemptions>
      未覆盖说明: <显式声明不检查什么、及为何>

排版约束：摘要追加在**结果行之后**，既有 `::error::` / `::warning::` 标记与退出码
逻辑不受影响（CI 与 `check_all.sh` 仅以退出码判定成败，不解析本输出）。
"""

from __future__ import annotations

from collections.abc import Sequence

# 豁免明细单条理由的显示截断长度——过长理由会淹没摘要，此处只保留可辨识前缀
_REASON_MAX = 40
# 未覆盖说明的固定前缀：突出"这是明示的空洞，不是遗漏"
_UNCOVERED_PREFIX = "未覆盖"


def print_coverage_summary(
    scope: str,
    checked: int,
    passed: int,
    blocked: int,
    exempted: int,
    exemptions: Sequence[str],
    uncovered: str,
    notes: Sequence[str] = (),
    exemptions_label: str = "豁免明细",
    max_item_len: int = _REASON_MAX,
) -> None:
    """打印 `[覆盖摘要]` 五段标签（`范围` / `检查项` / `检查口径` / `豁免明细` / `未覆盖说明`）。

    其中 `检查口径` 与 `豁免明细` 为**条件段**：前者仅在传入 `notes` 时打印，
    后者仅在 `exemptions` 非空时打印。三处门禁的段标签集合因此可能不同——
    取决于该门禁是否有可逐条列出的豁免/跟踪名单。

    **`exemptions` 应在"存在具体名单"时传入，而非留空**：豁免计数 `exempted` 只说明
    数量，看不到"豁免了哪些"仍属 PASS 掩盖空洞。只要数据源是名单（键路径、术语词、
    事件名等）就应逐条列出；仅当豁免是**纯规则**（无法枚举）时才留空。

    参数：
    - `scope`：扫描对象的人可读描述（含具体目录与文件数）
    - `checked`/`passed`/`blocked`/`exempted`：检查项计数
    - `exemptions`：豁免条目（形如 `键名 — 理由`），空序列则**不打印**该段
    - `uncovered`：未覆盖说明，必填——门禁不得只声明通过而不声明未覆盖范围
    - `notes`：逐项检查口径（形如 `检测 1 禁用词 -> 全部 221 键`）。当同一门禁包含
      **覆盖范围不同的多个检测**时必传：否则"总计/通过"会被误读为单一集合的通过率
    - `exemptions_label`：豁免段的标题，用于区分语义（如 G-045 用"跟踪项明细"）
    - `max_item_len`：明细单条的最大显示长度。默认 40（适合"路由 — 理由"式长条目）；
      若条目的**标识符本身较长**（如 G-044 的 i18n 键路径），应传更大值以免截断到不可辨识
    """
    print()
    print("[覆盖摘要]")
    print(f"  范围: {scope}")
    print(f"  检查项: 总计 {checked} ｜ 通过 {passed} ｜ 阻断 {blocked} ｜ 豁免 {exempted}")
    if notes:
        print("  检查口径:")
        for note in notes:
            print(f"    - {note}")
    if exemptions:
        print(f"  {exemptions_label}:")
        for item in exemptions:
            text = item if len(item) <= max_item_len else item[: max_item_len - 1] + "…"
            print(f"    - {text}")
    print(f"  未覆盖说明: {_UNCOVERED_PREFIX} —— {uncovered}")
