# 模块：项目/查询/引擎/_常量脚本
# 查询引擎常量 — 站点优先级、路由表
"""PROGRESS_TAG、按标准代号分流路由表。"""

import logging

from pilotstd.query.site_config import ADAPTER_DEFAULT_PROFILES

# 跨进程日志解析协议标识 — 压测脚本依赖此字符串进行心跳检测和进度解析
PROGRESS_TAG = "[PROGRESS]"

logger = logging.getLogger(__name__)

# 阶段3.2:默认站点优先级已迁移至__合并请求+评分器动态路由
# 兜底链：按_降序排列的完整适配器列表
_DEFAULT_FALLBACK_CHAIN: list[str] = sorted(
    ADAPTER_DEFAULT_PROFILES.keys(),
    key=lambda n: ADAPTER_DEFAULT_PROFILES[n].get("default_weight", 50),
    reverse=True,
)

# 国外标准兜底路由（评分器失败时的硬编码回退）
_FOREIGN_FALLBACK = ["ahbz", "njbz365"]

# 行业标准兜底路由（评分器失败时的硬编码回退）
_INDUSTRY_FALLBACK = ["hbba", "njbz365", "csres"]


def get_fallback_chain() -> list[str]:
    """返回按权重排序的完整兜底链（评分器失败时使用）。"""
    return list(_DEFAULT_FALLBACK_CHAIN)


# 按标准代号分流：专业站点优先，365二线，国标/行业兜底
def _build_default_code_routes() -> dict[str, list[str]]:
    from ...organizer.industry_lookup import _DB_PROVINCE_MAP

    routes: dict[str, list[str]] = {
        "ISO": ["iso_gov", "ahbz", "njbz365"],
        "IEC": ["iso_gov", "ahbz", "njbz365"],
        # 文物保护行业标准→专业平台优先
        "WW": ["ncha", "std_gov"],
        "WW/T": ["ncha", "std_gov"],
    }
    # 地方标准省级代码：数据库11,数据库11/,数据库35,数据库35/等→优先
    for province_code in _DB_PROVINCE_MAP:
        routes[f"DB{province_code}"] = ["dbba", "ahbz", "njbz365"]
        routes[f"DB{province_code}/T"] = ["dbba", "ahbz", "njbz365"]
    return routes


CODE_ROUTES = _build_default_code_routes()
