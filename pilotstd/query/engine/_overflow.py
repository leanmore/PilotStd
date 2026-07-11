# pilotstd/query/engine/_overflow.py
# 溢出/错误恢复混入 — 从 _batch.py 提取
"""溢出条目链式重试（微批 + 随机抖动 + 冷却/配额感知）。"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from ..models import QueryResult
from ..search_strategy import MATCH_SCORE

logger = logging.getLogger(__name__)


class OverflowHandler:
    """溢出链式重试混入 — 为 BatchMixin 提供 overflow 阶段方法。"""

    # 以下属性由 BatchMixin 的其他混入类提供（_core / _routing）
    _rotator: Any
    _record: Any
    _adapter_map: Any
    _build_chain_for_item: Any
    _bucket_key: Any

    def _try_overflow_site(
        self,
        idx: int,
        item: tuple,
        site: str,
        adapter: Any,
        state: dict,
        _time: Any,
        result_callback: Optional[Callable[[int, QueryResult], None]],
    ) -> bool:
        """对单个站点执行溢出查询，处理结果并更新评分/链状态。
        返回 True 表示找到 >=100 分的结果，该项无需继续重试。
        """
        try:
            _t0 = _time.time()
            result = adapter.query_with_strategy(  # type: ignore[assignment]
                item[0], item[1], item[2], item[3], item[4]
            )
            _elapsed = round(_time.time() - _t0, 3)
            if self._rotator:
                self._rotator.record_query_result(
                    site,
                    result is not None and result.is_found(),
                    _elapsed,
                )
        except Exception:
            return False

        if result:
            result.source_site = site
            self._record(site, 1)
            state["_record_match"](site, getattr(result, "match_status", "err"))
            tried_chain = state["item_chains"].get(idx, [])
            tried_chain.append(site)
            state["item_chains"][idx] = tried_chain
            score = MATCH_SCORE.get(getattr(result, "match_status", ""), 0)
            _td = f"{item[0]} {item[1]}-{item[2]}"
            if score >= 100:
                state["results"][idx] = result
                with state["_prog_lock"]:
                    state["_prog_ok"][0] += 1
                logger.info(
                    "查询 [%s] [OK]%s(%s)",
                    _td,
                    site,
                    getattr(result, "match_status", ""),
                )
                if result_callback and result.is_found():
                    result_callback(idx, result)
                state["bump"]()
                return True
            else:
                logger.info(
                    "查询 [%s] [LO]%s(%s=%d) 未达100分继续",
                    _td,
                    site,
                    getattr(result, "match_status", ""),
                    score,
                )
        return False

    def _process_overflow_item(
        self,
        idx: int,
        item: tuple,
        state: dict,
        _time: Any,
        result_callback: Optional[Callable[[int, QueryResult], None]],
        temp_skips: list,
        preferred_site: str | None = None,
    ) -> None:
        """处理单个溢出条目：遍历站点链尝试查询（含冷却/配额检查）。
        原地修改 state["results"]、state["item_chains"]、state["pending_reasons"]。
        """
        if idx in state["results"]:
            return
        chain = self._build_chain_for_item(item, preferred_site)
        # 主站点已查过，从二线开始
        start = 1 if chain and chain[0] == self._bucket_key(item[0], preferred_site) else 0
        found = False

        for site in chain[start:]:
            if site not in self._adapter_map:
                continue
            if self._rotator and self._rotator.get_cooldown_remaining(site) > 0:
                temp_skips[0] += 1
                ov_q = state["overflow_quota"].get(site, [0])
                logger.debug(
                    "[QUOTA] 站点=%s 操作=溢出不可用 原因=冷却中 剩余溢出配额=%d",
                    site,
                    ov_q[0] if ov_q else 0,
                )
                continue
            # 溢出配额控制：受限站点消耗配额，配额耗尽则跳过
            if site in state["overflow_quota"] and not state["_try_overflow"](site):
                logger.debug(
                    "[QUOTA] 站点=%s 操作=溢出配额耗尽 剩余=%d",
                    site,
                    state["overflow_quota"][site][0],
                )
                continue

            adapter = self._adapter_map[site]
            if self._try_overflow_site(idx, item, site, adapter, state, _time, result_callback):
                found = True
                break

        # 链耗尽→待确认
        if not found:
            chain_str = "→".join(state["item_chains"].get(idx, [])) or "none"
            _td2 = f"{item[0]} {item[1]}-{item[2]}"
            logger.info("查询 [%s] [NG] tried=%s", _td2, chain_str)
            state["pending_reasons"].append((idx, chain_str))
            state["results"][idx] = QueryResult(
                standard_number=f"{item[0]} {item[1]}-{item[2]}",
                standard_name=item[3],
                status="待确认",
                source_site="",
                match_status="chain_exhausted",
            )
            state["bump"]()

    def _handle_overflow(
        self,
        state: dict,
        _time: Any,
        result_callback: Optional[Callable[[int, QueryResult], None]],
        preferred_site: str | None = None,
    ) -> int:
        """错误恢复：溢出条目微批链迭代（含随机抖动防惊群）。
        返回因站点冷却而跳过的次数。
        """
        all_overflow = state["all_overflow"]
        temp_skips = [0]
        if not all_overflow:
            return 0

        # 用户指定站点 → 禁止溢出到其他站点
        if preferred_site:
            return 0

        # 按剩余站点数升序（短链优先）
        all_overflow.sort(key=lambda x: len(self._build_chain_for_item(x[1], preferred_site)))
        # 微批：每批 20 条，批次间 2-5s 随机抖动
        batch_size = 20
        for batch_start in range(0, len(all_overflow), batch_size):
            batch = all_overflow[batch_start : batch_start + batch_size]
            if batch_start > 0:
                import random as _random

                jitter = _random.uniform(2, 5)
                _time.sleep(jitter)
            for idx, item in batch:
                self._process_overflow_item(idx, item, state, _time, result_callback, temp_skips, preferred_site)

        return temp_skips[0]
