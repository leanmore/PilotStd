# 模块：项目//_下载脚本
# 阶段4:收藏下载归档任务

import logging
import time
from pathlib import Path
from typing import Any, Optional, cast

from pilotstd.core.config import ConfigManager, get_db_path
from pilotstd.core.db.database import Database
from pilotstd.download.engine import ADOPTED_SKIP_MESSAGE
from pilotstd.organizer.industry_lookup import build_code_mapping
from pilotstd.scan.parser import StandardParser

logger = logging.getLogger(__name__)
# 收藏下载归档过程中的异常


class FavoriteArchiveError(Exception):
    """收藏下载归档过程中的异常。"""

    pass


class FavoriteSkip(FavoriteArchiveError):
    """业务终态跳过：类别闸/版权闸决定该标准**永远不会**被自动下载。

    与普通失败的区别是"重试无意义"：采标标准版权受限、非国标无下载适配器，
    再等 7 天结果也一样。链路据此直接置终态并只通知一次，不消耗重试窗口、
    不产生每日失败通知（此前实测每条要空转 7 天）。
    """

    pass


def _get_inbox_dir() -> Path:
    """从配置中获取 inbox 目录路径。"""
    cfg = ConfigManager()
    return Path(cfg.get("storage.inbox_dir", "/inbox"))


def _get_standard_type(favorite_id: int, db: Database) -> str:
    """读取收藏下载记录的标准分类（v57 落库；无记录或未分类返回空串）。"""
    row = db.fetchone(
        "SELECT standard_type FROM favorite_downloads WHERE favorite_id = ?", (favorite_id,)
    )
    return str(row["standard_type"]) if row and row["standard_type"] else ""


def _load_cached_query_result(db: Database, standard_number: str) -> Optional[Any]:
    """从查询缓存取该标准的查询结果，仅限 std_gov 源。

    下载所需的 hcno（= std_gov 搜索结果的 pid）只有该源产生；
    不限定 source_site 会命中外站行（ahbz/njbz365 等无 hcno）。
    """
    try:
        from pilotstd.query.cache import CacheRepository

        return CacheRepository(db).get(standard_number, "std_gov")
    except Exception as e:
        logger.warning("读取查询缓存失败 (%s): %s", standard_number, e)
        return None


def _query_std_gov(mgr: Any, standard_number: str) -> Optional[Any]:
    """缓存未命中时现场查询国标站点，取回含 hcno / 采标状态的查询结果。"""
    try:
        results, _stats = mgr.query_by_numbers([standard_number], preferred_site="std_gov")
    except Exception as e:
        logger.warning("标准查询失败 (%s): %s", standard_number, e)
        return None
    for result in results or []:
        if getattr(result, "hcno", ""):
            return result
    return None


def _find_in_file_index(standard_number: str, db: Database) -> Optional[str]:
    """检查 file_index 中是否已有该标准的文件。"""
    try:
        parser = StandardParser(build_code_mapping())
        parsed = parser.parse(standard_number)
        if parsed:
            cursor = db.execute(
                "SELECT file_path FROM file_index"
                " WHERE logical_code = ? AND number = ? AND year = ?"
                " ORDER BY scanned_at DESC LIMIT 1",
                (parsed.logical_code, parsed.number, parsed.year),
            )
            row = cursor.fetchone()
            if row:
                return cast("str | None", row["file_path"])
    except Exception:
        pass
    return None


def _safe_filename(standard_number: str, suffix: str) -> str:
    """将标准号中的非法文件名字符替换为下划线，追加后缀。"""
    safe = standard_number
    for ch in r'\/:*?"<>|':
        safe = safe.replace(ch, "_")
    return f"{safe}_{suffix}.pdf"


def _fetch_std_meta(standard_number: str) -> tuple[str, str]:
    """查询标准名称与分类（通知模板补充信息；查不到时降级为空串，不抛错）。"""
    try:
        db = Database(get_db_path())
        try:
            row = db.fetchone(
                "SELECT std_name, standard_type FROM announcement_record WHERE standard_number = ?",
                (standard_number,),
            )
            if row:
                return (row["std_name"] or ""), (row["standard_type"] or "")
        finally:
            db.close()
    except Exception:
        pass
    return "", ""


def _notify_download_failed(
    user_id: int, standard_number: str, error: str, favorite_id: int, notify: bool = True
) -> None:
    """通知用户下载失败。"""
    if not notify:
        return
    try:
        from pilotstd.manager.facade import StandardManager  # noqa: E402

        std_name, standard_type = _fetch_std_meta(standard_number)
        StandardManager().notification_mgr.send_event(
            "download_failed",
            {
                "user_id": user_id,
                "standard_number": standard_number,
                "standard_name": std_name,
                "standard_type": standard_type,
                "error": error,
                "favorite_id": favorite_id,
            },
        )
    except Exception as e:
        logger.warning("发送下载失败通知失败: %s", e)


