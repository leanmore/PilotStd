# 模块：项目/查询/_配置脚本
# 默认站点配置 — 单一事实来源。
# 管理器/入口_/均从此导入，不再各自手写。
# 阶段3.1:新增__合并请求字典（21适配器完整画像）+_字段

from typing import Any

from .rotator import SiteState

# ──适配器默认画像字典（阶段3.1路由评分器数据源）────────────────
# 键=适配器_，值=完整默认配置画像
# 字段说明：
# :中文显示名
# :行业关键词列表（用于行业匹配加分）
# _:标准号前缀列表（用于前缀精确匹配+30分）
# _:是否通用适配器（→-10降权）
# :可靠性评级（//）
# _:基础权重分
# _:速率限制子字典（_/_/_冷却/_）
# _:连续错误触发冷却阈值
# _:冷却持续秒数
# :路由角色（=主力站点,=后台补偿）

ADAPTER_DEFAULT_PROFILES: dict[str, dict] = {
    "std_gov": {
        "label": "全国标准信息公共服务平台",
        "industries": [],
        "std_prefixes": ["GB", "GB/T", "GB/Z"],
        "is_general": True,
        "reliability": "high",
        "default_weight": 70,
        "rate_limit": {"request_interval": 0.3, "batch_limit": 100, "batch_cooldown": 5},
        "cooling_threshold": 5,
        "cooling_duration": 30,
        "role": "primary",
    },
    "csres": {
        "label": "工标网",
        "industries": [],
        "std_prefixes": ["GB", "GB/T", "GB/Z"],
        "is_general": True,
        "reliability": "low",
        "default_weight": 30,
        "rate_limit": {"request_interval": 2.0, "batch_limit": 10, "batch_cooldown": 120},
        "cooling_threshold": 1,
        "cooling_duration": 86400,
        "role": "background",
    },
    "cssn": {
        "label": "中国标准服务网",
        "industries": [],
        "std_prefixes": ["GB", "GB/T"],
        "is_general": True,
        "reliability": "high",
        "default_weight": 60,
        "rate_limit": {"request_interval": 0.3, "batch_limit": 80, "batch_cooldown": 5},
        "cooling_threshold": 5,
        "cooling_duration": 30,
        "role": "primary",
    },
    "jjg": {
        "label": "国家计量技术规范全文公开系统",
        "industries": ["计量"],
        "std_prefixes": ["JJG", "JJF"],
        "is_general": False,
        "reliability": "high",
        "default_weight": 60,
        "rate_limit": {"request_interval": 0.3, "batch_limit": 80, "batch_cooldown": 5},
        "cooling_threshold": 5,
        "cooling_duration": 30,
        "role": "primary",
    },
    "ahbz": {
        "label": "安徽标准化信息服务平台",
        "industries": [],
        "std_prefixes": ["GB", "GB/T", "DB"],
        "is_general": True,
        "reliability": "high",
        "default_weight": 55,
        "rate_limit": {"request_interval": 0.5, "batch_limit": 50, "batch_cooldown": 5},
        "cooling_threshold": 3,
        "cooling_duration": 300,
        "role": "primary",
    },
    "hbba": {
        "label": "行业标准信息服务平台",
        "industries": [],
        "std_prefixes": ["SH", "NB", "HG", "JB", "YB", "SY", "CB", "QB", "FZ"],
        "is_general": False,
        "reliability": "high",
        "default_weight": 55,
        "rate_limit": {"request_interval": 0.5, "batch_limit": 50, "batch_cooldown": 5},
        "cooling_threshold": 3,
        "cooling_duration": 900,
        "role": "primary",
    },
    "miit": {
        "label": "工信部行业标准查询",
        "industries": ["工业"],
        "std_prefixes": ["YD", "SJ"],
        "is_general": False,
        "reliability": "medium",
        "default_weight": 55,
        "rate_limit": {"request_interval": 0.5, "batch_limit": 50, "batch_cooldown": 5},
        "cooling_threshold": 3,
        "cooling_duration": 300,
        "role": "primary",
    },
    "jtst": {
        "label": "交通运输部标准查询",
        "industries": ["交通"],
        "std_prefixes": ["JT", "JTG", "JTS"],
        "is_general": False,
        "reliability": "medium",
        "default_weight": 55,
        "rate_limit": {"request_interval": 0.5, "batch_limit": 50, "batch_cooldown": 5},
        "cooling_threshold": 3,
        "cooling_duration": 300,
        "role": "primary",
    },
    "mee": {
        "label": "生态环境部标准查询",
        "industries": ["环保"],
        "std_prefixes": ["HJ", "GB"],
        "is_general": False,
        "reliability": "medium",
        "default_weight": 55,
        "rate_limit": {"request_interval": 0.5, "batch_limit": 50, "batch_cooldown": 5},
        "cooling_threshold": 3,
        "cooling_duration": 300,
        "role": "primary",
    },
    "nrsis": {
        "label": "自然资源标准信息服务平台",
        "industries": ["自然资源"],
        "std_prefixes": ["DZ", "TD"],
        "is_general": False,
        "reliability": "medium",
        "default_weight": 55,
        "rate_limit": {"request_interval": 0.5, "batch_limit": 50, "batch_cooldown": 5},
        "cooling_threshold": 3,
        "cooling_duration": 300,
        "role": "primary",
    },
    "sppt": {
        "label": "食品安全国家标准数据检索平台",
        "industries": ["食品"],
        "std_prefixes": ["GB"],
        "is_general": False,
        "reliability": "medium",
        "default_weight": 55,
        "rate_limit": {"request_interval": 0.5, "batch_limit": 50, "batch_cooldown": 5},
        "cooling_threshold": 3,
        "cooling_duration": 300,
        "role": "primary",
    },
    "sppt_local": {
        "label": "食品安全地方标准数据检索平台",
        "industries": ["食品"],
        "std_prefixes": ["DB"],
        "is_general": False,
        "reliability": "medium",
        "default_weight": 50,
        "rate_limit": {"request_interval": 0.5, "batch_limit": 50, "batch_cooldown": 5},
        "cooling_threshold": 3,
        "cooling_duration": 300,
        "role": "primary",
    },
    "tdpress": {
        "label": "铁路标准信息服务平台",
        "industries": ["铁路"],
        "std_prefixes": ["TB"],
        "is_general": False,
        "reliability": "medium",
        "default_weight": 55,
        "rate_limit": {"request_interval": 0.5, "batch_limit": 50, "batch_cooldown": 5},
        "cooling_threshold": 3,
        "cooling_duration": 300,
        "role": "primary",
    },
    "ncha": {
        "label": "文物保护标准查询",
        "industries": ["文物"],
        "std_prefixes": ["WW"],
        "is_general": False,
        "reliability": "medium",
        "default_weight": 55,
        "rate_limit": {"request_interval": 0.5, "batch_limit": 50, "batch_cooldown": 5},
        "cooling_threshold": 3,
        "cooling_duration": 300,
        "role": "primary",
    },
    "gongbiaoku": {
        "label": "工标库",
        "industries": [],
        "std_prefixes": [],
        "is_general": True,
        "reliability": "low",
        "default_weight": 40,
        "rate_limit": {"request_interval": 0.5, "batch_limit": 50, "batch_cooldown": 5},
        "cooling_threshold": 3,
        "cooling_duration": 300,
        "role": "primary",
    },
    "energy": {
        "label": "能源标准信息服务平台",
        "industries": ["能源"],
        "std_prefixes": ["NB", "DL"],
        "is_general": False,
        "reliability": "low",
        "default_weight": 50,
        "rate_limit": {"request_interval": 0.5, "batch_limit": 50, "batch_cooldown": 5},
        "cooling_threshold": 3,
        "cooling_duration": 300,
        "role": "primary",
    },
    "iso_gov": {
        "label": "ISO/IEC国际标准（全国标准平台子站）",
        "industries": [],
        "std_prefixes": ["ISO", "IEC", "IEEE"],
        "is_general": False,
        "reliability": "high",
        "default_weight": 60,
        "rate_limit": {"request_interval": 0.5, "batch_limit": 50, "batch_cooldown": 5},
        "cooling_threshold": 3,
        "cooling_duration": 600,
        "role": "primary",
    },
    "njbz365": {
        "label": "南京标准公共服务平台",
        "industries": [],
        "std_prefixes": [],
        "is_general": True,
        "reliability": "medium",
        "default_weight": 45,
        "rate_limit": {"request_interval": 3.0, "batch_limit": 20, "batch_cooldown": 30},
        "cooling_threshold": 3,
        "cooling_duration": 600,
        "role": "primary",
    },
    "ccsn": {
        "label": "中国工程建设标准化协会",
        "industries": ["工程建设"],
        "std_prefixes": ["CECS"],
        "is_general": False,
        "reliability": "medium",
        "default_weight": 50,
        "rate_limit": {"request_interval": 1.0, "batch_limit": 15, "batch_cooldown": 10},
        "cooling_threshold": 3,
        "cooling_duration": 300,
        "role": "primary",
    },
    "dbba": {
        "label": "地方标准信息服务平台",
        "industries": [],
        "std_prefixes": ["DB"],
        "is_general": False,
        "reliability": "high",
        "default_weight": 55,
        "rate_limit": {"request_interval": 0.5, "batch_limit": 50, "batch_cooldown": 5},
        "cooling_threshold": 3,
        "cooling_duration": 600,
        "role": "primary",
    },
    "ttbz": {
        "label": "全国团体标准信息平台",
        "industries": [],
        "std_prefixes": ["T/"],
        "is_general": False,
        "reliability": "medium",
        "default_weight": 50,
        "rate_limit": {"request_interval": 0.5, "batch_limit": 50, "batch_cooldown": 5},
        "cooling_threshold": 3,
        "cooling_duration": 300,
        "role": "primary",
    },
}


