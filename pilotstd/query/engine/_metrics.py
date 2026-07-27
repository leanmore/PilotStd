# pilotstd/query/engine/_metrics.py
# QueryMetrics — 线程安全的批次查询计数器（#46 修复配套基础设施）
#
# 设计约束：
# - batch_id 维度隔离，不同批次互不干扰
# - 线程安全（threading.Lock）
# - 与 batch_state 表分离，避免写锁竞争
# - adapter_quota_snapshot 接口预留，待调查返回后填充
import logging
import threading
import time
from collections import defaultdict
from typing import Optional

from pilotstd.core.config.paths import get_db_path
from pilotstd.core.db import Database

logger = logging.getLogger(__name__)

# ✅ #46 P0: adapter_quota_snapshot schema 版本号
SNAPSHOT_SCHEMA_VERSION = 1


class QueryMetrics:
    """批次查询指标收集器，线程安全。

    使用方式：
        metrics = QueryMetrics(batch_id="batch-20260727-001")
        metrics.increment("parse_ok")
        metrics.increment("quota_exhausted", count=5)
        report = metrics.get_report()
    """

    def __init__(self, batch_id: str):
        self.batch_id = batch_id
        self._created_at = time.time()
        self._lock = threading.Lock()
        self.counters: dict[str, int] = defaultdict(int)

    def increment(self, key: str, count: int = 1) -> None:
        """原子递增指定计数器。"""
        with self._lock:
            self.counters[key] += count

    def set(self, key: str, value: int) -> None:
        """原子设置指定计数器值。"""
        with self._lock:
            self.counters[key] = value

    def get(self, key: str) -> int:
        """原子读取指定计数器值。"""
        with self._lock:
            return self.counters.get(key, 0)

    def get_report(self) -> dict:
        """获取完整统计报告，包含 batch_id 和耗时。"""
        with self._lock:
            elapsed = time.time() - self._created_at
            return {
                "batch_id": self.batch_id,
                "elapsed_seconds": round(elapsed, 2),
                **dict(self.counters),
            }

    # ✅ 任务4：持久化到 query_metrics 表
    def persist_to_db(self) -> None:
        """将非零计数器批量写入 query_metrics 表。

        使用项目统一 DB 访问方式（Database + get_db_path）。
        写入失败不阻断主流程，仅记录异常日志。
        """
        report = self.get_report()
        batch_id = report["batch_id"]
        try:
            db = Database(get_db_path())
            for key, value in self.counters.items():
                if value > 0:
                    db.execute(
                        "INSERT INTO query_metrics (batch_id, metric_key, metric_value) VALUES (?, ?, ?)",
                        (batch_id, key, value),
                    )
            logger.info("query_metrics 已持久化: batch=%s keys=%d", batch_id, len(self.counters))
        except Exception:
            logger.exception("query_metrics 持久化失败（非阻断）: batch=%s", batch_id)

    # ── 适配器状态快照（#46 P0：调查1确认冷却为全局进程级+Lock保护）──

    def take_adapter_snapshot(self, rotator, quota_tracker=None, adapter_names: Optional[list[str]] = None) -> dict:
        """创建中断时的适配器全局状态快照。

        必须在 rotator._lock 内执行以保证一致性。
        返回符合 ADAPTER_SNAPSHOT_SCHEMA v1 的快照字典。
        """
        snapshot: dict = {"version": SNAPSHOT_SCHEMA_VERSION, "captured_at": time.time(), "adapters": {}}
        with rotator._lock:
            for name, site in rotator._sites.items():
                if adapter_names and name not in adapter_names:
                    continue
                snapshot["adapters"][name] = {
                    "cooldown_until": site.cooldown_until,
                    "request_count_in_window": site.request_count,
                    "daily_count": site.daily_count,
                    "consecutive_errors": site.consecutive_errors,
                }
        return snapshot

    def apply_adapter_snapshot(self, rotator, snapshot: dict) -> bool:
        """从快照恢复适配器全局状态。

        必须在 rotator._lock 内执行以保证一致性。
        cooldown_until 取 max 防止覆盖中断后新触发的冷却。
        对未知适配器名称做 skip + warning，不因配置变更导致续传崩溃。

        返回 True 表示恢复成功。
        """
        if snapshot.get("version") != SNAPSHOT_SCHEMA_VERSION:
            logger.warning("Unknown snapshot version: %s, skipping restore", snapshot.get("version"))
            return False
        with rotator._lock:
            for name, state in snapshot.get("adapters", {}).items():
                if name not in rotator._sites:
                    logger.warning("Snapshot adapter %s not found in current rotator, skipping", name)
                    continue
                site = rotator._sites[name]
                site.cooldown_until = max(
                    state.get("cooldown_until", 0),
                    site.cooldown_until,  # 取较晚者，防止覆盖更新的冷却
                )
                site.request_count = state.get("request_count_in_window", 0)
                site.daily_count = state.get("daily_count", 0)
                site.consecutive_errors = state.get("consecutive_errors", 0)
        return True

    # ── 预定义计数器键名（统一命名约定）──

    # 解析阶段
    KEY_PARSE_OK = "parse_ok"
    KEY_PARSE_FAIL = "parse_fail"

    # 路由阶段
    KEY_ROUTE_COOLED = "route_cooldown_skip"
    KEY_ROUTE_QUOTA_EXHAUSTED = "route_quota_exhausted"
    KEY_ROUTE_NO_ADAPTER = "route_no_adapter"

    # 查询阶段
    KEY_QUERY_OK = "query_ok"
    KEY_QUERY_FAIL_NETWORK = "query_fail_network"
    KEY_QUERY_FAIL_SCORE_LOW = "query_fail_score_low"
    KEY_QUERY_FAIL_ADAPTER_ERR = "query_fail_adapter_error"

    # 溢出阶段
    KEY_OVERFLOW_OK = "overflow_ok"
    KEY_OVERFLOW_CHAIN_EXHAUSTED = "overflow_chain_exhausted"
    KEY_OVERFLOW_QUOTA_EXHAUSTED = "overflow_quota_exhausted"

    # 其他
    KEY_BATCH_CRASH = "batch_crash"
    KEY_CSRES_CIRCUIT_BREAK = "csres_circuit_break"
    KEY_CSRES_DROPPED = "csres_dropped"
