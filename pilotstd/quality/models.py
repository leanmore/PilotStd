# pilotstd/quality/models.py
# 数据模型

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class Violation:
    rule: str
    severity: Severity
    file: str
    line: int
    message: str


@dataclass
class CheckReport:
    violations: List[Violation] = field(default_factory=list)
    files_checked: int = 0

    @property
    def passed(self) -> bool:
        return not any(v.severity == Severity.ERROR for v in self.violations)
