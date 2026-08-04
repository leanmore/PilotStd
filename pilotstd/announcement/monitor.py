# 模块：pilotstd/announcement/monitor.py
# 公告查询阶段监控：耗时 + 成功率 + 异常计数
"""公告查询各阶段耗时与成功率统计。"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AnnounceMonitor:
    """公告查询一次完整执行的监控数据。"""

    # 每阶段耗时（毫秒）
    fetch_list_ms: int = 0
    fetch_detail_total_ms: int = 0
    parse_total_ms: int = 0
    write_db_ms: int = 0

    # 网络统计
    api_calls: int = 0
    api_failures: int = 0

    # 解析统计
    total_announcements: int = 0
    total_standards_parsed: int = 0
    html_hits: int = 0
    attachment_hits: int = 0
    ocr_hits: int = 0

    _t0: float = field(default_factory=time.time, repr=False)
    _stage_start: float = field(default=0, repr=False)

    def start_stage(self) -> None:
        """开始计时一个新阶段。"""
        self._stage_start = time.time()

    def end_stage(self, stage_name: str) -> float:
        """结束当前阶段计时，返回耗时（秒）。"""
        elapsed = time.time() - self._stage_start
        elapsed_ms = int(elapsed * 1000)
        if stage_name == "fetch_list":
            self.fetch_list_ms = elapsed_ms
        elif stage_name == "fetch_detail":
            self.fetch_detail_total_ms += elapsed_ms
        elif stage_name == "parse":
            self.parse_total_ms += elapsed_ms
        elif stage_name == "write_db":
            self.write_db_ms = elapsed_ms
        return elapsed

    def inc_api_call(self, success: bool = True) -> None:
        """记录一次 API 调用，success=False 时计入失败次数。"""
        self.api_calls += 1
        if not success:
            self.api_failures += 1

    @property
    def total_elapsed_ms(self) -> int:
        return int((time.time() - self._t0) * 1000)

    def summary(self) -> str:
        """生成单行监控摘要：公告数/标准数/HTML+附件+OCR命中/API成功率/各阶段耗时。"""
        total = self.total_announcements
        if total == 0:
            return "公告: 无数据"
        api_ok = self.api_calls - self.api_failures
        return (
            f"公告: {total}条, {self.total_standards_parsed}标准 | "
            f"HTML={self.html_hits} 附件={self.attachment_hits} OCR={self.ocr_hits} | "
            f"API={self.api_calls}(成功{api_ok}) | "
            f"耗时: 列表={self.fetch_list_ms}ms 详情={self.fetch_detail_total_ms}ms "
            f"解析={self.parse_total_ms}ms 写入={self.write_db_ms}ms"
        )
