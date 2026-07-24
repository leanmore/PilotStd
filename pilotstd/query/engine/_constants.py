# pilotstd/query/engine/_constants.py
# 查询引擎常量 — 站点优先级、路由表
"""PROGRESS_TAG、默认站点优先级、按标准代号分流路由表。"""

import logging

# 跨进程日志解析协议标识 — 压测脚本依赖此字符串进行心跳检测和进度解析
PROGRESS_TAG = "[PROGRESS]"

logger = logging.getLogger(__name__)

# 默认站点优先级（兜底，无代号匹配时使用）
PROD_PRIORITY = ["ahbz", "std_gov", "mee", "hbba", "iso_gov", "njbz365", "ttbz", "csres"]
# 国外标准默认路由：ahbz免鉴权优先，njbz365次选
FOREIGN_ROUTE = ["ahbz", "njbz365"]


# 按标准代号分流：专业站点优先，njbz365 二线，csres 国标/行业兜底
def _build_default_code_routes() -> dict[str, list[str]]:
    from ...organizer.industry_lookup import _DB_PROVINCE_MAP

    routes: dict[str, list[str]] = {
        "ISO": ["iso_gov", "ahbz", "njbz365"],
        "IEC": ["iso_gov", "ahbz", "njbz365"],
    }
    # 地方标准省级代码：DB11, DB11/T, DB35, DB35/T 等 → dbba 优先
    for province_code in _DB_PROVINCE_MAP:
        routes[f"DB{province_code}"] = ["dbba", "ahbz", "njbz365"]
        routes[f"DB{province_code}/T"] = ["dbba", "ahbz", "njbz365"]
    return routes


CODE_ROUTES = _build_default_code_routes()
# 行业标准（SH/NB/HG/JB 等）：行标平台优先，njbz365二线，csres兜底
INDUSTRY_ROUTE = ["hbba", "njbz365", "csres"]
