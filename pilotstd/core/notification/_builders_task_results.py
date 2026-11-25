# 模块：项目/核心//_构建器_任务结果脚本
# 通知消息构建器（扫描/查询/归档/规范化/公告抓取/日期提醒）——从 _builders_batch.py 拆出
"""任务结果类通知的构建器（纯函数，无副作用）。

拆出原因（G-010 文件规模治理）：_builders_batch.py 有效行 477 进入警告区；
本块 10 个构建器（scan/query/archive/normalize/announce_fetch/date_reminder）
与原文件其余部分**无任何共享的模块级符号**（AST 实测），因此可整体搬移而
不产生反向依赖，也不改变任何渲染结果。

约定：每个 _build_xxx(data) 接收事件载荷、返回 NotificationMessage；签名即文档，
新增事件时在本文件末尾追加，勿再堆回 _builders_batch.py。
"""

# 分组依据：按消息在链路里的语义阶段排序（扫描 → 查询 → 归档/规范化 → 状态迁移 → 公告抓取），
# 定位模板时先按阶段缩小范围；与 _builders_batch.py 的「下载/收藏」阶段互补，两者合起来
# 覆盖全部任务类通知。顺序本身无副作用（管理器按事件名查表，不依赖定义顺序）。
from pilotstd.i18n import t

from ._builders_batch import build_failed_items_block
from ._builders_common import _std_label
from ._format_utils import translate_error_message
from .blocks import (
    KeyValueBlock,
    NotificationBlock,
    TextBlock,
)
from .channel import NotificationMessage

# 查询全未命中时正文最多列出的标准号条数（超长批量只列前 N 条；总数仍由首行给出）。
# 为什么不在构建器里无限展开：一次批量查询可达数百条，全部展开会让单条消息被渠道反复分段。
_MAX_QUERY_EMPTY_STANDARDS = 10


