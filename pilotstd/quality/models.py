# 模块：项目//模型脚本
# 数据模型

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class Violation:
    """单条质量违规记录：规则名、严重程度、所在文件、行号、描述信息。"""

    rule: str
    severity: Severity
    file: str
    line: int
    message: str


@dataclass
class CheckReport:
    """质量检查报告：违规列表、已检查文件数，passed 属性判断是否零错误。"""

    violations: List[Violation] = field(default_factory=list)
    files_checked: int = 0

    @property
    def passed(self) -> bool:
        return not any(v.severity == Severity.ERROR for v in self.violations)
