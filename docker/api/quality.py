# 容器//脚本—数据质量检查接口
import logging

from fastapi import Depends, Request
from fastapi.routing import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from ..auth import require_role
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["quality"])


class QualityViolationItem(BaseModel):
    """单条质量违规：规则名、严重程度、文件、行号与说明。"""

    rule: str
    severity: str
    file: str
    line: int
    message: str


class QualitySummary(BaseModel):
    """质量检查摘要：违规总数、已检文件数、是否通过及失败数。"""

    total: int
    files_checked: int
    passed: bool
    failed: int


class QualityRunResponse(BaseModel):
    """数据质量检查响应：总体结果、违规列表与摘要。"""

    # 允许服务层附加新键原样透传，避免响应模型反向收窄既有接口契约
    model_config = ConfigDict(extra="allow")

    ok: bool
    results: list[QualityViolationItem] = Field(default_factory=list)
    summary: QualitySummary | None = None


@router.post("/api/quality/run", response_model=QualityRunResponse, response_model_exclude_unset=True)
@require_role("admin")
def run_quality_check(request: Request, mgr=Depends(get_manager_dep)):
    """运行数据质量检查。"""
    return mgr.quality_service.run_check()