def _build_scan_complete_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。

    模板：共扫描 N 个文件：识别成功 S 个，无法识别 F 个；有明细时
    追加"无法识别的文件："节（• 路径 — 原因）。

    标题按失败数分支（第 5 批 F-3）：failed>0 时把数量写进标题，用户不展开即知；
    failed==0 时用 title.clean 变体——原实现两种情形共用同一标题"扫描完成"，
    与 scan_empty 完全同值，用户无法区分"扫到 N 个"与"无新增文件"。
    """
    total = data.get("total", 0)
    success = data.get("success", data.get("count", 0))
    failed = data.get("failed", 0)
    blocks: list[NotificationBlock] = [
        TextBlock(text=t("notification.scan.scan_complete.body.stats").format(t=total, s=success, f=failed)),
    ]
    failed_files = data.get("failed_files") or []
    if failed_files:
        # 失败文件逐行展示（模板："• {path} — {reason}"）
        blocks.append(TextBlock(text=t("notification.scan.scan_complete.body.failed_header")))
        lines = [
            t("notification.scan.scan_complete.body.failed_item").format(
                path=ff.get("path", ""), reason=ff.get("reason") or t("notification.common.unknown_reason")
            )
            for ff in failed_files
            if ff.get("path")
        ]
        if lines:
            blocks.append(TextBlock(text="\n".join(lines)))
    title_key = (
        "notification.scan.scan_complete.title"
        if failed > 0
        else "notification.scan.scan_complete.title.clean"
    )
    return NotificationMessage(
        # `clean` 变体无占位符，`format` 会静默忽略多余关键字参数，故统一调用
        title=t(title_key).format(failed=failed),
        blocks=blocks,
        level="warning" if failed > 0 else "info",
        event_type="scan_complete",
        icon="pi pi-search",
    )


def _build_date_reminder_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    std_no = data.get("standard_number", "")
    name = data.get("std_name", "")
    days = data.get("days_before", 0)
    remind_type = data.get("remind_type", "")
    blocks: list[NotificationBlock] = [
        TextBlock(
            text=t("notification.validity.date_reminder.body").format(
                standard_number=std_no, std_name=name, days_before=days, remind_type=remind_type
            )
        ),
    ]
    return NotificationMessage(
        title=t("notification.validity.date_reminder.title"),
        blocks=blocks,
        level="info",
        event_type="date_reminder",
        icon="pi pi-calendar",
    )


def _build_scan_empty_message(data: dict) -> NotificationMessage:
    """扫描完成但无新增文件（P1 批 B-4：补「对象」——扫描了哪个目录）。

    原实现只说"未发现新文件"，用户无法判断"没扫到"是不是路径配错。
    payload 的 `path` 由 `_scan.py` 三处触发点传入（扫描根目录）；旧 payload/测试样本
    没有该键时**不追加**路径块（零回归）。
    """
    blocks: list[NotificationBlock] = [TextBlock(text=t("notification.scan.scan_empty.body"))]
    scan_path = data.get("path") or ""
    if scan_path:
        # 复用同类别（notification.scan）既有的"路径："模板，避免为一个字段扩散新增 i18n 键
        blocks.append(TextBlock(text=t("notification.scan.auto_scan_failed.body.path").format(p=scan_path)))
    return NotificationMessage(
        title=t("notification.scan.scan_empty.title"),
        blocks=blocks,
        level="info",
        event_type="scan_empty",
        icon="pi pi-search",
    )


# ── 查询 ──
def _build_query_failed_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    std_no = data.get("standard_number", "")
    std_name = data.get("standard_name", "")
    error = data.get("error", t("notification.common.unknown_error"))
    blocks: list[NotificationBlock] = [
        TextBlock(
            text=t("notification.query.query_failed.body").format(
                standard_number=_std_label(std_no, std_name), error=error
            )
        ),
    ]
    return NotificationMessage(
        title=t("notification.query.query_failed.title"),
        blocks=blocks,
        level="error",
        event_type="query_failed",
        icon="pi pi-search",
    )


def _build_query_empty_message(data: dict) -> NotificationMessage:
    """批量查询全部未命中（P1 批 B-4：补「对象」——所查询的标准号清单）。

    原实现只有"共 N 条标准，均未查询到结果"，用户不知道"该重新查哪几条"。
    payload 的 `standards` 由 `_query_subsystem.py` 传入（本次查询的标准号，按结果顺序）；
    正文列**前 N 条**（`_MAX_QUERY_EMPTY_STANDARDS`），总数仍由首行给出。
    """
    total = data.get("total", 0)
    blocks: list[NotificationBlock] = [
        TextBlock(text=t("notification.query.query_empty.body").format(total=total))
    ]
    standards = [str(s).strip() for s in (data.get("standards") or []) if str(s).strip()]
    if standards:
        blocks.append(
            TextBlock(
                text=t("notification.common.std_no").format(
                    s=", ".join(standards[:_MAX_QUERY_EMPTY_STANDARDS])
                )
            )
        )
    return NotificationMessage(
        title=t("notification.query.query_empty.title"),
        blocks=blocks,
        level="warning",
        event_type="query_empty",
        icon="pi pi-search",
    )


# ── 归档 / 规范化（失败侧）──
def _build_archive_failed_message(data: dict) -> NotificationMessage:
    """归档失败汇总（P1 批 B-4：补「对象」——失败的标准号 / 失败明细）。

    与 archive_abandoned 语义区分：本事件指批量归档操作失败的汇总通知；
    archive_abandoned 指单条收藏下载重试 7 次后放弃。

    渲染口径（避免同一条失败重复展示两遍）：
    · `standard_number` 非空（生产者仅在**单条失败**时给出）⇒ 正文补"标准号：X"；
    · 否则 `failed_items` 非空（多条失败）⇒ 追加失败明细列表块。
    """
    count = data.get("count", 0)
    error = data.get("error", t("notification.common.unknown_error"))
    blocks: list[NotificationBlock] = [
        TextBlock(text=t("notification.archive.archive_failed.body").format(count=count, error=error))
    ]
    std_no = data.get("standard_number") or ""
    if std_no:
        blocks.append(TextBlock(text=t("notification.common.std_no").format(s=std_no)))
    else:
        failed_block = build_failed_items_block(data)
        if failed_block:
            blocks.append(failed_block)
    return NotificationMessage(
        title=t("notification.archive.archive_failed.title"),
        blocks=blocks,
        level="error",
        event_type="archive_failed",
        icon="pi pi-folder-open",
    )


def _build_normalize_failed_message(data: dict) -> NotificationMessage:
    """规范化流程异常（P1 批 B-4：补「对象」——失败明细）。

    P1 修复：error 经翻译映射后再渲染，避免 raw Python 异常文本直出。
    P1 批 B-4：payload 的 `failed_items`（文件名/标准号 + 原因，4 列口径）渲染为明细块；
    无明细时保持原正文形态（零回归），复用 `_builders_batch.build_failed_items_block`。
    """
    total = data.get("total", 0)
    failed = data.get("failed_items") or []
    # D8：正文的"N 条规范化失败"必须与明细块**同口径**——producer 的 `total` 是批次总数，
    # 而 `failed_items` 只带"当前正在处理的那条"；有明细时以明细条数为准（无明细保持旧口径）。
    total = len(failed) if failed else total
    friendly_error = translate_error_message(data.get("error", ""))
    blocks: list[NotificationBlock] = [
        TextBlock(
            text=t("notification.archive.normalize_failed.body").format(total=total, error=friendly_error)
        )
    ]
    failed_block = build_failed_items_block(data)
    if failed_block:
        blocks.append(failed_block)
    return NotificationMessage(
        title=t("notification.archive.normalize_failed.title"),
        blocks=blocks,
        level="error",
        event_type="normalize_failed",
        icon="pi pi-check-square",
    )


# ── 标准状态迁移：失效移出 / 被替代 ──
def _build_expire_standard_moved_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    std_no = data.get("standard_number", "")
    std_name = data.get("standard_name", "")
    target = data.get("target_path", "")
    return NotificationMessage(
        title=t("notification.validity.expire_standard_moved.title"),
        blocks=[
            TextBlock(
                text=t("notification.validity.expire_standard_moved.body").format(
                    standard_number=_std_label(std_no, std_name), target_path=target
                )
            )
        ],
        level="info",
        event_type="expire_standard_moved",
        icon="pi pi-folder-open",
    )


def _build_replacement_not_found_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    std_no = data.get("standard_number", "")
    std_name = data.get("standard_name", "")
    sources = data.get("searched_sources", [])
    label = _std_label(std_no, std_name)
    if sources:
        sources_str = ", ".join(str(s) for s in sources)
        text = t("notification.validity.replacement_not_found.body.with_sources").format(
            standard_number=label, sources_str=sources_str
        )
    else:
        text = t("notification.validity.replacement_not_found.body.no_sources").format(standard_number=label)
    return NotificationMessage(
        title=t("notification.validity.replacement_not_found.title"),
        blocks=[TextBlock(text=text)],
        level="warning",
        event_type="replacement_not_found",
        icon="pi pi-question-circle",
    )


# ── 公告抓取汇总 ──
def _adapter_label(name: str) -> str:
    """把 samr_gb/samr_hb 适配器标识转成用户可读名称，缺失时原样回退。"""
    key = f"notification.announce.source.{name}"
    label = t(key)
    return label if label != key else name


def _build_announce_fetch_summary_message(data: dict) -> NotificationMessage:
    """公告抓取逐站汇总（4 段式：标题 + 总计统计行 + 适配器明细（≤5 条））。"""
    adapters = data.get("adapters", [])
    total = data.get("total_count", 0)
    has_error = data.get("has_error", False)
    # 明细截断阈值（4 段式规范：超过 5 条显示汇总提示）
    MAX_ADAPTER_DISPLAY = 5
    # 统计行 + 适配器明细（最多 5 个）
    blocks: list[NotificationBlock] = [
        KeyValueBlock(key=t("notification.announce.announce_fetch_summary.body.total"), value=str(total))
    ]

    display_adapters = adapters[:MAX_ADAPTER_DISPLAY]
    for a in display_adapters:
        if a["status"] == "success":
            status_text = t("notification.announce.announce_fetch_summary.body.adapter_count").format(count=a["count"])
        else:
            status_text = t("notification.announce.announce_fetch_summary.body.adapter_error").format(
                error=a.get("error_msg", t("notification.common.unknown_error"))
            )
        blocks.append(KeyValueBlock(key=_adapter_label(a["name"]), value=status_text))

    if len(adapters) > MAX_ADAPTER_DISPLAY:
        blocks.append(
            KeyValueBlock(
                key=t("notification.announce.announce_fetch_summary.body.others"),
                value=t("notification.announce.announce_fetch_summary.body.others_count").format(
                    total=len(adapters)
                ),
            )
        )

    title_key = (
        "notification.announce.announce_fetch_summary.title.normal"
        if not has_error
        else "notification.announce.announce_fetch_summary.title.with_error"
    )
    level = "info" if not has_error else "warning"

    return NotificationMessage(
        title=t(title_key),
        blocks=blocks,
        level=level,
        event_type="announce_fetch_summary",
        icon="pi pi-megaphone",
    )


def _build_task_progress_message(data: dict) -> NotificationMessage:
    """周期进度汇报（D-2）：任务名 / 完成数 / 总数 / 百分比 / 已运行分钟 / 当前步骤。"""
    task_id = str(data.get("task_id") or "")
    task_name = str(data.get("task_name") or task_id)
    completed = int(data.get("completed") or 0)
    total = int(data.get("total") or 0)
    percent = int(data.get("percent") or 0)
    elapsed = int(data.get("elapsed_minutes") or 0)
    step = str(data.get("step") or "")

    title = t("notification.task_progress.title")
    body = t("notification.task_progress.body").format(
        task=task_name, completed=completed, total=total, percent=percent, elapsed=elapsed
    )
    if step:
        body += t("notification.task_progress.step").format(step=step)

    return NotificationMessage(
        title=title,
        body=body,
        level="info",
        event_type="task_progress",
        task_id=task_id,
        target_id=task_id,
        icon="pi pi-spin pi-spinner",
    )


def _build_auto_pipeline_summary_message(data: dict) -> NotificationMessage:
    """一键处理管道级终局汇总（Q11）：扫描 / 查到 / 下载 / 归档四行统计。

    为什么用 `KeyValueBlock` 而不是正文：四个阶段是并列指标，键值块在桌面与 Web
    都能按列对齐；正文拼串在窄屏会折行成不可读的长句。

    P1 批 B-4：补「对象」——`task_id`（本次一键处理的批次号）与 `path`（扫描根/处理范围）。
    原实现只有四个计数，用户不知道"这 12 个文件是哪一批、哪次一键处理"。
    """
    scan = int(data.get("scan") or 0)
    found = int(data.get("query_found") or 0)
    downloaded = int(data.get("download_success") or 0)
    moved = int(data.get("organize_moved") or 0)
    task_id = data.get("task_id") or ""
    scope_path = data.get("path") or ""

    blocks: list[NotificationBlock] = []
    # 对象行优先：先回答"处理了哪一批/哪个范围"，再回答"结果如何"。
    # 复用既有模板（任务/路径），避免为一个字段扩散新增 i18n 键。
    if task_id:
        blocks.append(TextBlock(text=t("notification.system.task_execution_failed.body.task").format(t=task_id)))
    if scope_path:
        blocks.append(TextBlock(text=t("notification.scan.auto_scan_failed.body.path").format(p=scope_path)))
    blocks.extend(
        [
            KeyValueBlock(key=t("notification.auto.auto_pipeline_summary.body.scan"), value=str(scan)),
            KeyValueBlock(key=t("notification.auto.auto_pipeline_summary.body.query_found"), value=str(found)),
            KeyValueBlock(
                key=t("notification.auto.auto_pipeline_summary.body.download_success"), value=str(downloaded)
            ),
            KeyValueBlock(key=t("notification.auto.auto_pipeline_summary.body.organize_moved"), value=str(moved)),
        ]
    )

    return NotificationMessage(
        title=t("notification.auto.auto_pipeline_summary.title"),
        blocks=blocks,
        level="info",
        event_type="auto_pipeline_summary",
        icon="pi pi-bolt",
    )
