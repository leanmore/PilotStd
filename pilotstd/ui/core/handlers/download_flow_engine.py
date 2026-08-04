# 模块：项目//核心/处理器/下载__引擎脚本
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

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 路径有效性校验（纯字符串操作，不检查文件系统）
    # ═══════════════════════════════════════════════════════════════ 分隔

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

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 解析（纯字符串操作，零文件/）
    # ═══════════════════════════════════════════════════════════════ 分隔

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

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 下载去重（纯数据结构操作）
    # ═══════════════════════════════════════════════════════════════ 分隔

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

    # ═══════════════════════════════════════════════════════════════ 分隔
    # 阶段2预抽取纯逻辑（待后续集成）
    # ═══════════════════════════════════════════════════════════════ 分隔

    @staticmethod
    def parse_download_url(raw_url: str) -> dict:
        """解析并标准化下载URL，提取协议、主机、路径及查询参数。

        纯字符串处理，不发起网络请求。
        """
        if not raw_url or not isinstance(raw_url, str):
            return {"valid": False, "error": "URL为空或非字符串"}
        url = raw_url.strip()
        if not url.startswith(("http://", "https://")):
            return {"valid": False, "error": "不支持的协议，仅允许http/https"}
        try:
            from urllib.parse import parse_qs, urlparse

            parsed = urlparse(url)
            if not parsed.netloc:
                return {"valid": False, "error": "缺少主机名"}
            return {
                "valid": True,
                "scheme": parsed.scheme,
                "host": parsed.netloc,
                "path": parsed.path,
                "params": parse_qs(parsed.query),
                "original": url,
            }
        except Exception as e:
            return {"valid": False, "error": f"URL解析失败: {str(e)}"}

    @staticmethod
    def calculate_retry_delay(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
        """计算指数退避重试延迟（含 10% 随机抖动）。

        Args:
            attempt: 重试次数（0-based）
            base_delay: 基础延迟秒数
            max_delay: 延迟上限秒数
        """
        if attempt < 0:
            return base_delay
        import random

        exponential = min(base_delay * (2**attempt), max_delay)
        jitter = random.uniform(0, exponential * 0.1)
        return round(exponential + jitter, 3)

    @staticmethod
    def validate_file_size(file_size: int, min_size: int = 0, max_size: int | None = None) -> dict:
        """校验文件大小是否在允许范围内。

        Args:
            file_size: 文件大小（字节）
            min_size: 最小允许大小
            max_size: 最大允许大小，None 表示不限制
        """
        if not isinstance(file_size, (int, float)) or file_size < 0:
            return {"valid": False, "message": "文件大小无效"}
        if file_size < min_size:
            return {"valid": False, "message": f"文件过小({file_size}B < {min_size}B)"}
        if max_size is not None and file_size > max_size:
            return {"valid": False, "message": f"文件过大({file_size}B > {max_size}B)"}
        return {"valid": True, "message": "大小合规"}
