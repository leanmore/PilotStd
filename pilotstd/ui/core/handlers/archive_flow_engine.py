# pilotstd/ui/core/handlers/archive_flow_engine.py
"""ArchiveFlowEngine — 归档相关的纯逻辑层（无 Qt 依赖）。

从 ArchiveUIHandler 中提取所有数据转换、校验、格式化方法。
"""

from __future__ import annotations

import os
from typing import Any, Callable

from ....core.config import get_library_root
from ....i18n import _

# ── 状态 → 标签映射常量 ────────────────────────────────────
_STATUS_LABELS: dict[str, str] = {
    "被代替": "被代替",
    "废止": "废止",
    "已废止": "废止",
    "作废": "废止",
}


class ArchiveFlowEngine:
    """归档相关的纯逻辑层。

    所有方法均为静态方法，不持有任何状态。
    """

    # ═══════════════════════════════════════════════════════════
    # 状态映射
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def determine_status_label(effect_status: str) -> str:
        """将生效状态映射为 file_index 中使用的状态标签。

        被代替 → '被代替'
        废止/已废止/作废 → '废止'
        其他 → '现行'
        """
        if effect_status == "被代替":
            return "被代替"
        if effect_status in ("废止", "已废止", "作废"):
            return "废止"
        return "现行"

    # ═══════════════════════════════════════════════════════════
    # 冲突检测
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def detect_file_conflicts(
        parsed_results: list[Any],
        root_dir: str,
        config: Any,
        target_path_fn: Callable[[Any, str, Any], str | None],
    ) -> list[tuple[str, str]]:
        """检测归档目标路径已存在的文件冲突。

        返回 [(源文件名, 目标路径), ...]。
        """
        conflicts: list[tuple[str, str]] = []
        for parsed in parsed_results:
            if not parsed.source_path or not os.path.exists(parsed.source_path):
                continue
            dst = target_path_fn(parsed, root_dir, config)
            if dst and os.path.exists(dst):
                conflicts.append((os.path.basename(parsed.source_path), dst))
        return conflicts

    @staticmethod
    def format_conflict_message(conflicts: list[tuple[str, str]]) -> str:
        """格式化冲突列表为可展示的文本消息。"""
        count = len(conflicts)
        sample_lines = [f"  {n} → {d}" for n, d in conflicts[:5]]
        sample = "\n".join(sample_lines)
        if count > 5:
            sample += f"\n  ... 等共 {count} 个"
        return _("msg_file_overwrite").format(count=count, sample=sample)

    # ═══════════════════════════════════════════════════════════
    # 数据过滤
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def filter_by_action(parsed_results: list[Any], action: str) -> list[Any]:
        """按 next_action 过滤标准列表。"""
        return [p for p in parsed_results if getattr(p, "next_action", "") == action]

    # ═══════════════════════════════════════════════════════════
    # 统计计数
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def count_archive_results(
        archive_results: list[tuple[int, str]],
    ) -> tuple[int, int]:
        """统计归档结果中的成功/跳过数量。返回 (saved, skipped)。"""
        saved = sum(1 for _i, s in archive_results if s == "已归档")
        skipped = len(archive_results) - saved
        return saved, skipped

    # ═══════════════════════════════════════════════════════════
    # 缺失名称检测
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def find_missing_names(parsed_results: list[Any]) -> list[str]:
        """查找标准名称缺失的条目，返回标准号列表。"""
        return [p.get_full_number() for p in parsed_results if not p.std_name and not p.found_name]

    # ═══════════════════════════════════════════════════════════
    # 格式化跳过详情
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def format_skip_details(
        archive_results: list[tuple[int, str]],
        parsed_results: list[Any],
    ) -> list[str]:
        """格式化归档跳过的文件详情列表。"""
        details: list[str] = []
        for idx, status in archive_results:
            if status != "已归档" and idx < len(parsed_results):
                p = parsed_results[idx]
                fname = os.path.basename(getattr(p, "source_path", "") or getattr(p, "raw_filename", "") or "")
                details.append(_("msg_archive_skip_line").format(name=fname, reason=status))
        return details

    # ═══════════════════════════════════════════════════════════
    # 库根路径
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def get_library_root_from_config(config: Any) -> str:
        """从配置获取标准库根目录。"""
        return get_library_root(config)
