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

# 历史脏代号：旧解析器曾把 ASME 系列词并入代号（`ASMEPTC`/`ASMECSD`）。
# 路由前归一化到 `ASME`，避免按通用国外代号落到 `_FOREIGN_FALLBACK`（应走 `asme` 站点）。
_ASME_SERIES_SUFFIXES = ("PTC", "CSD")


def normalize_route_code(logical_code: str) -> str:
    """路由用代号归一化：仅处理 ASME 系列词污染，其余代号原样返回。

    `ASMEPTC`/`ASMECSD`（历史脏代号）与 `ASME PTC`（带系列词的代号）统一归一为 `ASME`，
    使路由命中 `CODE_ROUTES["ASME"]`（asme 站点），而不是通用国外兜底链。
    """
    text = str(logical_code or "").strip()
    if not text:
        return ""
    tokens = text.split(" ")
    first = tokens[0].upper()
    if first == "ASME":
        return "ASME"
    for suffix in _ASME_SERIES_SUFFIXES:
        if first == f"ASME{suffix}":
            return "ASME"
    return text


# 按标准代号分流：专业站点优先，365二线，国标/行业兜底
def _build_default_code_routes() -> dict[str, list[str]]:
    from ...organizer.industry_lookup import _DB_PROVINCE_MAP

    routes: dict[str, list[str]] = {
        "ISO": ["iso_gov", "ahbz", "njbz365"],
        "IEC": ["iso_gov", "ahbz", "njbz365"],
        # 文物保护行业标准→专业平台优先
        "WW": ["ncha", "std_gov"],
        "WW/T": ["ncha", "std_gov"],
        # API（美国石油学会）标准→API Webstore 优先
        "API": ["api_webstore", "iso_gov", "csres"],
        # ASME（美国机械工程师学会）标准→ASME 商品目录优先
        "ASME": ["asme", "iso_gov", "csres"],
    }
    # 地方标准省级代码：数据库11,数据库11/,数据库35,数据库35/等→优先
    for province_code in _DB_PROVINCE_MAP:
        chain = ["dbba", "ahbz", "njbz365"]
        if str(province_code) == "50":
            # 重庆 DB50：重庆标准信息平台是权威源（含全文 PDF），排在地标平台之前
            chain = ["cqis", *chain]
        routes[f"DB{province_code}"] = chain
        routes[f"DB{province_code}/T"] = chain
    return routes


CODE_ROUTES = _build_default_code_routes()
