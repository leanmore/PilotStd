# pilotstd/query/site_config.py
# 默认站点配置 — 单一事实来源。
# manager / main_window / cli 均从此导入，不再各自手写。

from .rotator import SiteState


def create_default_sites() -> list[SiteState]:
    """创建默认站点配置，返回按优先级排序的 SiteState 列表。

    ahbz:    安徽标准化信息服务平台（免鉴权，230万条，全员模糊code匹配后精确过滤）
    njbz365: 南京标准公共服务平台（新站 .cn，2026-05-25 上线，含token/sign）
    std_gov: 全国标准信息公共服务平台（GB主力）
    hbba:    行业标准信息服务平台（行标主力）
    iso_gov: ISO 国际标准平台（国内镜像）
    dbba:    地方标准信息服务平台
    csres:   工标网（仅 HTTP，24h 拒绝冷却）
    """
    return [
        SiteState(
            name="ahbz",
            base_url="https://bzxx.ahbz.org.cn",
            max_requests=200,
            daily_limit=800,
            cooldown_seconds=300,
        ),
        SiteState(
            name="std_gov",
            base_url="https://openstd.samr.gov.cn",
            max_requests=200,
            daily_limit=800,
            cooldown_seconds=300,
        ),
        SiteState(
            name="hbba",
            base_url="https://hbba.sacinfo.org.cn",
            max_requests=200,
            daily_limit=800,
            cooldown_seconds=900,
        ),
        SiteState(
            name="iso_gov",
            base_url="https://std.samr.gov.cn",
            max_requests=200,
            daily_limit=800,
        ),
        SiteState(
            name="njbz365",
            base_url="https://www.njbz365.cn",
            max_requests=200,
            daily_limit=800,
        ),
        SiteState(
            name="dbba",
            base_url="https://dbba.sacinfo.org.cn",
            max_requests=200,
            daily_limit=800,
        ),
        SiteState(
            name="csres",
            base_url="http://www.csres.com",
            fallback_urls=["http://222.73.18.35"],
            max_requests=50,
            daily_limit=200,
        ),
        SiteState(
            name="ttbz",
            base_url="https://www.ttbz.org.cn",
            max_requests=100,
            daily_limit=400,
            cooldown_seconds=1,
        ),
    ]