def _create_sites_part1() -> list[SiteState]:
    """第一批默认站点（前11个适配器）。"""
    S = SiteState  # noqa: N806
    return [
        S(
            name="ahbz",
            base_url="https://bzxx.ahbz.org.cn",
            search_url="https://bzxx.ahbz.org.cn/standard/query",
            max_requests=200,
            daily_limit=800,
            cooldown_seconds=300,
            request_interval=0.5,
        ),
        S(
            name="std_gov",
            base_url="https://openstd.samr.gov.cn",
            search_url="https://std.samr.gov.cn/search/stdPage",
            probe_url="https://std.samr.gov.cn/search/stdPage",
            max_requests=400,
            daily_limit=800,
            cooldown_seconds=300,
            request_interval=0.3,
        ),
        S(
            name="hbba",
            base_url="https://hbba.sacinfo.org.cn",
            search_url="https://hbba.sacinfo.org.cn/stdQueryList",
            max_requests=400,
            daily_limit=800,
            cooldown_seconds=900,
            request_interval=0.5,
        ),
        S(name="iso_gov", base_url="https://std.samr.gov.cn",
          search_url="https://std.samr.gov.cn/gj/search/gjPage",
          probe_url="https://std.samr.gov.cn/gj/search/gjPage",
          max_requests=200, daily_limit=800, request_interval=0.5),
        S(name="njbz365", base_url="https://www.njbz365.cn",
          search_url="https://www.njbz365.cn/apis",
          max_requests=200, daily_limit=800, request_interval=3.0),
        S(name="dbba", base_url="https://dbba.sacinfo.org.cn",
          search_url="https://dbba.sacinfo.org.cn/stdQueryList",
          max_requests=200, daily_limit=800, request_interval=0.5),
    ]


