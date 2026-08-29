# 模块：项目//_下载脚本
# 阶段4:收藏下载归档任务

import json
import logging
import time
from pathlib import Path
from typing import Optional, cast

import requests

from pilotstd.core.config import ConfigManager, get_db_path
from pilotstd.core.db.database import Database
from pilotstd.organizer.industry_lookup import build_code_mapping
from pilotstd.scan.parser import StandardParser

logger = logging.getLogger(__name__)
# 收藏下载归档过程中的异常


class FavoriteArchiveError(Exception):
    """收藏下载归档过程中的异常。"""

    pass


def _get_inbox_dir() -> Path:
    """从配置中获取 inbox 目录路径。"""
    cfg = ConfigManager()
    return Path(cfg.get("storage.inbox_dir", "/inbox"))


def _get_download_url(standard_number: str, db: Database) -> Optional[str]:
    """从缓存中查询标准的下载链接。"""
    cursor = db.execute(
        "SELECT result_json FROM standard_info_cache WHERE standard_number = ? ORDER BY cached_at DESC LIMIT 1",
        (standard_number,),
    )
    row = cursor.fetchone()
    if row and row["result_json"]:
        try:
            data = json.loads(row["result_json"])
            return cast("str | None", data.get("download_url"))
        except Exception:
            pass
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


def _download_with_retry(
    url: str, target_path: Path, max_retries: int = 3, timeout: int = 60
) -> tuple[bool, Optional[str]]:
    """带重试的下载，指数退避。返回 (成功, 错误信息)。"""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, timeout=timeout, stream=True)
            resp.raise_for_status()
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            logger.info("下载成功 (attempt %d/%d)", attempt, max_retries)
            return True, None
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            logger.warning("下载失败 (attempt %d/%d): %s", attempt, max_retries, e)
            if attempt < max_retries:
                time.sleep(2**attempt)
    return False, last_error


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


def _notify_download_failed(user_id: int, standard_number: str, error: str, favorite_id: int) -> None:
    """通知用户下载失败。"""
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


def _notify_download_started(user_id: int, standard_number: str, favorite_id: int) -> None:
    """通知用户下载开始。

    在下载任务进入执行阶段（状态置为 downloading 前）发送，
    让用户感知收藏的自动下载流程已启动；通知失败仅记录日志，
    绝不中断下载主流程。
    """
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


def _notify_download_complete(user_id: int, standard_number: str, favorite_id: int, local_path: str) -> None:
    """通知用户下载归档完成。

    文件已在标准库 file_index 登记（done 状态）后发送；
    local_path 为归档后的实际存储路径，供用户直接定位。
    通知失败仅记录日志，不影响已完成的下载归档结果。
    """
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
def download_to_inbox(favorite_id: int, user_id: int, record_id: int) -> None:
    """收藏下载任务：复用已有文件 → 下载到 inbox → 轮询 file_index → 更新状态。
    所有状态更新写入 favorite_downloads 表（v44 解耦），不再操作 user_favorites。"""
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

        # 检查是否已有文件（复用）
        existing = _find_in_file_index(standard_number, db)
        if existing:
            db.execute(
                "UPDATE favorite_downloads SET status = 'done', local_path = ?,"
                " updated_at = datetime('now') WHERE favorite_id = ?",
                (existing, favorite_id),
            )
            logger.info("复用已有文件: %s", existing)
            # 复用路径同样视为下载归档完成，通知用户文件已就绪
            _notify_download_complete(user_id, standard_number, favorite_id, existing)
            return

        # 先校验下载链接可用性，再通知用户下载开始（A-2：避免"有始无终"——
        # URL 缺失时不应误发"开始下载"通知）
        download_url = _get_download_url(standard_number, db)
        if not download_url:
            raise FavoriteArchiveError(f"无法获取下载链接: {standard_number}")

        _notify_download_started(user_id, standard_number, favorite_id)
        db.execute(
            "UPDATE favorite_downloads SET status = 'downloading', updated_at = datetime('now') WHERE favorite_id = ?",
            (favorite_id,),
        )

        inbox_dir = _get_inbox_dir()
        inbox_dir.mkdir(parents=True, exist_ok=True)
        suffix = str(favorite_id)[-6:]
        inbox_path = inbox_dir / _safe_filename(standard_number, suffix)

        if not inbox_path.exists():
            ok, err = _download_with_retry(download_url, inbox_path, max_retries=3)
            if not ok:
                # 不在此处发送失败通知：raise 后由下方 except 块统一补发一次
                # （避免同一失败路径双通知——内层原始错误 + 外层包装错误）
                raise FavoriteArchiveError(f"下载失败(重试3次): {standard_number}, {err}")

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
                _notify_download_complete(user_id, standard_number, favorite_id, found)
                return

        db.execute(
            "UPDATE favorite_downloads SET status = 'failed', error_message = ?,"
            " updated_at = datetime('now') WHERE favorite_id = ?",
            ("归档超时：文件未被扫描器处理", favorite_id),
        )
        logger.warning("收藏归档超时: favorite_id=%s", favorite_id)
        # A-4：归档超时补发下载失败通知（避免用户只收到"开始下载"再无后续）
        _notify_download_failed(user_id, standard_number, "归档超时：文件未被扫描器处理", favorite_id)

    except Exception as e:
        logger.error("收藏失败: favorite_id=%s, %s", favorite_id, e, exc_info=True)
        if db:
            db.execute(
                "UPDATE favorite_downloads SET status = 'failed', error_message = ?,"
                " updated_at = datetime('now') WHERE favorite_id = ?",
                (str(e), favorite_id),
            )
        # A-3：异常路径补发下载失败通知（URL 缺失等场景不再"有始无终"）
        if standard_number:
            _notify_download_failed(user_id, standard_number, str(e), favorite_id)
    finally:
        if db:
            db.close()
