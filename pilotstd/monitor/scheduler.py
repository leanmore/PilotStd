# 模块：项目//调度器脚本
"""文件监控调度器——管理 watchdog Observer 生命周期。"""

import logging
import os
import threading
import time
from typing import Any

from watchdog.observers import Observer

from .config import (
    get_catchup_watermark,
    get_config,
    get_last_processed,
    get_monitor_stats,
    set_catchup_watermark,
    set_last_processed,
)
from .handler import StandardFileHandler

logger = logging.getLogger(__name__)


def _log_trace_id() -> str:
    """生成日志结构化上下文用的短随机追踪号（线程安全，无依赖）。"""
    import secrets

    return secrets.token_hex(4)


def _cleanup_empty_dirs(watch_root: str, start_dir: str) -> int:
    """删除 start_dir 下（含自身）的空目录，但绝不删除 watch_root 本身。

    只做 `os.rmdir`：目录非空会失败，因此不会误删还有文件的目录。
    返回删除数量；路径不在 watch_root 内时直接返回 0（测试/注入场景安全）。
    """
    try:
        root = os.path.realpath(watch_root)
        start = os.path.realpath(start_dir)
        if os.path.commonpath([root, start]) != root:
            return 0
    except (OSError, ValueError) as exc:
        logger.warning("清理空目录路径校验失败，跳过: %s (%s)", start_dir, exc)  # i18n-allow: 内部运维日志
        return 0

    removed = 0
    for dirpath, _dirnames, _filenames in os.walk(start, topdown=False):
        # 永不删除 watch_root 本身；start==root 时仍要清理它下面的空子目录。
        if os.path.realpath(dirpath) == root:
            continue
        try:
            os.rmdir(dirpath)
            removed += 1
        except OSError:
            # 非空 / 无权限：保留，不阻断归档；非空是正常情况，不刷日志
            continue
    if removed:
        logger.info("[MONITOR] 清理空目录: %d 个", removed)  # i18n-allow: 内部运维日志
    return removed

_instance = None


def resolve_monitor_config(cfg: dict | None = None) -> dict:
    """解析监控配置，支持环境变量覆盖。传入cfg时可纯函数运行，零I/O。

    .. note:: 可测试单元
       在测试中显式传入cfg以避免get_config()的I/O依赖。
    """
    if cfg is None:
        cfg = get_config()
    return {
        "watch_path": (
            os.environ.get("PILOTSTD_STORAGE_INBOX_DIR")
            or cfg.get("watch_path")
            or "/tmp/pilotstd-inbox"
        ),
        "delay_seconds": cfg.get("delay_seconds", 5),
        "recursive": cfg.get("recursive", True),
    }


_scheduler_lock = threading.Lock()


def get_scheduler():
    """返回全局单例 FileMonitorScheduler 实例（并发安全）。"""
    global _instance
    if _instance is None:
        with _scheduler_lock:
            if _instance is None:
                _instance = FileMonitorScheduler()
    return _instance


# 后台线程驱动，文件就绪后触发自动归档
# 全局单例模式，通过_调度器()获取，/管理生命周期
def _count_catchup_files(groups: dict[str, list[str]], kept: list[str]) -> int:
    """统计 kept 目录及其后代目录的文件总数（祖先折叠后不能只数 kept 自身）。"""
    total = 0
    for key, files in groups.items():
        if any(key == k or key.startswith(k.rstrip("/") + "/") for k in kept):
            total += len(files)
    return total


def _covered_by_ancestor(
    path: str, active_dirs: set[str], recent_dirs: dict[str, float], now: float, window: float = 10.0
) -> bool:
    """path 是否已被某个祖先目录的批次覆盖（正在跑，或 10s 内跑过）。

    批次按目录触发时 `auto_run(dir)` 会递归扫描子目录；子目录随后自身的实时事件
    不应再触发一次（2026-11-15 生产复现：a/nested 被 a 批与自身事件各处理一次）。
    """
    for d in active_dirs:
        if path == d or path.startswith(d.rstrip("/") + "/"):
            return True
    for d, ts in recent_dirs.items():
        if (path == d or path.startswith(d.rstrip("/") + "/")) and now - ts < window:
            return True
    return False


