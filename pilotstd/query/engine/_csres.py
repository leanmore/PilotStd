# pilotstd/query/engine/_csres.py
# CSRes 后台查询混入 — 从 _batch.py 提取

import logging

logger = logging.getLogger(__name__)


class CsresMixin:
    """CSRes 适配器独立查询线程（混入 BatchMixin）。"""

    def _build_csres_pool(self, gb_items: list, industry_items: list) -> list:
        """计算 GB/行业各取多少条（GB 60% + 行业 40%）。"""
        gb_take = int(self._CSRES_LIMIT * 0.6)
        industry_take = self._CSRES_LIMIT - gb_take
        return gb_items[:gb_take] + industry_items[:industry_take]

    def _rate_limit_sleep(self, _last_ts: float, _t0: float) -> float:
        """计算并执行限速休眠，返回新的时间戳。"""
        import random as _random
        import time as _time2

        base_interval = 5.0
        jitter = _random.uniform(0, 1.0)
        query_elapsed = _time2.time() - _t0
        sleep_time = max(0, base_interval + jitter - query_elapsed)
        _time2.sleep(sleep_time)
        now = _time2.time()
        self._csres_processed += 1
        logger.info(
            "[CSRES_INTERVAL] 实际=%.1f秒 目标=%.1f秒 查询=%.1f秒 休眠=%.1f秒",
            now - _last_ts,
            base_interval + jitter,
            query_elapsed,
            sleep_time,
        )
        return now

    def _run_csres_worker(
        self, gb_items: list, industry_items: list, csres_results: dict, csres_failures: list
    ) -> None:
        """CSRes 后台查询线程：从 GB/行业桶各取配额条目并发查询。"""
        adapter = self._adapter_map.get("csres")
        if not adapter:
            return
        import time as _time2

        pool = self._build_csres_pool(gb_items, industry_items)
        self._csres_active = True
        self._csres_processed = 0
        self._csres_total = len(pool)
        _last_ts = _time2.time()
        for idx, item in pool:
            if csres_failures[0] >= self._CSRES_CIRCUIT_BREAK:
                break
            _t0 = _time2.time()
            try:
                result = adapter.query_with_strategy(item[0], item[1], item[2], num_prefix=item[3], part=item[4])
                _elapsed = round(_time2.time() - _t0, 3)
                if self._rotator:
                    self._rotator.record_query_result("csres", result is not None and result.is_found(), _elapsed)
                if result:
                    result.source_site = "csres"
                    csres_results[idx] = result
                    csres_failures[0] = 0
                    logger.info(
                        "[CSRES] idx=%d code=%s num=%s %d-%d 状态=找到 评分=100",
                        idx,
                        item[0],
                        item[0],
                        item[1],
                        item[2],
                    )
                else:
                    csres_failures[0] += 1
                    logger.info(
                        "[CSRES] idx=%d code=%s num=%s %d-%d 状态=未找到 失败=%d/%d",
                        idx,
                        item[0],
                        item[0],
                        item[1],
                        item[2],
                        csres_failures[0],
                        self._CSRES_CIRCUIT_BREAK,
                    )
            except Exception:
                csres_failures[0] += 1
                logger.info(
                    "[CSRES] idx=%d code=%s 状态=错误 失败=%d/%d",
                    idx,
                    item[0],
                    csres_failures[0],
                    self._CSRES_CIRCUIT_BREAK,
                )
            _last_ts = self._rate_limit_sleep(_last_ts, _t0)
        self._csres_active = False
