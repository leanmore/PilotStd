# 模块：项目/核心/_检查器脚本
# 标准时效性检查模块 — 跟踪标准现行/废止状态变更
# 1:本地公告缓存表2:网络适配器查询3:历史状态对比

import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pilotstd.core.time_utils import iso_now

from .db import Database
from .status import ABOLISHED_STATUSES_WITH_EXPIRED, Status, normalize_status

logger = logging.getLogger(__name__)

_TABLE = "standard_validity"


class ValidityChecker:
    """标准时效性检查器。

    三级检查策略：
      L1 — 查 announcement_match / announcement_record
      L2 — 查适配器（QueryEngine 实时查询）
      L3 — 对比 standard_validity 历史记录
    """

    def __init__(self, db: Database):
        self._db = db
        self._ensure_last_changed_at_column()

    def _ensure_last_changed_at_column(self) -> None:
        """确保 standard_validity 表存在 last_changed_at 字段（首次启动自动迁移）。"""
        try:
            cols = self._db.fetchall("PRAGMA table_info(standard_validity)")
            col_names = [c["name"] for c in cols]
            if "last_changed_at" not in col_names:
                self._db.execute("ALTER TABLE standard_validity ADD COLUMN last_changed_at TEXT")
                self._db.execute("UPDATE standard_validity SET last_changed_at = updated_at")
                logger.info("standard_validity 表已添加 last_changed_at 字段并回填")
        except Exception as e:
            logger.warning("last_changed_at 迁移跳过: %s", e)

    # ── 注册新标准 ──────────────────────────────────────────────

    def register_new_standard(self, standard_number: str, notification_mgr: Any = None) -> None:
        """归档后注册新标准，初始状态='未知'，next_check_at=now（立即可查）。"""
        now = datetime.now(timezone.utc).isoformat()
        # 单条 INSERT OR IGNORE：并发首次登记不会撞 standard_number 唯一键，
        # 也不会在 SELECT 与 INSERT 之间被另一个线程抢先插入。
        cursor = self._db.execute(
            f"INSERT OR IGNORE INTO {_TABLE} "
            "(standard_number, status, next_check_at, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (standard_number, Status.UNKNOWN.value, now, now, now),
        )
        if not getattr(cursor, "rowcount", 0):
            return
        if notification_mgr:
            try:
                notification_mgr.send_event(
                    "standard_first_registered",
                    {
                        "standard_number": standard_number,
                    },
                )
            except Exception as e:
                logger.warning("首次登记通知发送失败: %s, error=%s", standard_number, e)

    # ── 状态更新 ──────────────────────────────────────────────

    def should_apply_side_effects(self, evidence: str) -> bool:
        """是否允许执行有副作用的动作（搬文件/入下载队列）。

        只有 **L2（适配器实时查询）** 的结论才够格：L1 是名称关键词猜测、L3 是历史行，
        二者单独命中「废止/被代替」不得搬文件或入队（2026-11-03 修）。
        默认关闭（`validity.auto_move_expired=false`）：要自动搬文件必须显式开启。
        """
        if evidence != "L2":
            return False
        from .config import ConfigManager

        return bool(ConfigManager().get("validity.auto_move_expired", False))

    def update_status(
        self,
        standard_number: str,
        new_status: str,
        notification_mgr: Any = None,
        new_standard: str = "",
        new_standard_name: str = "",
        evidence: str = "L3",
    ) -> None:
        """更新标准时效性状态，设置下次检查时间=now + total_weeks*7 天。
        状态变更时同步更新 last_changed_at，未变化时仅更新 updated_at。
        evidence 标记结论来源（L1/L2/L3），决定是否允许搬文件等副作用。
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        from .config import ConfigManager

        total_weeks = ConfigManager().get("validity.total_weeks", 4)
        next_check = (now + timedelta(days=total_weeks * 7)).isoformat()
        row = self._db.fetchone(
            f"SELECT status, check_count FROM {_TABLE} WHERE standard_number=?",
            (standard_number,),
        )
        status_changed = bool(row and row["status"] != new_status)
        should_move = (
            status_changed
            and new_status in ABOLISHED_STATUSES_WITH_EXPIRED
            and self.should_apply_side_effects(evidence)
        )
        # 先搬文件、成功后再写库：移动失败时保持原状态（下一轮重试），
        # 绝不出现“库说废止、文件还在原位”的不一致（D3-1）。
        if should_move and not self._move_files_before_abandon(standard_number, new_status):
            return
        if not row:
            self._db.execute(
                f"INSERT INTO {_TABLE} (standard_number, status, last_checked_at, "
                "next_check_at, last_changed_at, check_count, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (standard_number, new_status, now_iso, next_check, now_iso, now_iso, now_iso),
            )
            return
        if not status_changed:
            self._db.execute(
                f"UPDATE {_TABLE} SET last_checked_at=?, next_check_at=?, "
                "check_count=check_count+1, updated_at=? WHERE standard_number=?",
                (now_iso, next_check, now_iso, standard_number),
            )
            return
        self._db.execute(
            f"UPDATE {_TABLE} SET status=?, last_checked_at=?, next_check_at=?, "
            "last_status=?, last_status_updated_at=?, last_changed_at=?, "
            "check_count=check_count+1, updated_at=? WHERE standard_number=?",
            (new_status, now_iso, next_check, row["status"], now_iso, now_iso, now_iso, standard_number),
        )
        self._notify_status_changed(
            notification_mgr, standard_number, new_status, row["status"], new_standard, new_standard_name
        )
        if new_status in ABOLISHED_STATUSES_WITH_EXPIRED and not should_move:
            logger.info(
                # i18n-allow: 内部日志
                "validity: 不自动搬文件（证据=%s，需 L2 + auto_move_expired）: %s",
                evidence,
                standard_number,
            )

    def _move_files_before_abandon(self, standard_number: str, new_status: str) -> bool:
        """搬文件成功返回 True；失败返回 False（调用方放弃写废止状态）。"""
        moved = self._move_expired_file(standard_number, new_status)
        if moved is None:
            logger.warning(
                # i18n-allow: 内部运维日志
                "validity: 文件移动失败，暂不写废止状态，等待下轮重试: %s",
                standard_number,
            )
            return False
        for old_path, new_path in moved:
            # 移动成功后回写索引，避免查询结果指向已不存在的旧路径（D3-3）
            self._db.execute(
                "UPDATE file_index SET file_path=?, status=? WHERE file_path=?",
                (new_path, new_status, old_path),
            )
        return True

    def _notify_status_changed(
        self,
        notification_mgr: Any,
        standard_number: str,
        new_status: str,
        old_status: str,
        new_standard: str,
        new_standard_name: str,
    ) -> None:
        """发送状态变更通知（废止并入本事件，用 is_expired 区分）。"""
        if not notification_mgr:
            return
        try:
            standard_name = ""
            try:
                name_row = self._db.fetchone(
                    "SELECT std_name FROM announcement_record WHERE standard_number=? LIMIT 1",
                    (standard_number,),
                )
                if name_row and "std_name" in name_row.keys():
                    standard_name = str(name_row["std_name"] or "")
            except (KeyError, IndexError, TypeError):
                standard_name = ""
            payload = {
                "standard_number": standard_number,
                "old_status": old_status,
                "new_status": new_status,
                "is_expired": new_status == Status.WITHDRAWN_NORMALIZED.value,
                "changed_at": iso_now(),
            }
            if standard_name:
                payload["standard_name"] = standard_name
            if new_standard:
                payload["new_standard"] = new_standard
                payload["new_standard_name"] = new_standard_name
            notification_mgr.send_event("standard_status_changed", payload)
        except Exception as e:
            logger.warning("状态变更通知发送失败: %s, error=%s", standard_number, e)

    # ── 到期标准查询 ──────────────────────────────────────────

    def _move_expired_file(
        self, standard_number: str, new_status: str
    ) -> Optional[list[tuple[str, str]]]:
        """把该标准对应文件移到“过期作废”目录，返回 `[(旧路径, 新路径)]`。

        返回 `None` 表示**至少一个文件移动失败**——调用方据此放弃写“废止”状态，
        避免库与磁盘不一致（D3-1）。
        选取范围精确到 `part`（D3-4），并排除修改单文件（修改单随本体，不单独搬）。
        """
        import os

        from ..organizer.dir_builder import DirBuilder
        from ..organizer.industry_lookup import build_code_mapping
        from ..organizer.mover import FileMover
        from ..scan.parser import StandardParser
        from .config import ConfigManager, get_library_root
        from .std_utils import parse_std_number

        parsed = parse_std_number(standard_number)
        if not parsed:
            logger.warning("无法解析标准号，跳过搬文件: %s", standard_number)  # i18n-allow: 内部日志
            return []
        part = parsed.get("part")
        raw_code = str(parsed["raw_code"])
        normalized = raw_code.replace("/", "")
        slash = f"{normalized[:2]}/{normalized[2:]}" if len(normalized) > 2 else normalized
        codes = tuple({raw_code, normalized, slash})
        placeholders = ",".join("?" for _ in codes)
        expire_name = str(ConfigManager().get("storage.expire_folder", "过期作废") or "过期作废")
        try:
            root = get_library_root(ConfigManager())
            dir_builder = DirBuilder(root, expire_dir_name=expire_name)
            mover = FileMover(dir_builder)
            rows = self._db.fetchall(
                "SELECT file_path, std_name FROM file_index"
                f" WHERE logical_code IN ({placeholders}) AND number=? AND year=?"  # i18n-allow: SQL
                "   AND (? IS NULL OR part = ?)"
                "   AND COALESCE(std_name,'') NOT LIKE '%修改单%'"
                "   AND COALESCE(file_path,'') NOT LIKE '%修改单%'",  # i18n-allow: SQL 含中文关键词“修改单”
                (*codes, parsed["number"], parsed["year"], part, part),
            )
        except Exception as exc:  # noqa: BLE001 — 查询/构造失败视为本轮失败，交由上层放弃写库
            logger.warning("准备搬文件失败: %s (%s)", standard_number, exc)  # i18n-allow: 内部日志
            return None

        moved: list[tuple[str, str]] = []
        failed: list[str] = []
        for row in rows:
            path = str(row["file_path"] or "")
            if not path or expire_name in path.replace("\\", "/").split("/"):
                continue
            info = StandardParser(build_code_mapping()).parse(os.path.basename(path))
            if not info:
                continue
            info.source_path = path
            info.effect_status = new_status
            try:
                dst = mover.move_to_code_dir(path, info)
            except Exception as exc:  # noqa: BLE001 — 单个文件异常不应中断其余文件
                logger.warning("移动过期文件异常: %s (%s)", path, exc)  # i18n-allow: 内部日志
                dst = None
            if dst:
                moved.append((path, dst))
            else:
                failed.append(path)
        if failed:
            # 回滚已搬走的文件：否则“不再写废止状态”的下一轮会拿着失效的旧路径重试，
            # 形成永久停滞（2026-11-04 审计风险 3）。
            self._rollback_moves(moved)
            logger.warning(
                "过期文件移动失败 %d 个，已回滚 %d 个，保持原状态待重试: %s %s",  # i18n-allow: 内部日志
                len(failed),
                len(moved),
                standard_number,
                failed,
            )
            return None
        return moved

    @staticmethod
    def _rollback_moves(moved: list[tuple[str, str]]) -> None:
        """把已移动的文件搬回原路径（尽力而为，失败只记日志）。"""
        import os
        import shutil

        for old_path, new_path in reversed(moved):
            try:
                if os.path.exists(new_path) and not os.path.exists(old_path):
                    os.makedirs(os.path.dirname(old_path), exist_ok=True)
                    shutil.move(new_path, old_path)
            except OSError as exc:
                # i18n-allow: 内部运维日志
                logger.error("回滚过期文件失败: %s -> %s (%s)", new_path, old_path, exc)

    def _file_index_exists(self) -> bool:
        """兼容测试替身/旧库：没有 file_index 表时不做路径排除。"""
        rows = self._db.fetchall("PRAGMA table_info(file_index)")
        return bool(rows)

    def _exclude_expired_sql(self) -> tuple[str, str]:
        """排除 file_index 中路径含“过期作废”子目录的标准。"""
        if not self._file_index_exists():
            return "", ""
        from .config import ConfigManager

        folder = str(ConfigManager().get("storage.expire_folder", "过期作废") or "过期作废")  # i18n-allow: 配置默认值
        pattern = f"%/{folder}/%"
        clause = (
            " AND NOT EXISTS ("
            " SELECT 1 FROM file_index f"
            " WHERE REPLACE(f.file_path, '\\\\', '/') LIKE ?"
            " AND (f.logical_code || ' ' || f.number ||"
            " CASE WHEN f.part > 0 THEN '.' || f.part ELSE '' END ||"
            " CASE WHEN f.year > 0 THEN '-' || f.year ELSE '' END) = v.standard_number)"
        )
        return clause, pattern

    def get_due_standards(self) -> list[str]:
        """查询所有 next_check_at <= now 的到期标准号。"""
        now = datetime.now(timezone.utc).isoformat()
        clause, pattern = self._exclude_expired_sql()
        params: tuple[Any, ...] = (now,) if not clause else (now, pattern)
        rows = self._db.fetchall(
            f"SELECT standard_number FROM {_TABLE} v"
            f" WHERE next_check_at <= ?{clause} ORDER BY next_check_at ASC",
            params,
        )
        return [r["standard_number"] for r in rows]

    def count_due_standards(self) -> int:
        """到期标准总数（轻量 COUNT 查询，不加载数据）。"""
        now = datetime.now(timezone.utc).isoformat()
        clause, pattern = self._exclude_expired_sql()
        params: tuple[Any, ...] = (now,) if not clause else (now, pattern)
        row = self._db.fetchone(
            f"SELECT COUNT(*) as cnt FROM {_TABLE} v WHERE next_check_at <= ?{clause}",
            params,
        )
        return row["cnt"] if row else 0

    def get_due_standards_random(self, limit: int) -> list[str]:
        """随机采样 limit 条到期标准号（数据库层 ORDER BY RANDOM() + LIMIT，避免全量加载到 Python 内存）。"""
        now = datetime.now(timezone.utc).isoformat()
        clause, pattern = self._exclude_expired_sql()
        params: tuple[Any, ...] = (now, limit) if not clause else (now, pattern, limit)
        rows = self._db.fetchall(
            f"SELECT standard_number FROM {_TABLE} v WHERE next_check_at <= ?{clause}"
            " ORDER BY RANDOM() LIMIT ?",
            params,
        )
        return [r["standard_number"] for r in rows]

    @staticmethod
    def random_slice(candidates: list[str], week_number: int, batch_size: int = 50) -> list[str]:
        """从候选列表中随机切片取约 1/4（固定种子，同周结果一致）。"""
        if not candidates:
            return []
        # 复制后，避免修改原列表
        shuffled = list(candidates)
        rng = random.Random(week_number)
        rng.shuffle(shuffled)
        start = (week_number % max(1, (len(shuffled) + batch_size - 1) // batch_size)) * batch_size
        return shuffled[start : start + batch_size]

    # ── 状态检查 ──────────────────────────────────────────────

    def check_standard(
        self,
        standard_number: str,
        query_engine: Any = None,
    ) -> Optional[dict[str, Optional[str]]]:
        """检查单个标准的时效性状态。

        L1 — 查本地公告缓存（announcement_match + announcement_record）
        L2 — 查适配器实时查询（需传 query_engine）
        L3 — 对比历史状态记录

        返回: {"status": str, "previous": str|None} 或 None（查询失败）
        """
        # ──1:公告缓存表（只信“否定”，不信“肯定”，且不阻断 L2）──
        try:
            # 1a. 优先读 matcher 已算好的结构化状态（被代替/现行/即将实施）
            cached = normalize_status(self._cached_announcement_status(standard_number))
            if cached in ABOLISHED_STATUSES_WITH_EXPIRED:
                info: dict[str, Optional[str]] = {
                    "status": cached,
                    "previous": None,
                    "evidence": "L1",
                }
                info.update(self._replacement_info(standard_number))
                return info
            # 1b. 名称关键词只作为“废止”的正证据；不再把“公告里出现过”当成现行证据，
            #     否则适配器（L2）永远看不到真实状态（2026-11-04 实测：适配器调用 0 次）。
            row = self._db.fetchone(
                # i18n-allow: SQL 里匹配中文关键词“修改单”
                "SELECT std_name FROM announcement_record"
                " WHERE standard_number=? AND COALESCE(std_name,'') NOT LIKE '%修改单%' LIMIT 1",
                (standard_number,),
            )
            if row and self._name_says_abolished(str(row.get("std_name") or "")):
                info = {
                    "status": Status.WITHDRAWN_NORMALIZED.value,
                    "previous": None,
                    "evidence": "L1",
                }
                info.update(self._replacement_info(standard_number))
                return info
        except Exception:
            logger.exception("查询公告缓存失败: %s", standard_number)  # i18n-allow: 内部日志

        # ──2:适配器实时查询──
        if query_engine:
            try:
                from ..core.std_utils import parse_std_number

                parsed = parse_std_number(standard_number)
                if parsed:
                    results = query_engine.query_standards(
                        [(parsed["code"], parsed["number"], parsed.get("year", 0), "", None, "")]
                    )
                    if results and results[0].is_found():
                        info = {
                            "status": results[0].status or Status.ACTIVE.value,
                            "previous": None,
                            "evidence": "L2",
                        }
                        info.update(self._replacement_info(standard_number))
                        return info
            except Exception as e:
                # 在线查询失败 → 回落到历史状态对比，但要留痕
                logger.debug("online validity query failed for %s: %s", standard_number, e)

        # ──3:历史状态对比──
        row = self._db.fetchone(
            f"SELECT status, last_status FROM {_TABLE} WHERE standard_number=?",
            (standard_number,),
        )
        if row:
            info = {
                "status": row["status"],
                "previous": row["last_status"],
                "evidence": "L3",
            }
            info.update(self._replacement_info(standard_number))
            return info

        return None

    def _replacement_info(self, standard_number: str) -> dict[str, str]:
        """查替代标准：announcement_record.superseded_by 指向的新标准号。"""
        try:
            row = self._db.fetchone(
                "SELECT superseded_by FROM announcement_record"
                " WHERE standard_number=? AND COALESCE(superseded_by,'')<>'' LIMIT 1",
                (standard_number,),
            )
            if row:
                new_standard = str(row["superseded_by"] or "")
                name_row = self._db.fetchone(
                    "SELECT std_name FROM announcement_record WHERE standard_number=? LIMIT 1",
                    (new_standard,),
                )
                return {
                    "new_standard": new_standard,
                    "new_standard_name": str(name_row["std_name"] or "") if name_row else "",
                }
        except Exception:
            logger.warning("replacement lookup failed for %s", standard_number, exc_info=True)
        return {}

    def _cached_announcement_status(self, standard_number: str) -> str:
        """读 `announcement_match.result_json.status`（matcher 计算的结构化状态）。

        这是公告侧唯一的权威状态来源；`announcement_record` 没有公告类型/状态列，
        只靠名称关键词无法判断“废止”（2026-11-04 审计结论）。
        """
        row = None
        try:
            row = self._db.fetchone(
                "SELECT result_json FROM announcement_match"
                " WHERE standard_number=? ORDER BY cached_at DESC LIMIT 1",
                (standard_number,),
            )
        except Exception as exc:  # noqa: BLE001 — 读缓存失败按“无状态”处理，但必须留痕
            logger.warning("read announcement_match status failed: %s (%s)", standard_number, exc)
        if not row or not row.get("result_json"):
            return ""
        data: dict[str, Any] = {}
        try:
            loaded = json.loads(row["result_json"])
            if isinstance(loaded, dict):
                data = loaded
        except (TypeError, ValueError) as exc:
            logger.warning("invalid announcement_match json: %s (%s)", standard_number, exc)
        return str(data.get("status") or "")

    @staticmethod
    def _name_says_abolished(std_name: str) -> bool:
        """名称里出现废止类词才算“废止”的正证据（保守判定，避免误杀）。"""
        name_lower = (std_name or "").lower()
        return any(
            keyword in name_lower
            for keyword in (
                Status.WITHDRAWN.value,
                Status.VOIDED.value,
                Status.SUPERSEDED.value,
                "abolished",
                "withdrawn",
                "obsolete",
            )
        )

    # ── 统计 ──────────────────────────────────────────────────

    def get_status_summary(self) -> dict[str, int]:
        """返回各状态的标准数量统计。"""
        rows = self._db.fetchall(f"SELECT status, COUNT(*) as cnt FROM {_TABLE} GROUP BY status")
        return {r["status"]: r["cnt"] for r in rows}


# ──流水线函数（已提取至__流水线脚本）──

from ._validity_pipeline import (  # noqa: E402, F401 — 由 API/调度器导入消费
    _finalize_validity_round,
    _process_validity_batch,
    _sample_due_standards,
    run_validity_check,
)
