# pilotstd/query/adapters/base.py
# 查询网站适配器抽象基类

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import QueryResult
from ..search_strategy import build_search_terms, build_code_variants, match_result, MATCH_SCORE, MATCH_SCORE_CONFIRMED, MATCH_SCORE_HIGH_CONFIDENCE, _parse_result_number, build_code_variant

logger = logging.getLogger(__name__)


class BaseAdapter(ABC):
    """所有查询网站适配器的抽象基类。"""

    # 能力声明：是否支持从详情页补查替代关系
    supports_replaces_detail: bool = False

    @property
    @abstractmethod
    def site_name(self) -> str:
        ...

    @property
    @abstractmethod
    def site_label(self) -> str:
        ...

    # ── 搜索（子类通常不需要重写，只需实现 _search_candidates 和钩子）──

    def _search(self, search_term: str) -> Optional[QueryResult]:
        """单结果兼容接口。调 _search_candidates，精确匹配优先，否则选最新。
        子类可重写以满足特定站点逻辑。"""
        candidates = self._search_candidates(search_term)
        if not candidates:
            return None
        for c in candidates:
            if c.standard_number == search_term:
                self._post_process_result(c)
                return c
        best = max(candidates, key=lambda c: getattr(c, 'publish_date', '') or '')
        self._post_process_result(best)
        return best

    def query_single(self, standard_number: str) -> Optional[QueryResult]:
        """默认：直接用标准号搜索。子类可重写以使用渐进式搜索。"""
        return self._search(standard_number)

    def query_with_strategy(self, logical_code: str, number: int, year: int,
                            std_name: str = "", part: int = None,
                            num_prefix: str = "", num_suffix: str = "") -> Optional[QueryResult]:
        """渐进式搜索：逐级搜索词，收集候选，取最优匹配。

        子类可重写 _search_candidates(term) 支持多结果搜索（翻页等），
        重写 _post_process_result 添加站点特定后处理（如提取 replaces）。
        """
        part_str = f".{part}" if part else ""
        target = f"{logical_code} {num_prefix or ''}{number}{num_suffix or ''}{part_str}-{year}"
        terms = build_search_terms(logical_code, number, year, std_name, part, num_prefix, num_suffix)
        terms.extend(build_code_variants(logical_code, number, year, num_prefix))
        best_score = -1
        best_result = None
        best_match_status = ""
        all_candidates = []
        term_log: list[str] = []  # 逐级记录，最终一条日志输出完整搜索链

        for idx, term in enumerate(terms):
            candidates = self._search_candidates(term)
            # 前缀变体回退：GB/T 搜不到试 GB，反之亦然
            variant_label = ""
            if not candidates:
                variant_term = build_code_variant(term)
                if variant_term:
                    candidates = self._search_candidates(variant_term)
                    if candidates:
                        variant_label = f"→变体「{variant_term}」"
                    else:
                        variant_label = f"→变体「{variant_term}」→空"
                if not candidates:
                    tail = variant_label if variant_label else ""
                    term_log.append(f"#{idx+1}「{term}」→空{tail}")
                    continue
            # 本级最佳（独立追踪，避免跨级污染）
            local_best_score = 0
            local_best_number = ""
            local_best_status = ""
            for result in candidates:
                is_match, status = match_result(
                    logical_code, number, year,
                    result.standard_name, result.standard_number,
                    local_part=part)
                score = MATCH_SCORE.get(status, 0)
                if score >= 20:
                    all_candidates.append((result, score))
                if score > local_best_score:
                    local_best_score = score
                    local_best_number = result.standard_number
                    local_best_status = status
                if score > best_score:
                    best_score = score
                    best_result = result
                    best_match_status = status
                if score >= MATCH_SCORE_CONFIRMED:
                    break
            term_log.append(
                f"#{idx+1}「{term}」{variant_label}→{len(candidates)}条 "
                f"最佳={local_best_number}({local_best_status},{local_best_score}分)")
            if best_score >= MATCH_SCORE_CONFIRMED:
                break

        # 单条日志：目标标准 | 站点 | 逐级搜索过程 | 最终结果
        parts = " · ".join(term_log)
        if best_result is not None:
            best_result.match_status = best_match_status
            if best_score <= MATCH_SCORE_HIGH_CONFIDENCE:
                best_result.status = "待确认"
            split = self._detect_split_parts(all_candidates, number)
            if split:
                best_result.split_into = split
            self._post_process_result(best_result)
            logger.debug(f"查询 [{target}] @{self.site_name} | {parts} | 结果={best_result.standard_number}({best_match_status})")
            return best_result

        logger.debug(f"查询 [{target}] @{self.site_name} | {parts} | 结果=无匹配")
        return QueryResult(
            standard_number=target,
            error_message="所有搜索词均未找到匹配结果",
            source_site=self.site_name)

    def _search_candidates(self, search_term: str) -> list:
        """搜索候选项，默认逐条搜索。子类可重写以返回多个结果（翻页等）。"""
        result = self._search(search_term)
        if result and result.is_found():
            return [result]
        return []

    def _build_search_data(self, search_term: str) -> dict:
        """构建搜索请求 data。子类可重写以添加额外字段（如 status 过滤）。"""
        return {"current": 1, "size": 15, "key": search_term}

    def _post_search_candidates(self, search_term: str) -> list:
        """POST 搜索候选（通用实现）。子类的 _search_candidates 可委托此方法。"""
        data = self._build_search_data(search_term)
        from ..network import safe_post
        resp = safe_post(self._session, self.API_URL, self.site_name,
                        data=data, timeout=15)
        if resp is None or resp.status_code != 200:
            return []

        try:
            payload = resp.json()
        except ValueError:
            return []

        records = payload.get("records", [])
        if not records:
            return []

        return [self._parse_result(rec, search_term) for rec in records]

    def _post_process_result(self, result: QueryResult) -> None:
        """结果后处理钩子，子类可重写（如从详情页提取 replaces）。"""

    @staticmethod
    def _detect_split_parts(candidates: list, local_number: int) -> str:
        """检测标准是否被拆分为多个部分。

        同 number 出现 ≥2 个不同 part 时，返回逗号分隔的部分编号列表。
        """
        if len(candidates) < 2:
            return ""
        part_nums = set()
        for result, score in candidates:
            parsed = _parse_result_number(result.standard_number)
            if not parsed:
                continue
            if parsed.get('number') == local_number:
                p = parsed.get('part')
                if p is not None:
                    part_nums.add(result.standard_number)
        if len(part_nums) >= 2:
            return ", ".join(sorted(part_nums))
        return ""

    def query_batch(self, standard_numbers: List[str]) -> List[QueryResult]:
        results = []
        for num in standard_numbers:
            try:
                r = self.query_single(num)
                results.append(r if r else QueryResult(
                    standard_number=num, error_message="未找到",
                    source_site=self.site_name))
            except Exception as e:
                results.append(QueryResult(
                    standard_number=num, error_message=str(e),
                    source_site=self.site_name))
        return results
