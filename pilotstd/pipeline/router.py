# pilotstd/pipeline/router.py
# 流水线路由调度器 — 每完成一个阶段后重读状态标记，决定下一站

import logging
import os
from typing import List

from ..core.file_utils import make_standard_filename
from ..core.std_utils import is_gb_code, GB_CODES
from ..models import ParsedStdInfo

logger = logging.getLogger(__name__)


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
    def _newer_exists_locally(item, all_items) -> bool:
        """检查 match_status=="newer" 对应的新版文件是否已在本地存在。

        遍历所有已解析条目，查找是否已有与当前条目同代号、同序号、
        同部分号、且查询结果为 exact 匹配的文件。
        若存在则说明新版标准已由用户持有，无需重复下载。
        """
        code = (getattr(item, 'logical_code', '') or '').replace('/', '').upper()
        number = getattr(item, 'number', 0)
        part = getattr(item, 'part', None)
        for other in all_items:
            if other is item:
                continue
            other_code = (getattr(other, 'logical_code', '') or '').replace('/', '').upper()
            if other_code != code:
                continue
            if getattr(other, 'number', 0) != number:
                continue
            if getattr(other, 'part', None) != part:
                continue
            if getattr(other, 'match_status', '') == 'exact':
                return True
        return False

    def classify_after_scan(self, items: List[ParsedStdInfo]) -> dict:
        """扫描后第一轮判断。按 next_action 分堆。

        返回 {"archive": [...], "normalize": [...], "query": [...], "fallback": [...]}
        """
        buckets: dict = {"archive": [], "normalize": [], "query": [], "fallback": []}
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

    def classify_after_query(self, items: List[ParsedStdInfo]) -> dict:
        """查询后第二轮判断。按 effect_status 分堆。

        返回 {"organize": [...], "expire": [...], "download": [...],
              "pending": [...], "fallback": [...]}

        路由规则（按优先级）：
        1. match_status=="newer" + GB + 非采标 → download（远程有更新版且可下载）
           match_status=="newer" + GB + 采标   → pending（有更新版但采标受限，不可下载）
        2. 未查到/未知/状态缺失 → pending（与 manager 统一，原 fallback 过于宽泛）
        3. 待确认 → pending
        4. 废止/已废止/作废 + 有替代信息 + GB → download（manager _resolve_replaces 已填充 found_replaces）
        5. 废止/已废止/作废 → expire（标准已死，不可下载）
        6. 被代替 + 有替代标准 + GB 类代码 → download（openstd 可下载新版）
        7. 被代替（无替代或非 GB）→ expire（无法下载，过期归档）
        8. 现行 → organize（文件名规范）/ normalize（需重命名）
        9. 其他 → fallback
        """
        buckets: dict = {"organize": [], "normalize": [], "expire": [],
                         "download": [], "pending": [], "fallback": []}
        for p in items:
            status = getattr(p, "effect_status", "") or ""
            replaces = getattr(p, "found_replaces", "") or ""
            code = getattr(p, "logical_code", "") or ""
            match_status = getattr(p, "match_status", "") or ""
            logger.debug("路由: %s | 状态=%s match=%s 采标=%s replaces=%s",
                         p.get_full_number(), status, match_status,
                         getattr(p, 'is_adopted', False), bool(replaces))
            has_valid_replaces = bool(replaces and replaces not in ("网站无此分类",))
            is_gb = is_gb_code(code)

            # 规则0: 非 exact 匹配 → pending（置信不足，等以后重查）
            if match_status and match_status != "exact":
                buckets["pending"].append(p)
                continue

            # 规则1: match_status=="newer" + GB + 非采标 → 远程有更新版，可下载
            # ⚠️ 下载前先检查新版是否已在本地存在——避免重复下载
            if match_status == "newer" and is_gb:
                if getattr(p, 'is_adopted', False):
                    buckets["pending"].append(p)
                elif self._newer_exists_locally(p, items):
                    # 新版文件已在本地，旧版直接归档过期，不下载
                    logger.debug("路由: %s | 新版已本地存在，跳过下载→归档过期",
                                 p.get_full_number())
                    buckets["expire"].append(p)
                else:
                    buckets["download"].append(p)
                continue

            # 规则2: 未查到/未知/状态缺失 → 待确认
            if not status or status == "未知":
                buckets["pending"].append(p)
                continue

            # 规则3: 待确认 → 待确认
            if status == "待确认":
                buckets["pending"].append(p)
                continue

            # 规则4+5: 废止/已废止/作废
            if status in ("废止", "已废止", "作废"):
                if has_valid_replaces and is_gb:
                    if getattr(p, 'is_adopted', False):
                        buckets["pending"].append(p)
                    else:
                        buckets["download"].append(p)
                else:
                    buckets["expire"].append(p)
                continue

            # 规则6+7: 被代替
            if status == "被代替":
                if has_valid_replaces and is_gb:
                    if getattr(p, 'is_adopted', False):
                        buckets["pending"].append(p)
                    else:
                        buckets["download"].append(p)
                else:
                    buckets["expire"].append(p)
                continue

            # 规则8: 现行 → 检查文件名是否已符合规范格式
            if status == "现行":
                expected = make_standard_filename(
                    p.logical_code, p.number, p.year,
                    p.std_name, getattr(p, "part", None),
                    language=getattr(p, "language", ""),
                    num_prefix=getattr(p, "num_prefix", ""),
                    num_suffix=getattr(p, "num_suffix", ""),
                    ext=getattr(p, "ext", "pdf"))
                actual = os.path.basename(p.source_path or "")
                if actual == expected:
                    buckets["organize"].append(p)
                else:
                    buckets["normalize"].append(p)
                continue

            # 规则9: 其他（含"即将实施"等未明确处理的状态）→ 兜底
            buckets["fallback"].append(p)
        return buckets

    def apply_actions(self, items: List[ParsedStdInfo]) -> dict:
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
        for p in buckets.get("pending", []):
            p.next_action = "pending"
        for p in buckets.get("fallback", []):
            p.next_action = "not_found"
        return buckets

    def classify_after_download(self, items: List[ParsedStdInfo]) -> dict:
        """下载完成后第三轮判断。已下载的全部送归档。

        返回 {"organize": [...]}
        """
        return {"organize": list(items)}
