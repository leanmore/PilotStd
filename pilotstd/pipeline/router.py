# 模块：pilotstd/pipeline/router.py
# 流水线路由调度器 — 每完成一个阶段后重读状态标记，决定下一站

import logging
import os
from typing import Any, List

from ..core.file_utils import make_standard_filename
from ..core.std_utils import GB_CODES, is_gb_code
from ..models import ParsedStdInfo

logger = logging.getLogger(__name__)


def _parse_code_from_std_number(standard_number: str) -> str:
    """从标准号字符串中提取代号前缀。如 'GB/T 713.1-2023' → 'GB/T'，'HG/T 20584-2020' → 'HG/T'。"""
    import re

    m = re.match(r"([A-Z]+(?:\s*/\s*[A-Z]+)?)", str(standard_number))
    if m:
        return m.group(1).replace(" ", "")
    return ""


class PipelineRouter:
    """根据标准信息结构体中的状态标记，将文件分堆到对应的下一阶段。

    不是一次性静态判断——每完成一个阶段后重新调用分类方法，
    重新读取状态标记，重新决定去向。冷启动时所有文件"待确认"，
    全部送查询；查询完成后状态落定再分堆。

    公开方法：
    - classify_after_scan: 扫描完成后分堆
    - classify_after_query: 查询完成后分堆
    - classify_after_download: 下载完成后→全部归档
    """

    # openstd 仅支持下载 GB 类标准，非国标不可路由到 download
    _GB_CODES = GB_CODES  # 定义见 pilotstd.core.std_utils

    @staticmethod
    def _newer_exists_locally(item: Any, all_items: Any) -> bool:
        """检查 match_status=="newer" 对应的新版文件是否已在本地存在。

        遍历所有已解析条目，查找是否已有与当前条目同代号、同序号、
        同部分号、且查询结果为 exact 匹配的文件。
        若存在则说明新版标准已由用户持有，无需重复下载。
        """
        code = (getattr(item, "logical_code", "") or "").replace("/", "").upper()
        number = getattr(item, "number", 0)
        part = getattr(item, "part", None)
        for other in all_items:
            if other is item:
                continue
            other_code = (getattr(other, "logical_code", "") or "").replace("/", "").upper()
            if other_code != code:
                continue
            if getattr(other, "number", 0) != number:
                continue
            if getattr(other, "part", None) != part:
                continue
            if getattr(other, "match_status", "") == "exact":
                return True
        return False

    def classify_after_scan(self, items: List[ParsedStdInfo]) -> dict[str, Any]:
        """扫描后第一轮判断。按 next_action 分堆。

        返回 {"archive": [...], "normalize": [...], "query": [...], "fallback": [...]}
        """
        buckets: dict[str, list[Any]] = {
            "archive": [],
            "normalize": [],
            "query": [],
            "fallback": [],
        }
        for p in items:
            action = getattr(p, "next_action", "") or ""
            if action == "archive":
                buckets["archive"].append(p)
            elif action == "normalize":
                buckets["normalize"].append(p)
            elif action == "not_found":
                buckets["fallback"].append(p)
            else:
                # pending 及未设置 next_action 的默认送查询
                buckets["query"].append(p)
        return buckets

    @staticmethod
    def _route_replaced_or_obsolete(
        p: Any, buckets: dict[str, list[Any]], has_valid_replaces: bool, replaces: str
    ) -> None:
        """路由规则: 有替代关系 → 替代为GB→download，替代为非GB→manual_download，否则→organize。
        废止标准统一走主线 organize() 归档，由 normalize_filename 根据 effect_status 追加过期作废子目录。"""
        if has_valid_replaces:
            replacement_code = _parse_code_from_std_number(replaces)
            if replacement_code and is_gb_code(replacement_code):
                if getattr(p, "is_adopted", False):
                    buckets["pending"].append(p)
                else:
                    buckets["download"].append(p)
            else:
                # 替代标准为非GB（或无法解析代号）→ 手动下载
                buckets["manual_download"].append(p)
                p.stage_status = "replacement_manual"
        else:
            buckets["organize"].append(p)

    @staticmethod
    def _route_current_status(p: Any, buckets: dict[str, list[Any]]) -> None:
        """路由规则: '现行' 状态 → 比对文件名决定 organize 或 normalize。"""
        expected = make_standard_filename(
            p.logical_code,
            p.number,
            p.year,
            p.std_name,
            getattr(p, "part", None),
            language=getattr(p, "language", ""),
            num_prefix=getattr(p, "num_prefix", ""),
            num_suffix=getattr(p, "num_suffix", ""),
            ext=getattr(p, "ext", ".pdf"),
            raw_number=getattr(p, "raw_number", None),
        )
        actual = os.path.basename(p.source_path or "")
        if actual == expected:
            buckets["organize"].append(p)
        else:
            buckets["normalize"].append(p)

    def _route_by_status(self, p: Any, buckets: dict[str, list[Any]], items: list[Any]) -> None:
        """根据单条标准的状态标记决定路由去向（原地修改 buckets）。"""
        status = getattr(p, "effect_status", "") or ""
        replaces = getattr(p, "found_replaces", "") or ""
        code = getattr(p, "logical_code", "") or ""
        match_status = getattr(p, "match_status", "") or ""
        logger.debug(
            "路由: %s | 状态=%s match=%s 采标=%s replaces=%s",
            p.get_full_number(),
            status,
            match_status,
            getattr(p, "is_adopted", False),
            bool(replaces),
        )
        has_valid_replaces = bool(replaces and replaces not in ("网站无此分类",))
        is_gb = is_gb_code(code)

        # 规则0.1: 名称决策 — std_name 和 found_name 均为空 → pending
        src = (getattr(p, "source_name", "") or "").strip()
        qry = (getattr(p, "found_name", "") or "").strip()
        if not src and not qry:
            buckets["pending"].append(p)
            return
        # 规则1: match_status=="newer" + GB + 非采标 → download
        if match_status == "newer" and is_gb:
            if getattr(p, "is_adopted", False):
                buckets["pending"].append(p)
            elif self._newer_exists_locally(p, items):
                logger.debug("路由: %s | 新版已本地存在，跳过下载→归档过期", p.get_full_number())
                buckets["organize"].append(p)
            else:
                buckets["download"].append(p)
            return
        # 规则2: 未查到/未知/状态缺失 → 待确认
        if not status or status == "未知":
            buckets["pending"].append(p)
            return
        # 规则3: 待确认 → 待确认
        if status == "待确认":
            buckets["pending"].append(p)
            return
        # 规则4-7: 废止/已废止/作废/被代替/过期
        if status in ("废止", "已废止", "作废", "被代替", "过期"):
            self._route_replaced_or_obsolete(p, buckets, has_valid_replaces, replaces)
            return
        # 规则4.5: 本地无文件 → GB 进 download，非GB 进 manual_download
        source_path = getattr(p, "source_path", "") or ""
        if not source_path or not os.path.exists(source_path):
            if is_gb:
                buckets["download"].append(p)
                p.stage_status = "need_download"
            else:
                buckets["manual_download"].append(p)
                p.stage_status = "need_manual_download"
            return
        # 规则8: 现行 → organize/normalize
        if status == "现行":
            self._route_current_status(p, buckets)
            return
        # 规则9: 非 exact 匹配兜底 → pending（排在所有具体判定之后，仅捕获无法归类的条目）
        if match_status and match_status != "exact":
            buckets["pending"].append(p)
            if match_status in ("older", "newer"):
                p.stage_status = "version_mismatch"
            return
        # 规则10: 最终兜底
        buckets["fallback"].append(p)

    def classify_after_query(self, items: List[ParsedStdInfo]) -> dict[str, Any]:
        """查询后第二轮判断。按 effect_status 分堆。"""
        buckets: dict[str, list[Any]] = {
            "organize": [],
            "normalize": [],
            "download": [],
            "manual_download": [],
            "pending": [],
            "fallback": [],
        }
        for p in items:
            self._route_by_status(p, buckets, items)

        _ce_count = sum(1 for p in buckets.get("pending", []) if getattr(p, "match_status", "") == "chain_exhausted")
        logger.info(
            "[ROUTER] 分类结果: pending=%d (chain_exhausted=%d) "
            "organize=%d normalize=%d download=%d manual_download=%d fallback=%d",
            len(buckets["pending"]),
            _ce_count,
            len(buckets["organize"]),
            len(buckets["normalize"]),
            len(buckets["download"]),
            len(buckets["manual_download"]),
            len(buckets["fallback"]),
        )
        for p in buckets["pending"]:
            logger.info(
                "[PENDING_DETAIL] 标准=%s 匹配状态=%s 下一步=%s 有效性=%s 源路径=%s",
                p.get_full_number(),
                getattr(p, "match_status", ""),
                getattr(p, "next_action", ""),
                getattr(p, "effect_status", ""),
                (getattr(p, "source_path", "") or "")[:80],
            )
        return buckets

    def apply_actions(self, items: List[ParsedStdInfo]) -> dict[str, Any]:
        """对条目分类并设置 next_action。返回分桶结果。"""
        buckets = self.classify_after_query(items)
        for p in buckets.get("organize", []):
            p.next_action = "archive"
        for p in buckets.get("normalize", []):
            p.next_action = "normalize"
        for p in buckets.get("expire", []):
            p.next_action = "expire"
        for p in buckets.get("download", []):
            p.next_action = "download"
        for p in buckets.get("manual_download", []):
            p.next_action = "manual_download"
        for p in buckets.get("pending", []):
            p.next_action = "pending"
        for p in buckets.get("fallback", []):
            p.next_action = "not_found"
        # 名称决策：仅对进入下载队列的条目（GB 类标准）比较源名称与查询名称，
        # 实质差异条目移入 pending。非 GB 标准不参与名称决策，保持 organize/normalize 状态。
        name_conflicts = self._resolve_names(buckets.get("download", []))
        if name_conflicts:
            for p in name_conflicts:
                p.next_action = "pending"
                p.stage_status = "name_conflict"
            buckets["pending"].extend(name_conflicts)
        return buckets

    def _resolve_names(self, items: List[ParsedStdInfo]) -> List[ParsedStdInfo]:
        """名称决策：比较 source_name 与 found_name，确定 final_name。

        返回：因实质差异需移入 pending 的条目列表。
        """
        conflicts = []
        for p in items:
            src = (getattr(p, "source_name", "") or "").strip()
            qry = (getattr(p, "found_name", "") or "").strip()

            if src and qry:
                if src == qry:
                    p.final_name = src
                else:
                    norm_src = self._normalize_name(src)
                    norm_qry = self._normalize_name(qry)
                    if norm_src == norm_qry:
                        p.normalized_name = norm_src
                        p.final_name = norm_src
                    elif not self._is_core_different(norm_src, norm_qry):
                        # 仅停用词/标点差异 → 自动规范化
                        p.normalized_name = norm_src
                        p.final_name = norm_src
                    else:
                        # 实质差异：不自动赋值，移入 pending
                        conflicts.append(p)
                        continue
            elif src and not qry:
                p.final_name = src
            elif not src and qry:
                p.final_name = qry

            # 过渡期：回写 std_name，归档链路零改动
            if p.final_name:
                p.std_name = p.final_name
        return conflicts

    # 中文停用词/字集合（名称对比时忽略）
    _STOP_WORDS = frozenset({"的", "和", "及", "与", "或", "及其", "以及", "第", "部分"})

    @classmethod
    def _is_core_different(cls, a: str, b: str) -> bool:
        """比较两个名称的核心词是否不同。

        去除停用词、标点、数字后，提取核心词集合进行比较。
        中文按字符级分词，英文按空格分词。
        核心词相同 → False（格式差异）; 核心词不同 → True（实质差异）。
        """
        import re

        def _extract_core(name: str) -> frozenset[Any]:
            cleaned = re.sub(r"[^\w\s]", " ", name)
            cleaned = re.sub(r"\d+", " ", cleaned)
            # 检测是否含中文
            has_cjk = any("一" <= c <= "鿿" for c in cleaned)
            if has_cjk:
                # 中文：逐字分词，过滤停用字和空白
                words = [c for c in cleaned if c not in cls._STOP_WORDS and c.strip()]
            else:
                # 英文：按空格分词
                words = [w for w in cleaned.split() if w not in cls._STOP_WORDS]
            return frozenset(words)

        core_a = _extract_core(a)
        core_b = _extract_core(b)
        if not core_a or not core_b:
            return False
        return core_a != core_b

    @staticmethod
    def _normalize_name(name: str) -> str:
        """名称格式规范化：全角转半角、统一标点、去多余空格。"""
        import re
        import unicodedata

        name = unicodedata.normalize("NFKC", name)
        name = name.replace("（", "(").replace("）", ")")
        name = name.replace("：", ":").replace("，", ",")
        name = name.replace("。", ".").replace("；", ";")
        name = re.sub(r"\s+", " ", name).strip()
        return name

    def classify_after_download(self, items: List[ParsedStdInfo]) -> dict[str, list[ParsedStdInfo]]:
        """下载完成后第三轮判断。已下载的全部送归档。

        返回 {"organize": [...]}
        """
        return {"organize": list(items)}
