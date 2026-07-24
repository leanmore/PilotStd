# pilotstd/query/site_config.py
# 默认站点配置 — 单一事实来源。
# manager / main_window / cli 均从此导入，不再各自手写。

from .rotator import SiteState


def create_default_sites() -> list[SiteState]:
    """创建默认站点配置，返回按优先级排序的 SiteState 列表。"""
    S = SiteState  # noqa: N806 — 本地别名
    return [
        S(name="ahbz", base_url="https://bzxx.ahbz.org.cn", max_requests=200, daily_limit=800, cooldown_seconds=300),
        S(
            name="std_gov",
            base_url="https://openstd.samr.gov.cn",
            max_requests=200,
            daily_limit=800,
            cooldown_seconds=300,
        ),
        S(name="hbba", base_url="https://hbba.sacinfo.org.cn", max_requests=200, daily_limit=800, cooldown_seconds=900),
        S(name="iso_gov", base_url="https://std.samr.gov.cn", max_requests=200, daily_limit=800),
        S(name="njbz365", base_url="https://www.njbz365.cn", max_requests=200, daily_limit=800),
        S(name="dbba", base_url="https://dbba.sacinfo.org.cn", max_requests=200, daily_limit=800),
        S(
            name="csres",
            base_url="http://www.csres.com",
            fallback_urls=["http://222.73.18.35"],
            max_requests=50,
            daily_limit=200,
        ),
        S(name="ttbz", base_url="https://www.ttbz.org.cn", max_requests=100, daily_limit=400, cooldown_seconds=1),
        S(name="mee", base_url="https://www.mee.gov.cn", max_requests=50, daily_limit=500, cooldown_seconds=2),
        S(name="nrsis", base_url="http://www.nrsis.org.cn", max_requests=30, daily_limit=300, cooldown_seconds=3),
        S(name="jtst", base_url="https://jtst.mot.gov.cn", max_requests=50, daily_limit=500, cooldown_seconds=2),
        S(name="ccsn", base_url="https://www.ccsn.org.cn", max_requests=50, daily_limit=500, cooldown_seconds=3),
        S(name="jjg", base_url="https://jjg.spc.org.cn", max_requests=100, daily_limit=1000, cooldown_seconds=1),
        S(name="sppt", base_url="https://sppt.cfsa.net.cn:8086", max_requests=50, daily_limit=500, cooldown_seconds=2),
        S(
            name="sppt_local",
            base_url="https://sppt.cfsa.net.cn:8087",
            max_requests=30,
            daily_limit=300,
            cooldown_seconds=3,
        ),
        S(
            name="gongbiaoku",
            base_url="https://www.gongbiaoku.com",
            max_requests=50,
            daily_limit=500,
            cooldown_seconds=2,
        ),
    ]