def _notify_download_started(user_id: int, standard_number: str, favorite_id: int, notify: bool = True) -> None:
    """通知用户下载开始。

    在下载任务进入执行阶段（状态置为 downloading 前）发送，
    让用户感知收藏的自动下载流程已启动；通知失败仅记录日志，
    绝不中断下载主流程。
    """
    if not notify:
        return
    try:
        from pilotstd.manager.facade import StandardManager  # noqa: E402

        std_name, standard_type = _fetch_std_meta(standard_number)
        StandardManager().notification_mgr.send_event(
            "download_started",
            {
                "user_id": user_id,
                "standard_number": standard_number,
                "standard_name": std_name,
                "standard_type": standard_type,
                "favorite_id": favorite_id,
            },
        )
    except Exception as e:
        logger.warning("发送下载开始通知失败: %s", e)


def _notify_download_complete(
    user_id: int, standard_number: str, favorite_id: int, local_path: str, notify: bool = True
) -> None:
    """通知用户下载归档完成。

    文件已在标准库 file_index 登记（done 状态）后发送；
    local_path 为归档后的实际存储路径，供用户直接定位。
    通知失败仅记录日志，不影响已完成的下载归档结果。
    """
    if not notify:
        return
    try:
        from pilotstd.manager.facade import StandardManager  # noqa: E402

        std_name, standard_type = _fetch_std_meta(standard_number)
        StandardManager().notification_mgr.send_event(
            "download_complete",
            {
                "user_id": user_id,
                "standard_number": standard_number,
                "standard_name": std_name,
                "standard_type": standard_type,
                "favorite_id": favorite_id,
                "local_path": local_path,
                "status": "success",
            },
        )
    except Exception as e:
        logger.warning("发送下载完成通知失败: %s", e)


# 下载__—收藏下载任务（44解耦后操作_下载表）
def _resolve_download_target(mgr: Any, db: Database, favorite_id: int, standard_number: str) -> Any:
    """下载前三闸：类别（仅国标）→ hcno 取用 → 采标。返回可下载的查询结果。

    hcno 是可下载能力的载体（openstd 需先建会话再取全文），查询缓存优先、
    未命中现场查一次；冷却期与新标准判定由下载链 SQL 负责，此处不重复。

    类别闸/版权闸命中时抛 `FavoriteSkip`（业务终态，重试无意义）。
    """
    std_type = _get_standard_type(favorite_id, db)
    if std_type and std_type != "NationalStd":
        raise FavoriteSkip(f"非国标标准（{std_type}），自动下载仅支持国标")

    query_result = _load_cached_query_result(db, standard_number)
    if query_result is None or not getattr(query_result, "hcno", ""):
        query_result = _query_std_gov(mgr, standard_number)
    if query_result is None:
        raise FavoriteArchiveError(f"无法获取下载标识(hcno): {standard_number}")
    if getattr(query_result, "is_adopted", False):
        raise FavoriteSkip(f"{ADOPTED_SKIP_MESSAGE}: {standard_number}")
    return query_result


def _fetch_into_inbox(mgr: Any, query_result: Any, standard_number: str, inbox_path: Path) -> None:
    """经下载引擎取字节写入 inbox（失败抛 FavoriteArchiveError，由外层统一补通知）。"""
    from pilotstd.download.models import DownloadTask

    content, err = mgr.download_engine.fetch_bytes(
        DownloadTask(
            standard_number=standard_number,
            query_result=query_result,
            source_site="std_gov",
        )
    )
    if not content:
        # 引擎侧同样以该文案表达"采标跳过"（引擎字节抓取的版权闸）→ 归为终态跳过
        if err == ADOPTED_SKIP_MESSAGE:
            raise FavoriteSkip(f"{err}: {standard_number}")
        # 不在此处发送失败通知：抛出异常后由外层异常捕获统一补发一次
        # （避免同一失败路径双通知——内层原始错误 + 外层包装错误）
        raise FavoriteArchiveError(f"下载失败: {standard_number}, {err}")
    inbox_path.write_bytes(content)


