# pilotstd/ui/core/handlers/download_flow_engine.py
"""DownloadFlowEngine — 下载相关的纯逻辑层（零 Qt 依赖，零文件 I/O）。

所有方法输入/输出均为 Python 原生类型或项目数据类（ParsedStdInfo），
不依赖任何 Qt 控件、文件系统访问或网络操作。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────
DEFAULT_THRESHOLD_DAYS = 28
"""默认的'过新'判定阈值（天）：发布日期在此天数内的标准视为过新，暂不下载。"""


class DownloadFlowEngine:
    """下载流程的纯逻辑处理：过滤、解析、校验、去重。"""

    @staticmethod
    def filter_too_new_standards(
        standards: list[Any],
        threshold_days: int = DEFAULT_THRESHOLD_DAYS,
        reference_date: date | None = None,
    ) -> list[Any]:
        """筛选发布日期过近的标准。

        Args:
            standards: ParsedStdInfo 列表
            threshold_days: 阈值天数，在此天数内发布的视为过新
            reference_date: 参考日期，默认当天

        Returns:
            过新的标准列表（与输入列表中的对象同一引用）。
        """
        if reference_date is None:
            reference_date = date.today()

        too_new: list[Any] = []
        for p in standards:
            pub_str = getattr(p, "found_publish_date", "")
            if not pub_str:
                continue
            try:
                pub_date = datetime.strptime(pub_str, "%Y-%m-%d").date()
                if reference_date - pub_date < timedelta(days=threshold_days):
                    too_new.append(p)
            except (ValueError, TypeError):
                continue
        return too_new

    # ═══════════════════════════════════════════════════════════════
    # 路径有效性校验（纯字符串操作，不检查文件系统）
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def validate_download_paths(paths: list[str], root_dir: str) -> dict[str, bool]:
        """校验下载目标路径的合法性。

        仅做字符串级别的安全检查：空路径、含空字节、路径遍历攻击、超长路径。
        不检查文件系统（文件是否存在、磁盘空间等）。

        Args:
            paths: 待校验的路径列表
            root_dir: 下载根目录

        Returns:
            {path: is_valid} 映射。
        """
        result: dict[str, bool] = {}
        for p in paths:
            if not isinstance(p, str) or not p.strip():
                result[str(p)] = False
                continue
            # 空字节注入
            if "\x00" in p:
                result[p] = False
                continue
            # 路径遍历
            segments = p.replace("\\", "/").split("/")
            if any(seg == ".." for seg in segments):
                result[p] = False
                continue
            # 超长路径
            if len(p) > 4096:
                result[p] = False
                continue
            result[p] = True
        return result

    # ═══════════════════════════════════════════════════════════════
    # CSV 解析（纯字符串操作，零文件 I/O）
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def parse_download_csv(csv_content: str | None) -> list[dict[str, str]]:
        """解析下载清单 CSV 字符串，返回 list[dict]。

        Args:
            csv_content: CSV 格式字符串，首行为表头

        Returns:
            每行一个 dict（key=表头），空行自动过滤。
            输入为空/None/非 str 类型时返回空列表。
        """
        import csv
        import io

        if not isinstance(csv_content, str) or not csv_content.strip():
            return []
        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            return [row for row in reader if any(v.strip() for v in row.values())]
        except Exception:
            return []

    # ═══════════════════════════════════════════════════════════════
    # 下载去重（纯数据结构操作）
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def deduplicate_downloads(items: list[Any], key: str) -> list[Any]:
        """按指定 key 去重，保留首次出现，维持原始顺序。

        Args:
            items: dict 列表
            key: 去重依据的字段名

        Returns:
            去重后的列表。非 dict 元素或 key 值为 None 的元素被跳过。
        """
        seen: set[Any] = set()
        result: list[Any] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            val = item.get(key)
            if val is None:
                continue
            if val not in seen:
                seen.add(val)
                result.append(item)
        return result