class FileMonitorScheduler:
    # 补扫目录之间的间隔（秒）：避免启动瞬间打满查询/下载；stop 时可被立即打断。
    CATCHUP_INTERVAL_SECONDS = 1.0

    def __init__(self, manager: Any = None):
        self.observer: Observer | None = None  # type: ignore[valid-type]
        self.handler: StandardFileHandler | None = None
        self.running = False
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._catchup_stop: threading.Event | None = None
        self._catchup_thread: threading.Thread | None = None
        self._last_processed = ""
        self._mgr = manager  # 依赖注入，避免 monitor→manager 反向导入
        self._mgr_lock = threading.Lock()  # 懒加载 manager 的并发保护
        # 同一目录可能有多个文件事件；只允许一个主链运行，并做短时间去抖
        self._active_dirs: set[str] = set()
        self._recent_dirs: dict[str, float] = {}
        self._dir_lock = threading.Lock()
        # 手动触发补扫的并发保护：同一时刻只允许一个补扫线程（2026-11-15）
        self._catchup_trigger_lock = threading.Lock()

    def start(self):
        """启动文件监控后台线程。"""
        if self.running:
            return
        cfg = get_config()
        if not cfg.get("enabled", True):
            # 批次4：禁用时跳过启动并记录结构化日志（running 保持 False）
            logger.info(
                "监控已禁用，跳过启动: trace_id=%s source_type=monitor_scheduler target_chat_id=-",
                _log_trace_id(),
            )
            return
        self._stop.clear()
        # 每次启动用新的补扫停止信号：旧补扫线程持有旧 Event，stop() 已置位，不会串到新一轮
        self._catchup_stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="file-monitor")
        self._thread.start()
        logger.info("[MONITOR] 启动成功")

    def stop(self):
        """停止文件监控，等待后台线程退出并清理资源。"""
        self._stop.set()
        if self._catchup_stop is not None:
            self._catchup_stop.set()
        if self.observer:
            self.observer.stop()
        if self._thread:
            self._thread.join(timeout=5)
        if self._catchup_thread is not None:
            self._catchup_thread.join(timeout=5)
            self._catchup_thread = None
        self.running = False
        logger.info(
            "监控调度器已停止: trace_id=%s source_type=monitor_scheduler target_chat_id=-",
            _log_trace_id(),
        )

    def _run(self):
        """后台监控循环。

        .. note:: E2E范围
           配置解析通过resolve_monitor_config()测试。
           Observer生命周期+sleep循环需集成/E2E测试。
           参见：docs/testing/playbook.md §UI-layer skip rule #3
        """
        cfg = get_config()
        resolved = resolve_monitor_config(cfg)
        watch_path = resolved["watch_path"]
        delay = resolved["delay_seconds"]
        recursive = resolved["recursive"]

        source = ("env" if os.environ.get("PILOTSTD_STORAGE_INBOX_DIR")
                  else ("db" if cfg.get("watch_path") else "default"))
        logger.info("[MONITOR] watch_path=%s (source=%s)", watch_path, source)
        try:
            os.makedirs(watch_path, exist_ok=True)
        except OSError as e:
            logger.error("[MONITOR] 无法创建 watch_path=%s: %s — 文件监控已禁用", watch_path, e)
            return

        self.handler = StandardFileHandler(callback=self._on_file, delay_seconds=delay)
        self.observer = Observer()
        self.observer.schedule(self.handler, watch_path, recursive=recursive)
        self.observer.start()
        self.running = True
        logger.info("[MONITOR] 监控 %s (recursive=%s delay=%ds)", watch_path, recursive, delay)

        # P3-16 / 08#23：observer 已就绪后再补扫存量，扫不到的窗口由事件兜底。
        if cfg.get("scan_existing_on_start", True) and cfg.get("auto_archive", True):
            if self._catchup_stop is None:
                self._catchup_stop = threading.Event()
            self._last_processed = get_last_processed()
            self._catchup_thread = threading.Thread(
                target=self._catch_up_existing,
                args=(self._catchup_stop,),
                daemon=True,
                name="monitor-catchup",
            )
            self._catchup_thread.start()
        else:
            logger.info(
                "[MONITOR] 启动补扫已禁用（scan_existing_on_start=%s auto_archive=%s）",  # i18n-allow: 内部运维日志
                cfg.get("scan_existing_on_start", True),
                cfg.get("auto_archive", True),
            )

        try:
            while not self._stop.is_set():
                time.sleep(1)
        finally:
            self.observer.stop()
            self.observer.join()
            self.running = False

    def trigger_catchup(self) -> dict[str, object]:
        """手动触发一次启动补扫（admin 端点用）。

        并发与 watermark 语义：
        - 同一时刻只允许一个补扫；已在跑时返回 started=False，不排队；
        - watermark 仍由 `_catch_up_existing` 在**正常跑完**时设为 `scan_started`：
          补扫期间新写入的文件 mtime 会晚于该值，下次仍会被处理，不会被推前跳过；
        - 与实时 monitor 共用 `_on_file` 的目录级去重（`_active_dirs`/`_recent_dirs`），
          同一目录不会被实时与补扫重复处理。
        """
        # 允许“先 stop 再补扫”（62 批前置：停实时 → 投放 → catchup → start）：
        # observer 停止后 handler 仍在，_catch_up_existing 可独立跑；start() 会重建 observer。
        if not self.running and self.handler is None:
            return {"started": False, "reason": "monitor not running"}
        with self._catchup_trigger_lock:
            if self._catchup_thread is not None and self._catchup_thread.is_alive():
                return {"started": False, "reason": "catchup already running"}
            stop = threading.Event()
            self._catchup_stop = stop
            self._catchup_thread = threading.Thread(
                target=self._catch_up_existing,
                args=(stop,),
                daemon=True,
                name="monitor-catchup-manual",
            )
            self._catchup_thread.start()
            return {"started": True, "reason": ""}

    def _collect_catchup_groups(self, watch_path, recursive, watermark, cfg, stop_event):
        """遍历 watch_path，按父目录收集 mtime 晚于 watermark 的待补扫文件。"""
        groups: dict[str, list[str]] = {}
        skipped = 0
        try:
            for dirpath, dirnames, filenames in os.walk(watch_path):
                if stop_event.is_set():
                    return groups, skipped
                for name in filenames:
                    path = os.path.join(dirpath, name)
                    if self.handler is None or not self.handler._should_handle(path, cfg=cfg):
                        continue
                    try:
                        mtime = os.path.getmtime(path)
                    except OSError:
                        continue
                    if mtime <= watermark:
                        skipped += 1
                        continue
                    groups.setdefault(dirpath, []).append(path)
                if not recursive:
                    dirnames[:] = []
        except OSError as e:
            logger.warning("[MONITOR] 启动补扫遍历失败，跳过本轮: %s", e)  # i18n-allow: 内部运维日志
            return {}, skipped
        return groups, skipped

    @staticmethod
    def _collapse_catchup_dirs(groups: dict[str, list[str]], watch_path: str) -> list[str]:
        """祖先目录折叠：父目录的 auto_run 递归扫描会覆盖子目录，返回需处理的目录列表。

        根目录（`watch_path` 自身）里若直接有文件，**不能**把它和子目录一起折叠：
        否则 `auto_run(watch_path)` 会把 825 个文件塞进**一个**超大批次（实测 2026-11-13
        远程：根下 3 个散件 + 62 个子目录 → 只生成 1 批）。根散件改为**最后单独一批**，
        此时子目录已被前面的批次排空，根批次只会处理散件。
        """
        root = os.path.normpath(watch_path)
        kept: list[str] = []
        for key in sorted(groups):
            if os.path.normpath(key) == root:
                continue
            if any(key == anc or key.startswith(anc + os.sep) for anc in kept):
                continue
            kept.append(key)
        if any(os.path.normpath(key) == root for key in groups):
            kept.append(root)
        return kept

    def _process_catchup_batches(self, kept, groups, stop_event):
        """逐目录调用 _on_file；返回 (完成目录数, 是否被 stop 打断)。"""
        for idx, key in enumerate(kept, 1):
            if stop_event.is_set():
                logger.info(
                    "[MONITOR] 启动补扫被停止: %d/%d 目录，水位不推进",  # i18n-allow: 内部运维日志
                    idx - 1,
                    len(kept),
                )
                return idx - 1, True
            logger.info(
                "[MONITOR] 启动补扫 %d/%d: %s（%d 文件）",  # i18n-allow: 内部运维日志
                idx,
                len(kept),
                key,
                _count_catchup_files(groups, [key]),
            )
            self._on_file(groups[key][0])
            if idx < len(kept) and stop_event.wait(self.CATCHUP_INTERVAL_SECONDS):
                logger.info(
                    "[MONITOR] 启动补扫被停止: %d/%d 目录，水位不推进",  # i18n-allow: 内部运维日志
                    idx,
                    len(kept),
                )
                return idx, True
        return len(kept), False

    def _catch_up_existing(self, stop_event: threading.Event):
        """启动补扫：处理 watch_path 下**已存在**的文件（08#23 / P3-16）。

        设计要点：
        - 只处理 mtime 晚于 `catchup_watermark` 的文件；watermark 默认 0 ⇒ 首次启动全处理；
        - 按**父目录**分批（`auto_run(dir)` 会递归扫子目录），祖先目录折叠后代，避免重复扫描；
        - 每批一次 `_on_file`，复用去抖/锁/空目录清理，一批 ≈ 一条通知；
        - 目录间 `CATCHUP_INTERVAL_SECONDS` 间隔，`stop` 可立即打断；被打断时不推进 watermark。

        注意：`auto_run` 在 worker 线程里跑，超大目录会持续较久；daemon 线程在进程退出时中断，
        此时 watermark 未推进，下次启动会重扫（已处理的文件已被搬走，不会重复）。
        """
        cfg = get_config()
        watch_path = resolve_monitor_config(cfg)["watch_path"]
        if not os.path.isdir(watch_path):
            logger.warning("[MONITOR] 启动补扫跳过：watch_path 不存在 %s", watch_path)  # i18n-allow: 内部运维日志
            return
        watermark = get_catchup_watermark()
        scan_started = time.time()
        groups, skipped = self._collect_catchup_groups(
            watch_path, bool(cfg.get("recursive", True)), watermark, cfg, stop_event
        )
        if stop_event.is_set():
            return
        if not groups:
            set_catchup_watermark(scan_started)
            logger.info(
                "[MONITOR] 启动补扫: 无待处理文件（watermark=%.3f，跳过 %d 个旧文件）",  # i18n-allow: 内部运维日志
                watermark,
                skipped,
            )
            return
        kept = self._collapse_catchup_dirs(groups, watch_path)
        total_files = _count_catchup_files(groups, kept)
        logger.info(
            "[MONITOR] 启动补扫开始: %d 目录 / %d 文件（watermark 跳过 %d）",  # i18n-allow: 内部运维日志
            len(kept),
            total_files,
            skipped,
        )
        done, interrupted = self._process_catchup_batches(kept, groups, stop_event)
        if interrupted:
            return
        set_catchup_watermark(scan_started)
        logger.info(
            "[MONITOR] 启动补扫完成: %d 目录 / %d 文件", done, total_files  # i18n-allow: 内部运维日志
        )

    def _on_file(self, path: str):
        """文件稳定后触发：解析 → 归档 → 按**真实归档结果**计数。

        计数口径（技术债 #30）：`success` 必须是"真归档成功"，不能是"文件名解析出来了"。
        改前只调 `scan_directory`（仅解析、不搬文件、不写 `file_index`）却照记 success，
        现场出现 `processed_today=6 / success_today=6` 而 inbox 里 6 个文件一个都没入库
        → 面板显示健康、实际什么都没发生（`auto_archive` 开关形同虚设）。
        """
        cfg = get_config()
        if not cfg.get("auto_archive", True):
            logger.info("[MONITOR] 自动归档已禁用，跳过: %s", path)  # i18n-allow: 内部运维日志
            return

        stats = get_monitor_stats()
        stats.increment("processed")
        watch_path = resolve_monitor_config(cfg)["watch_path"]
        source_root = os.path.dirname(path)
        now = time.monotonic()

        # 同一目录只跑一条主链：并发回调直接跳过，10 秒内也不重复触发
        with self._dir_lock:
            last = self._recent_dirs.get(source_root, 0.0)
            if _covered_by_ancestor(source_root, self._active_dirs, self._recent_dirs, now):
                logger.info("[MONITOR] 已被祖先目录批次覆盖/去抖，跳过: %s", path)  # i18n-allow: 内部运维日志
                return
            if source_root in self._active_dirs or now - last < 10:
                logger.info("[MONITOR] 同目录处理中/去抖，跳过: %s", path)  # i18n-allow: 内部运维日志
                return
            self._active_dirs.add(source_root)
            self._recent_dirs[source_root] = now
            if len(self._recent_dirs) > 200:
                cutoff = now - 60
                self._recent_dirs = {k: v for k, v in self._recent_dirs.items() if v >= cutoff}

        try:
            if self._mgr is None:
                # 兼容未注入管理器的场景（自动降级）
                with self._mgr_lock:
                    if self._mgr is None:
                        from pilotstd.manager.facade import StandardManager  # noqa: PLC0415

                        self._mgr = StandardManager()
            # monitor 只负责“发现文件稳定 → 触发主链”，不自己实现 scan+archive。
            report = self._mgr.auto_run(source_root)
            moved = int(report.get("organize_moved", 0) or 0) if isinstance(report, dict) else 0
            scanned = int(report.get("scan", 0) or 0) if isinstance(report, dict) else 0
            failed = int(report.get("organize_failed", 0) or 0) if isinstance(report, dict) else 0
            if moved:
                logger.info("[MONITOR] 主链归档完成: %d 条", moved)  # i18n-allow: 内部运维日志
                stats.increment("success")
            elif failed:
                logger.error("[MONITOR] 主链归档失败: %d 条", failed)  # i18n-allow: 内部运维日志
                stats.increment("failed")
            elif scanned == 0:
                if os.path.exists(path):
                    logger.warning("[MONITOR] 未识别到标准号，未归档: %s", path)  # i18n-allow: 内部运维日志
                    stats.increment("failed")
                else:
                    logger.info("[MONITOR] 父目录已无可处理文件: %s", path)  # i18n-allow: 内部运维日志
            else:
                logger.info("[MONITOR] 主链完成但无搬移: %s", path)  # i18n-allow: 内部运维日志
            _cleanup_empty_dirs(watch_path, source_root)
        except Exception as e:
            logger.error("[MONITOR] 主链处理失败: %s — %s", path, e)  # i18n-allow: 内部运维日志
            stats.increment("failed")
        finally:
            with self._dir_lock:
                self._active_dirs.discard(source_root)
            # 状态页可观测性（08#23 第 4 步）：最后处理的文件路径 + 落库，重启后仍可见
            self._last_processed = path
            set_last_processed(path)

    def get_status(self) -> dict:
        """返回监控运行状态，包含运行标志、路径、今日统计等。"""
        cfg = get_config()
        today_stats = get_monitor_stats().get_today_stats()
        if not self._last_processed:
            self._last_processed = get_last_processed()
        return {
            "running": self.running,
            "enabled": cfg.get("enabled", True),
            "watch_path": cfg.get("watch_path", "/inbox"),
            "delay_seconds": cfg.get("delay_seconds", 5),
            "last_processed": self._last_processed,
            "processed_today": today_stats["processed"],
            "success_today": today_stats["success"],
            "failed_today": today_stats["failed"],
        }