def _reuse_existing_file(
    db: Database, favorite_id: int, standard_number: str, user_id: int, notify: bool
) -> bool:
    """file_index 已有该标准文件时直接标记完成并返回 True（避免重复下载）。

    复用路径同样视为"下载归档完成"，向用户发一次完成通知（notify=False 时抑制）。
    """
    existing = _find_in_file_index(standard_number, db)
    if not existing:
        return False
    db.execute(
        "UPDATE favorite_downloads SET status = 'done', local_path = ?,"
        " updated_at = datetime('now') WHERE favorite_id = ?",
        (existing, favorite_id),
    )
    logger.info("复用已有文件: %s", existing)
    _notify_download_complete(user_id, standard_number, favorite_id, existing, notify)
    return True


def download_to_inbox(favorite_id: int, user_id: int, record_id: int, notify: bool = True) -> None:
    """收藏下载任务：复用已有文件 → 下载到 inbox → 轮询 file_index → 更新状态。
    所有状态更新写入 favorite_downloads 表（v44 解耦），不再操作 user_favorites。

    notify=False：抑制逐条通知（started/failed/complete），供批量链路按批汇总使用
    —— 逐条发会在一次运行里产生上百条通知并触发 Telegram 429（2026-09-21 实测
    1119 条中 622 条被拒），故链路改为运行结束发 1 条汇总。
    """
    # 44：所有状态更新目标表为_下载（非_）
    db = None
    standard_number = ""  # 预初始化：异常路径补发失败通知时安全引用（A-3）
    try:
        db = Database(get_db_path())

        cursor = db.execute("SELECT standard_number FROM announcement_record WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        if not row:
            raise FavoriteArchiveError(f"记录不存在: {record_id}")
        standard_number = row["standard_number"]
        if not standard_number:
            raise FavoriteArchiveError(f"标准号为空: {record_id}")

        # 检查是否已有文件（复用）：命中即视为完成，直接返回
        if _reuse_existing_file(db, favorite_id, standard_number, user_id, notify):
            return

        from pilotstd.manager.facade import StandardManager

        mgr = StandardManager()
        query_result = _resolve_download_target(mgr, db, favorite_id, standard_number)

        # 校验通过后再通知用户下载开始（避免"有始无终"）
        _notify_download_started(user_id, standard_number, favorite_id, notify)
        db.execute(
            "UPDATE favorite_downloads SET status = 'downloading', updated_at = datetime('now') WHERE favorite_id = ?",
            (favorite_id,),
        )

        inbox_dir = _get_inbox_dir()
        inbox_dir.mkdir(parents=True, exist_ok=True)
        suffix = str(favorite_id)[-6:]
        inbox_path = inbox_dir / _safe_filename(standard_number, suffix)

        if not inbox_path.exists():
            _fetch_into_inbox(mgr, query_result, standard_number, inbox_path)

        db.execute(
            "UPDATE favorite_downloads SET status = 'archiving', local_path = ?,"
            " updated_at = datetime('now') WHERE favorite_id = ?",
            (str(inbox_path), favorite_id),
        )

        for _ in range(30):
            time.sleep(2)
            found = _find_in_file_index(standard_number, db)
            if found:
                db.execute(
                    "UPDATE favorite_downloads SET status = 'done', local_path = ?,"
                    " updated_at = datetime('now') WHERE favorite_id = ?",
                    (found, favorite_id),
                )
                logger.info("归档完成: %s", found)
                # 扫描器已把文件登记到索引，通知用户下载归档全流程完成
                _notify_download_complete(user_id, standard_number, favorite_id, found, notify)
                return

        db.execute(
            "UPDATE favorite_downloads SET status = 'failed', error_message = ?,"
            " updated_at = datetime('now') WHERE favorite_id = ?",
            ("归档超时：文件未被扫描器处理", favorite_id),
        )
        logger.warning("收藏归档超时: favorite_id=%s", favorite_id)
        # 归档超时补发下载失败通知（避免用户只收到"开始下载"再无后续）
        _notify_download_failed(user_id, standard_number, "归档超时：文件未被扫描器处理", favorite_id, notify)

    except FavoriteSkip:  # 终态跳过不写 failed（否则链路按失败重试 7 次），原样上抛由链条置终态
        raise
    except Exception as e:
        logger.error("收藏失败: favorite_id=%s, %s", favorite_id, e, exc_info=True)
        if db:
            db.execute(
                "UPDATE favorite_downloads SET status = 'failed', error_message = ?,"
                " updated_at = datetime('now') WHERE favorite_id = ?",
                (str(e), favorite_id),
            )
        # 异常路径补发下载失败通知（链接缺失等场景不再"有始无终"）
        if standard_number:
            _notify_download_failed(user_id, standard_number, str(e), favorite_id, notify)
    finally:
        if db:
            db.close()
