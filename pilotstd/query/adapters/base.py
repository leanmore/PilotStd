# 模块：项目/查询/适配器/脚本
# 查询网站适配器抽象基类

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Tuple

from ..models import QueryResult
from ..search_strategy import (
    MATCH_SCORE,
    MATCH_SCORE_CONFIRMED,
    MATCH_SCORE_HIGH_CONFIDENCE,
    _parse_result_number,
    build_code_variants,
    match_result,
)

logger = logging.getLogger(__name__)


class BaseAdapter(ABC):
    """所有查询网站适配器的抽象基类。"""

    # 能力声明：是否支持从详情页补查替代关系
    supports_replaces_detail: bool = False

    @property
    @abstractmethod
    def site_name(self) -> str: ...

    @property
    @abstractmethod
    def site_label(self) -> str: ...

    # ──搜索（子类通常不需要重写，只需实现__和钩子）──

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
        best = max(candidates, key=lambda c: getattr(c, "publish_date", "") or "")
        self._post_process_result(best)
        return best

    def _try_exact_search(
        self,
        search_term: str,
        logical_code: str,
        number: int,
        year: int,
        part: int | None,
        accepted_statuses: set = {"exact"},
    ) -> Optional[QueryResult]:
        """通用精确搜索：搜索→匹配状态→后处理。匹配到接受的状态则返回 QueryResult，否则 None。"""
        result = self._search(search_term)
        if result and result.is_found():
            _, status = match_result(
                logical_code, number, year, result.standard_name, result.standard_number, local_part=part
            )
            if status in accepted_statuses:
                result.match_status = status
                self._post_process_result(result)
                return result
        return None

    def _search_progressive(
        self,
        logical_code: str,
        number: int,
        year: int,
        part: int | None,
        num_prefix: str,
        num_suffix: str,
        target: str,
    ) -> Optional[QueryResult]:
        """渐进式搜索前4步：完整号直搜 → 空格回退 → 去前缀 → 去年份。"""
        part_str = f".{part}" if part else ""

        # 第一步：完整标准号直接搜（横杠格式）
        result = self._try_exact_search(target, logical_code, number, year, part)
        if result is not None:
            return result

        # 第二步：空格格式回退
        space_target = f"{logical_code} {num_prefix or ''}{number}{num_suffix or ''}{part_str} {year}"
        if space_target != target:
            result = self._try_exact_search(space_target, logical_code, number, year, part)
            if result is not None:
                return result

        # 第三步：去除_回退（如78.81→78.81）
        if num_prefix:
            no_prefix = f"{logical_code} {number}{num_suffix or ''}{part_str}-{year}"
            if no_prefix != target:
                result = self._try_exact_search(no_prefix, logical_code, number, year, part)
                if result is not None:
                    return result

        # 第四步：去年份回退
        no_year = f"{logical_code} {num_prefix or ''}{number}{num_suffix or ''}{part_str}"
        result = self._try_exact_search(
            no_year, logical_code, number, year, part, accepted_statuses={"exact", "newer", "older"}
        )
        if result is not None:
            return result

        return None

    def query_with_strategy(
        self,
        logical_code: str,
        number: int,
        year: int,
        std_name: str = "",
        part: int | None = None,
        num_prefix: str = "",
        num_suffix: str = "",
    ) -> Optional[QueryResult]:
        """渐进式搜索：完整号直搜 → 空格回退 → 去前缀 → 去年份 → 代号变体。"""
        part_str = f".{part}" if part else ""
        target = f"{logical_code} {num_prefix or ''}{number}{num_suffix or ''}{part_str}-{year}"

        result = self._search_progressive(logical_code, number, year, part, num_prefix, num_suffix, target)
        if result is not None:
            return result

        # 第五步：代号变体补充（接口/、、等）
        variants = build_code_variants(logical_code, number, year, num_prefix)
        best_score = -1
        best_result: Optional[QueryResult] = None
        best_match_status = ""
        for term in variants:
            candidates = self._search_candidates(term)
            if not candidates:
                continue
            for result in candidates:
                if result is None:
                    continue
                _, status = match_result(
                    logical_code,
                    number,
                    year,
                    result.standard_name,
                    result.standard_number,
                    local_part=part,
                )
                score = MATCH_SCORE.get(status, 0)
                if score > best_score:
                    best_score = score
                    best_result = result
                    best_match_status = status
                if score >= MATCH_SCORE_CONFIRMED:
                    break
            if best_score >= MATCH_SCORE_HIGH_CONFIDENCE:
                break

        if best_result is not None:
            best_result.match_status = best_match_status
            self._post_process_result(best_result)
            return best_result

        return QueryResult(
            standard_number=target,
            error_message="未找到匹配结果",
            source_site=self.site_name,
        )

    def _search_candidates(self, search_term: str) -> list[QueryResult]:
        """搜索候选项，默认逐条搜索。子类可重写以返回多个结果（翻页等）。"""
        result = self._search(search_term)
        if result and result.is_found():
            return [result]
        return []

    def _build_search_data(self, search_term: str) -> dict[str, Any]:
        """构建搜索请求 data。子类可重写以添加额外字段（如 status 过滤）。"""
        return {"current": 1, "size": 15, "key": search_term}

    def _post_search_candidates(self, search_term: str) -> list[QueryResult]:
        """POST 搜索候选（通用实现）。子类的 _search_candidates 可委托此方法。

        注意：safe_post 通过懒加载导入（pilotstd.query.network），测试 mock 时
        需 patch 'pilotstd.query.network.safe_post' 而非本模块。"""
        data = self._build_search_data(search_term)
        from ..network import safe_post

        resp = safe_post(
            self._session,  # type: ignore[attr-defined]
            self.API_URL,  # type: ignore[attr-defined]
            self.site_name,
            data=data,
            timeout=15,
        )
        if resp is None or resp.status_code != 200:
            return []

        try:
            payload = resp.json()
        except ValueError:
            return []

        records = payload.get("records", [])
        if not records:
            return []

        return [self._parse_result(rec, search_term) for rec in records]  # type: ignore[attr-defined]

    def _post_process_result(self, result: QueryResult) -> None:
        """结果后处理钩子。基类为空实现，子类按需重写（如 csres/hbba/njbz365）。"""

    @staticmethod
    def _detect_split_parts(candidates: list[Tuple[QueryResult, int]], local_number: int) -> str:
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
            if parsed.get("number") == local_number:
                p = parsed.get("part")
                if p is not None:
                    part_nums.add(result.standard_number)
        if len(part_nums) >= 2:
            return ", ".join(sorted(part_nums))
        return ""