def _create_sites_part1b() -> list[SiteState]:
    """第一批默认站点后半（后5个适配器）。"""
    S = SiteState  # noqa: N806
    return [
        S(
            name="csres",
            base_url="http://www.csres.com",
            search_url="http://www.csres.com/s.jsp?keyword={}",
            probe_url="http://www.csres.com/s.jsp",
            fallback_urls=["http://222.73.18.35"],
            max_requests=50,
            daily_limit=200,
            request_interval=2.0,
        ),
        S(
            name="ttbz",
            base_url="https://www.ttbz.org.cn",
            search_url="https://www.ttbz.org.cn/cms-proxy/ms/portal/standardInfo/getPortalStandardList",
            max_requests=100,
            daily_limit=400,
            cooldown_seconds=1,
            request_interval=0.5,
        ),
        S(
            name="mee",
            base_url="https://www.mee.gov.cn",
            search_url="https://www.mee.gov.cn/was5/web/search",
            probe_url="https://www.mee.gov.cn/was5/web/search",
            max_requests=50,
            daily_limit=500,
            cooldown_seconds=2,
            request_interval=0.5,
        ),
        S(
            name="nrsis",
            base_url="http://www.nrsis.org.cn",
            search_url="http://www.nrsis.org.cn/portal/xxcx/std",
            probe_url="http://www.nrsis.org.cn/portal/xxcx/std",
            max_requests=30,
            daily_limit=300,
            cooldown_seconds=3,
            request_interval=0.5,
        ),
        S(
            name="jtst",
            base_url="https://jtst.mot.gov.cn",
            search_url="https://jtst.mot.gov.cn/search/stdPage",
            probe_url="https://jtst.mot.gov.cn/search/stdPage",
            max_requests=50,
            daily_limit=500,
            cooldown_seconds=2,
            request_interval=0.5,
        ),
    ]


