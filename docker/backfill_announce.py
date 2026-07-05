# docker/backfill_announce.py
# 一次性回填逻辑：为 announcement_record 历史数据补齐 announcement_title 和 standard_count。
# 在 Docker 容器启动时自动执行，通过 lifespan 调用。

import logging

logger = logging.getLogger(__name__)

_BACKFILL_DONE_FLAG = "_backfill_announce_v1_done"


def _needs_backfill(db) -> bool:
    """检查是否需要回填：表中存在 announcement_title 为 NULL 的记录。"""
    row = db.fetchone("SELECT COUNT(*) as cnt FROM announcement_record WHERE announcement_title IS NULL LIMIT 1")
    return (row["cnt"] if row else 0) > 0


def _build_list_lookup() -> dict[tuple[str, str], dict]:
    """从 GB/HB/DB 三个列表 API 拉取全量数据，构建 (source_site, pid) → {title, std_count} 查找表。"""
    from pilotstd.announcement.adapters.samr_db import SamrDbAdapter
    from pilotstd.announcement.adapters.samr_gb import SamrGbAdapter
    from pilotstd.announcement.adapters.samr_hb import SamrHbAdapter

    adapters = [
        SamrGbAdapter(),
        SamrHbAdapter(),
        SamrDbAdapter(),
    ]

    lookup: dict[tuple[str, str], dict] = {}
    for adapter in adapters:
        source_site = f"announcement_{adapter.standard_type}"
        logger.info("[backfill] 拉取 %s 列表 API 数据...", adapter.standard_type.upper())
        try:
            ann_list = adapter._fetch_list(since_date="", page_size=50)
        except Exception as e:
            logger.warning("[backfill] %s 列表 API 失败: %s", adapter.standard_type.upper(), e)
            continue

        for ann in ann_list:
            pid = ann.get("pid", "")
            title = ann.get("title", "")
            std_count_str = ann.get("std_count", "")
            std_count = int(std_count_str) if std_count_str else None
            lookup[(source_site, pid)] = {
                "announcement_title": title or None,
                "standard_count": std_count,
            }

        logger.info(
            "[backfill] %s: 列表 API 获取 %d 条公告",
            adapter.standard_type.upper(),
            len(ann_list),
        )

    return lookup


def _resolve_via_detail(
    pid: str,
    source_site: str,
    adapters: dict,
) -> dict | None:
    """对于列表 API 中找不到的 pid，通过详情页获取标题和标准数。"""
    std_type = source_site.replace("announcement_", "")
    adapter = adapters.get(std_type)
    if adapter is None:
        return None

    try:
        raw = adapter._fetch_detail(pid)
        if not raw:
            return None
        items = adapter._parse_items(raw)
        if not items:
            return None

        title = items[0].get("announcement_title", "") if items else ""
        return {
            "announcement_title": title or None,
            "standard_count": len(items),
        }
    except Exception as e:
        logger.warning("[backfill] 详情页回退失败 pid=%s: %s", pid[:32], e)
        return None


def run_backfill(db, adapters: dict) -> dict:
    """执行回填逻辑。返回 {total, updated, skipped, failed}。"""
    if not _needs_backfill(db):
        logger.info("[backfill] 无需回填：所有记录已包含 announcement_title")
        return {"total": 0, "updated": 0, "skipped": 0, "failed": 0}

    logger.info("[backfill] 检测到历史数据缺少 announcement_title，开始回填...")

    # Step 1: 从列表 API 构建查找表
    lookup = _build_list_lookup()
    logger.info("[backfill] 列表 API 查找表: %d 条公告", len(lookup))

    # Step 2: 查询所有需要回填的唯一 (source_site, pid)
    rows = db.fetchall("SELECT DISTINCT source_site, pid FROM announcement_record WHERE announcement_title IS NULL")
    total_pids = len(rows)
    logger.info("[backfill] 需要回填的公告: %d 个唯一 pid", total_pids)

    updated = 0
    failed = 0

    for row in rows:
        source_site = row["source_site"]
        pid = row["pid"]

        key = (source_site, pid)
        data = lookup.get(key)

        # 列表 API 未命中 → 尝试详情页
        if data is None:
            data = _resolve_via_detail(pid, source_site, adapters)
            if data is None:
                failed += 1
                continue

        # GB 列表 API 无 STD_COUNT → 详情页兜底计算 len(items)
        if data.get("standard_count") is None:
            detail = _resolve_via_detail(pid, source_site, adapters)
            if detail and detail.get("standard_count") is not None:
                data["standard_count"] = detail["standard_count"]

        title = data.get("announcement_title")
        std_count = data.get("standard_count")

        try:
            db.execute(
                "UPDATE announcement_record SET announcement_title=?, standard_count=? WHERE source_site=? AND pid=?",
                (title, std_count, source_site, pid),
            )
            updated += 1
        except Exception as e:
            logger.warning("[backfill] UPDATE 失败 pid=%s: %s", pid[:32], e)
            failed += 1

        if updated % 20 == 0:
            logger.info("[backfill] 进度: %d/%d 已处理", updated, total_pids)

    logger.info(
        "[backfill] 回填完成: total=%d updated=%d failed=%d",
        total_pids,
        updated,
        failed,
    )
    return {"total": total_pids, "updated": updated, "skipped": 0, "failed": failed}
