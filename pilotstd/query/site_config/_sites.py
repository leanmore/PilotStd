# 模块：项目/查询/站点配置/站点数据
# 默认站点定义（4 批）— 由加载器汇总为运行时配置。
# 注意：本文件只承载站点硬编码默认值，运行时覆盖逻辑在加载器中。

from ..rotator import SiteState


# ── 第一批：国内综合主力站点（国标/行标查询主入口）──
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


# ── 第一批后半：行业/协会/地方标准站点 ──
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


# ── 第二批：标准委/计量/食品/工标库站点 ──
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


# ── 第三批：能源/出版社/文物/工信/标准服务网站点 ──
def _create_sites_part3() -> list[SiteState]:
    """第三批默认站点（后5个适配器）。"""
    S = SiteState  # noqa: N806
    return [
        S(
            name="energy",
            base_url="https://114.251.111.103:18080",
            search_url="https://114.251.111.103:18080/zxd/portal/stdPage",
            probe_url="https://114.251.111.103:18080/zxd/portal/stdPage",
            # 该端点是 Bootstrap-table AJAX：不带 keyword/tid/limit/offset 直接返回 400，
            # 曾导致健康检查每小时把在线站点判为 down（2026-09-25 实测：裸 GET 400，带参 200）
            probe_params={"keyword": "GB", "tid": "0", "op": "", "limit": 15, "offset": 0},
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
