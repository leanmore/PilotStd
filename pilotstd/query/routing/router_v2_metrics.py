# 模块：项目/查询/路由/v2指标脚本
# 阶段四：v2 路由决策埋点 — 异步 JSONL 写入，不阻塞主查询链路。

from __future__ import annotations

import hashlib
import json
import queue
import threading
import time
from pathlib import Path
from typing import Optional

# 日志目录与文件（项目根 logs/）
_LOG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "logs" / "router_v2_decisions.jsonl"

# 异步缓冲队列：主线程 put，后台线程批量 flush，避免阻塞查询
_queue: "queue.Queue[str]" = queue.Queue()
_writer_started = False
_writer_lock = threading.Lock()


def _start_writer() -> None:
    """启动后台写入线程（惰性单次启动）。"""
    global _writer_started
    with _writer_lock:
        if _writer_started:
            return
        _writer_started = True
        t = threading.Thread(target=_write_loop, daemon=True)
        t.start()


def _write_loop() -> None:
    """后台消费队列，逐行写 JSONL。"""
    while True:
        line = _queue.get()
        try:
            _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with _LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass  # 埋点失败不阻断主链路


def record_decision(payload: dict) -> None:
    """异步记录一条 v2 路由决策（非阻塞）。"""
    _start_writer()
    payload.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    try:
        _queue.put(json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass


def hash_query(query: str) -> str:
    """返回查询的 sha256 前 8 位（不记录原始 query，保护隐私）。"""
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:8]


def record_v1_brief(query: str, hit_site: Optional[str], total_latency_ms: float) -> None:
    """记录 v1 精简对比日志（仅 query_hash/hit_site/latency，供 4.4 回归对比）。"""
    record_decision(
        {
            "query_hash": hash_query(query),
            "hit_site": hit_site,
            "total_latency_ms": round(total_latency_ms, 2),
            "routing_version": "v1",
        }
    )


def build_decision(
    query: str,
    intent,
    route_chain: list[str],
    attempted_sites: list[str],
    hit_site: Optional[str],
    fallback_count: int,
    quota_skipped_sites: list[str],
    total_latency_ms: float,
) -> dict:
    """构造 v2 埋点字段。"""
    return {
        "query_hash": hash_query(query),
        "intent": {
            "std_type": intent.std_type,
            "industry": intent.industry,
            "is_international": intent.is_international,
        },
        "route_chain": route_chain,
        "attempted_sites": attempted_sites,
        "hit_site": hit_site,
        "fallback_count": fallback_count,
        "quota_skipped_sites": quota_skipped_sites,
        "total_latency_ms": round(total_latency_ms, 2),
        "routing_version": "v2",
    }
