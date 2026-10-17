"""管道进度写入的安全封装（体检 D-11）。

四个业务端点（archive/download/normalize/query）在进入各自阶段时写一次
"running" 进度。原实现各自 `try: ... except Exception: pass`——写失败时前端
进度条会停在中间态且无任何痕迹。

统一走本函数：失败只记日志，不阻断业务；日志留 run_id/step/status 以便排查。
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def safe_update_step(
    store: Any, run_id: str, step: str, status: str, percent: int, **kwargs: Any
) -> None:
    """调用 `store.update_step`；异常只记日志，绝不向上抛。"""
    try:
        store.update_step(run_id, step, status, percent, **kwargs)
    except Exception as e:
        logger.info(
            "pipeline update skipped (run_id=%s, step=%s, status=%s): %s",
            run_id,
            step,
            status,
            e,
        )
