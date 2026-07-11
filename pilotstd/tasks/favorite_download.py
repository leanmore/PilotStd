# pilotstd/tasks/favorite_download.py
# Phase 4a: 收藏下载归档任务
#
# 流程:
#   1. 从 standard_info_cache 获取下载链接
#   2. requests 直接下载 PDF 到 inbox 目录（文件名带唯一后缀防并发覆盖）
#   3. 轮询 file_index 等待扫描器自动归档
#   4. 更新 user_favorites 状态
#
# 依赖: ConfigManager / Database / StandardParser / requests

import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests

from pilotstd.core.config import ConfigManager, get_db_path
from pilotstd.core.db.database import Database
from pilotstd.organizer.industry_lookup import build_code_mapping
from pilotstd.scan.parser import StandardParser

logger = logging.getLogger(__name__)


class FavoriteArchiveError(Exception):
    pass


def get_download_url(standard_number: str, db: Database) -> Optional[str]:
    """从 standard_info_cache 获取下载链接。"""
    cursor = db.execute(
        "SELECT result_json FROM standard_info_cache WHERE standard_number = ? ORDER BY cached_at DESC LIMIT 1",
        (standard_number,),
    )
    row = cursor.fetchone()
    if row and row.get("result_json"):
        try:
            data = json.loads(row["result_json"])
            url = data.get("download_url")
            if url:
                return url
        except Exception:
            pass
    return None


def download_file(url: str, target_path: Path, timeout: int = 60) -> bool:
    """直接用 requests 下载文件，不依赖 DownloadEngine。"""
    try:
        resp = requests.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True
    except Exception as e:
        logger.error("下载失败: %s, %s", url, e)
        return False


def _safe_filename(standard_number: str, suffix: str) -> str:
    """生成安全文件名（替换 Windows 非法字符 + 唯一后缀防并发覆盖）。"""
    safe = standard_number
    for ch in r'\/:*?"<>|':
        safe = safe.replace(ch, "_")
    return f"{safe}_{suffix}.pdf"


def find_in_file_index(standard_number: str, db: Database, parser: StandardParser) -> Optional[str]:
    """在 file_index 中查找标准文件路径。精确匹配 + LIKE 降级。"""
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
            return row["file_path"]

    # 降级：LIKE 模糊匹配
    pattern = f"%{standard_number.replace('/', '_')}%"
    cursor = db.execute("SELECT file_path FROM file_index WHERE file_path LIKE ? LIMIT 1", (pattern,))
    row = cursor.fetchone()
    return row["file_path"] if row else None


def _poll_until_archived(standard_number: str, db: Database, parser: StandardParser, favorite_id: int) -> bool:
    """轮询 file_index 等待扫描器归档。返回 True 表示成功。"""
    for _ in range(30):
        time.sleep(2)
        found = find_in_file_index(standard_number, db, parser)
        if found:
            db.execute(
                "UPDATE user_favorites SET status = 'done', local_path = ?, updated_at = datetime('now') WHERE id = ?",
                (found, favorite_id),
            )
            logger.info("收藏归档完成: favorite_id=%s, path=%s", favorite_id, found)
            return True
    return False


def download_to_inbox(favorite_id: int, user_id: int, record_id: int) -> None:
    """收藏下载任务：下载 PDF 到 inbox → 轮询 file_index → 更新状态。"""
    db = None
    try:
        cfg = ConfigManager()
        db = Database(get_db_path())

        cursor = db.execute("SELECT standard_number FROM announcement_record WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        if not row:
            raise FavoriteArchiveError(f"记录不存在: {record_id}")
        standard_number = row.get("standard_number")
        if not standard_number:
            raise FavoriteArchiveError(f"标准号为空: {record_id}")

        db.execute(
            "UPDATE user_favorites SET status = 'downloading', updated_at = datetime('now') WHERE id = ?",
            (favorite_id,),
        )

        download_url = get_download_url(standard_number, db)
        if not download_url:
            raise FavoriteArchiveError(f"无法获取下载链接: {standard_number}")

        inbox_dir = Path(cfg.get("storage.inbox_dir", "/inbox"))
        inbox_dir.mkdir(parents=True, exist_ok=True)
        suffix = str(favorite_id)[-6:]
        inbox_path = inbox_dir / _safe_filename(standard_number, suffix)

        if not inbox_path.exists():
            if not download_file(download_url, inbox_path):
                raise FavoriteArchiveError(f"下载失败: {standard_number}")

        db.execute(
            "UPDATE user_favorites SET status = 'archiving', local_path = ?, updated_at = datetime('now') WHERE id = ?",
            (str(inbox_path), favorite_id),
        )

        parser = StandardParser(build_code_mapping())
        if not _poll_until_archived(standard_number, db, parser, favorite_id):
            db.execute(
                "UPDATE user_favorites SET status = 'failed', error_message = ?,"
                " updated_at = datetime('now') WHERE id = ?",
                ("归档超时：文件未被扫描器处理", favorite_id),
            )
            logger.warning("收藏归档超时: favorite_id=%s", favorite_id)

    except Exception as e:
        logger.error("收藏失败: favorite_id=%s, %s", favorite_id, e, exc_info=True)
        if db:
            db.execute(
                "UPDATE user_favorites SET status = 'failed', error_message = ?,"
                " updated_at = datetime('now') WHERE id = ?",
                (str(e), favorite_id),
            )
    finally:
        if db:
            db.close()