def _create_sites_part2() -> list[SiteState]:
    """第二批默认站点（中间5个适配器）。"""
    S = SiteState  # noqa: N806
    return [
        S(
            name="ccsn",
            base_url="https://www.ccsn.org.cn",
            search_url="https://www.ccsn.org.cn/Zbbz/ZbbzList.aspx",
            probe_url="https://www.ccsn.org.cn/Zbbz/ZbbzList.aspx",
            max_requests=50,
            daily_limit=500,
            cooldown_seconds=3,
            request_interval=1.0,
        ),
        S(
            name="jjg",
            base_url="https://jjg.spc.org.cn",
            search_url="https://jjg.spc.org.cn/resmea/api/standard/search/page",
            probe_url="https://jjg.spc.org.cn/resmea/api/standard/search/page",
            max_requests=100,
            daily_limit=1000,
            cooldown_seconds=1,
            request_interval=0.3,
        ),
        S(
            name="sppt",
            base_url="https://sppt.cfsa.net.cn:8086",
            search_url="https://sppt.cfsa.net.cn:8086/db",
            probe_url="https://sppt.cfsa.net.cn:8086/db",
            max_requests=50,
            daily_limit=500,
            cooldown_seconds=2,
            request_interval=0.5,
        ),
        S(
            name="sppt_local",
            base_url="https://sppt.cfsa.net.cn:8087",
            search_url="https://sppt.cfsa.net.cn:8087/db",
            max_requests=30,
            daily_limit=300,
            cooldown_seconds=3,
            request_interval=0.5,
        ),
        S(
            name="gongbiaoku",
            base_url="https://www.gongbiaoku.com",
            search_url="https://www.gongbiaoku.com/search",
            probe_url="https://www.gongbiaoku.com/search",
            max_requests=50,
            daily_limit=500,
            cooldown_seconds=2,
            request_interval=0.5,
        ),
    ]


def _create_sites_part3() -> list[SiteState]:
    """第三批默认站点（后5个适配器）。"""
    S = SiteState  # noqa: N806
    return [
        S(
            name="energy",
            base_url="https://114.251.111.103:18080",
            search_url="https://114.251.111.103:18080/zxd/portal/stdPage",
            probe_url="https://114.251.111.103:18080/zxd/portal/stdPage",
            max_requests=30,
            daily_limit=100,
            cooldown_seconds=2,
            request_interval=0.5,
        ),
        S(
            name="tdpress",
            base_url="https://biaozhun.tdpress.com",
            search_url="https://biaozhun.tdpress.com/front/queryFomePage",
            probe_url="https://biaozhun.tdpress.com/front/queryFomePage",
            max_requests=50,
            daily_limit=500,
            cooldown_seconds=1,
            request_interval=0.5,
        ),
        S(
            name="ncha",
            base_url="http://bz.ncha.gov.cn",
            search_url="http://bz.ncha.gov.cn:9005/knowledge/bzgf/find",
            max_requests=50,
            daily_limit=500,
            cooldown_seconds=1,
            request_interval=0.5,
        ),
        S(
            name="miit",
            base_url="https://std.miit.gov.cn",
            search_url="https://std.miit.gov.cn/kjsStandproject/front/zxd/stand/queryFullDisclosureStandards",
            max_requests=50,
            daily_limit=300,
            cooldown_seconds=2,
            request_interval=0.5,
        ),
        S(
            name="cssn",
            base_url="https://www.cssn.net.cn",
            search_url="https://www.cssn.net.cn/api/standards/",
            probe_url="https://www.cssn.net.cn/api/standards/",
            max_requests=100,
            daily_limit=1000,
            cooldown_seconds=1,
            request_interval=0.3,
        ),
    ]


def create_default_sites() -> list[SiteState]:
    """创建默认站点配置并应用 config.json 的 UI 覆盖，返回 SiteState 列表。

    这是站点配置的唯一运行时出口：评分器与配额追踪器都从这里读取，
    保证 UI 修改（config.json 的 query.sites）与硬编码默认值单一来源对齐。
    """
    sites = _create_sites_part1() + _create_sites_part1b() + _create_sites_part2() + _create_sites_part3()
    overrides = _load_site_overrides()
    for site in sites:
        ov = overrides.get(site.name, {})
        # config.json 的 key 与 SiteState 字段名不一致，需逐一映射
        if ov.get("daily_limit") is not None:
            site.daily_limit = ov["daily_limit"]
        if ov.get("window_limit") is not None:  # UI 写入的 key 是 window_limit
            site.max_requests = ov["window_limit"]
        if ov.get("cooling_seconds") is not None:  # UI 写入的 key 是 cooling_seconds
            site.cooldown_seconds = ov["cooling_seconds"]
        if ov.get("request_interval") is not None:
            site.request_interval = ov["request_interval"]
    return sites


def _load_site_overrides() -> dict[str, Any]:
    """从 config.json 读取 query.sites 覆盖值，容错返回空 dict。"""
    try:
        from pilotstd.core.config.manager import ConfigManager

        sites = ConfigManager().get("query.sites", {})
        return sites if isinstance(sites, dict) else {}
    except Exception:
        return {}


# 站点配置缓存：create_default_sites 每次调用会重读 config.json，此处缓存避免重复开销
_site_config_cache: dict[str, SiteState] | None = None


def get_site_config(name: str) -> SiteState | None:
    """按名称返回站点配置（含 search_url/probe_url），供适配器与健康检查读取。

    未找到返回 None，调用方需自行回退到硬编码值或 base_url。
    """
    global _site_config_cache
    if _site_config_cache is None:
        _site_config_cache = {s.name: s for s in create_default_sites()}
    return _site_config_cache.get(name)
