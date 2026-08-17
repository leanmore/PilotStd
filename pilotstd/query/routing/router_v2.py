# 模块：项目/查询/路由/v2核心脚本
# 阶段二：三级漏斗路由引擎 v2.0
# 消费 config/site_capabilities.yaml 能力模型，替代 scorer.py 的扁平评分机制。
# 分隔
# 设计要点：
# 1. 查询类型三分支：国内标准号 / 国际标准号 / 纯关键词，各走不同漏斗路径
# 2. L1 只做国内标准精准匹配；L2 只做有标准号的综合兜底；L3 是模糊探索与最终兜底
# 3. 每个路由决策产出 decisions 记录，禁止黑盒排序
# 4. reliability 权重硬编码在代码中，不从 YAML 读取，避免配置漂移

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import Optional

import yaml  # type: ignore[import-untyped]  # PyYAML 无类型存根，项目未引入 types-PyYAML

# ── 数据结构 ──────────────────────────────────────────────


@dataclass
class QueryIntent:
    """意图解析结果：从查询字符串提取的结构化特征。"""

    std_type: Optional[str]  # 标准号前缀，如 "GB/T"、"HJ"、"ISO"，无则为 None
    industry: Optional[str]  # 行业领域，如 "环保"、"计量"，无则为 None
    is_international: bool  # 是否国际标准（ISO/IEC/EN 等）
    is_keyword_query: bool  # 是否纯关键词查询（无标准号前缀）
    raw_query: str  # 原始查询字符串


@dataclass
class Classification:
    """站点分类（level1 + level2）。"""

    level1: str  # 综合 / 特色
    level2: str  # 国内综合 / 全综合 / 按标准类型区分 / 按领域区分


@dataclass
class Capabilities:
    """站点能力声明。"""

    supported_types: list[str]  # 支持的标准前缀列表
    industries: list[str]  # 覆盖行业领域，空表示无领域限制
    is_international: bool  # 是否覆盖国际标准（仅全综合站为 True）
    search_reliability: str  # 搜索可靠性评级（unknown/low/medium/high）


@dataclass
class Constraints:
    """站点约束。"""

    batch_limit: int  # 单批次请求硬上限


@dataclass
class Status:
    """站点运行时状态快照。"""

    historical_hit_rate: float  # 历史命中率，无可查数据为 0.0


@dataclass
class SiteCapability:
    """单个站点的完整能力模型（对应 YAML 中的一个站点条目）。"""

    site_id: str
    classification: Classification
    capabilities: Capabilities
    constraints: Constraints
    status: Status
    notes: str


@dataclass
class RouteChain:
    """路由结果：有序站点列表 + 每个站点的选择理由。"""

    sites: list[str]  # 有序站点 ID 列表
    decisions: list[str]  # 每个站点的选择理由（可观测性）


# ── 意图解析器 ────────────────────────────────────────────

# 国际标准前缀集合：命中即为国际查询
_INTERNATIONAL_PREFIXES = {"ISO", "IEC", "EN", "IEEE", "ASTM", "JIS", "DIN", "BS"}

# 标准号前缀 → 领域映射（标准代号能唯一确定领域时使用）
# 仅收录"明确对应单一领域"的代号；GB/DB 等通用代号不在此列，
# 因为它们对应多个领域（GB 覆盖全领域，DB 覆盖所有地方），无法唯一推断。
_STD_TYPE_TO_INDUSTRY: dict[str, str] = {
    "HJ": "环保",
    "JJG": "计量",
    "JJF": "计量",
    "YD": "工业",
    "SJ": "工业",
    "JT": "交通",
    "JTG": "交通",
    "JTS": "交通",
    "DZ": "自然资源",
    "TD": "自然资源",
    "TB": "铁路",
    "WW": "文物",
    "NB": "能源",
    "DL": "能源",
    "CECS": "工程建设",
}

# 行业关键词词典：industry 名称 → 中文关键词列表
# key 与 site_capabilities.yaml 中 capabilities.industries 的值对齐，
# 覆盖全部 10 个领域，保证从 YAML 提取的每个 industry 都有对应关键词。
_INDUSTRY_KEYWORDS: dict[str, list[str]] = {
    "环保": ["环境", "排放", "污染", "水质", "大气", "生态"],
    "食品": ["食品", "添加剂", "营养", "安全"],
    "计量": ["计量", "检定", "校准"],
    "交通": ["交通", "运输", "公路", "水运", "航运"],
    "工业": ["工业", "信息化", "通信", "电子"],
    "铁路": ["铁路", "轨道", "机车"],
    "自然资源": ["自然资源", "土地", "矿产", "测绘", "海洋", "地质"],
    "文物": ["文物", "保护", "考古", "遗址"],
    "能源": ["能源", "电力", "光伏", "风电", "核电", "新能源"],
    "工程建设": ["工程建设", "建筑", "结构", "施工", "市政"],
}

# 标准号前缀正则：匹配开头的 2-6 个字母（可带斜杠后缀）。
# 不强制要求后面跟数字，以兼容批量路径传入的纯代号（如 "GB/T"、"ISO"）；
# 至少 2 个字母，避免把单字母或纯中文关键词误判为标准号。
_STD_PREFIX_RE = re.compile(r"^([A-Za-z]{2,6}(?:/[A-Za-z])?)")


class IntentParser:
    """意图解析器：规则库驱动（正则 + 关键词字典），不调用外部 API。"""

    def __init__(self, industry_keywords: Optional[dict[str, list[str]]] = None) -> None:
        # 领域词典可注入（测试用），默认用模块级硬编码词典
        self._industry_keywords = industry_keywords if industry_keywords is not None else _INDUSTRY_KEYWORDS

    def parse(self, query: str) -> QueryIntent:
        """从查询字符串提取结构化意图。"""
        raw = query.strip()
        std_type = self._extract_std_type(raw)
        industry = self._extract_industry(raw, std_type)
        is_international = std_type in _INTERNATIONAL_PREFIXES
        # 无标准号前缀即视为纯关键词查询
        is_keyword_query = std_type is None
        return QueryIntent(
            std_type=std_type,
            industry=industry,
            is_international=is_international,
            is_keyword_query=is_keyword_query,
            raw_query=raw,
        )

    @staticmethod
    def _extract_std_type(raw: str) -> Optional[str]:
        """用正则提取标准号前缀，未匹配到返回 None。"""
        m = _STD_PREFIX_RE.match(raw)
        if m:
            return m.group(1).upper()
        return None

    def _extract_industry(self, raw: str, std_type: Optional[str]) -> Optional[str]:
        """识别行业领域：标准号前缀推断优先，其次中文关键词匹配。"""
        # 1. 标准号前缀直接推断领域（优先级最高）
        if std_type and std_type in _STD_TYPE_TO_INDUSTRY:
            return _STD_TYPE_TO_INDUSTRY[std_type]
        # 2. 中文关键词匹配
        for industry, keywords in self._industry_keywords.items():
            if any(kw in raw for kw in keywords):
                return industry
        return None


# ── 动态配额管理器 ────────────────────────────────────────


class QuotaManager:
    """动态配额管理器：管理站点配额的消耗与溢出控制（线程安全）。"""

    def __init__(self, capabilities: list[SiteCapability]) -> None:
        self._capabilities: dict[str, SiteCapability] = {s.site_id: s for s in capabilities}
        # 已消耗配额计数，初始为 0
        self._used: dict[str, int] = {s.site_id: 0 for s in capabilities}
        # 线程锁保证 consume 原子性，支持并发查询场景
        self._lock = threading.Lock()

    def get_available_sites(self, layer: str, intent: QueryIntent) -> list[SiteCapability]:
        """返回指定层级中配额未满的站点列表。

        层级过滤规则（intent 参数预留给后续能力预过滤，当前层级判定不依赖它）：
        - "L1" → 特色站（level1 == 特色）
        - "L2" → 综合站（国内综合 / 全综合）
        - "L3" → 全综合站
        """
        with self._lock:
            layer_sites = self._filter_by_layer(layer)
            return [s for s in layer_sites if self._used[s.site_id] < s.constraints.batch_limit]

    def consume(self, site_id: str) -> bool:
        """原子消耗一个配额，返回是否成功。"""
        with self._lock:
            cap = self._capabilities.get(site_id)
            if cap is None or self._used[site_id] >= cap.constraints.batch_limit:
                return False
            self._used[site_id] += 1
            return True

    def is_exhausted(self, site_id: str) -> bool:
        """检查站点配额是否耗尽（未知站点视为已耗尽）。"""
        with self._lock:
            cap = self._capabilities.get(site_id)
            if cap is None:
                return True
            return self._used[site_id] >= cap.constraints.batch_limit

    def _filter_by_layer(self, layer: str) -> list[SiteCapability]:
        """按层级过滤站点，返回保持 YAML 原始顺序的站点列表。"""
        sites = list(self._capabilities.values())
        if layer == "L1":
            return [s for s in sites if s.classification.level1 == "特色"]
        if layer == "L2":
            return [s for s in sites if s.classification.level2 in ("国内综合", "全综合")]
        if layer == "L3":
            return [s for s in sites if s.classification.level2 == "全综合"]
        return []


# ── 三级漏斗路由引擎 ──────────────────────────────────────

# reliability 权重映射表（硬编码，不从 YAML 读取，避免配置漂移）
# high：历史验证可靠；medium：部分场景可用；low：已知缺陷保留兜底；unknown：无数据最后选项
RELIABILITY_WEIGHTS: dict[str, float] = {
    "high": 1.0,
    "medium": 0.6,
    "low": 0.2,
    "unknown": 0.0,
}


class RouterEngine:
    """三级漏斗路由引擎：L1 精准匹配 → L2 综合兜底 → L3 探索层。"""

    def __init__(self, capabilities: list[SiteCapability], quota: QuotaManager) -> None:
        self._capabilities: dict[str, SiteCapability] = {s.site_id: s for s in capabilities}
        self.quota = quota

    def route(self, intent: QueryIntent) -> RouteChain:
        """路由入口：查询类型三分支。

        国际标准分支（is_international=True）：跳过 L1 → L2 → L3
        国内标准分支（is_international=False 且有标准号）：L1 → L2 → L3
        纯关键词分支（is_keyword_query=True）：跳过 L1/L2 → 直接 L3
        """
        if intent.is_keyword_query:
            # 纯关键词分支：直接进探索层
            return self._route_l3(intent)

        if intent.is_international:
            # 国际分支：国际标准不走 L1（L1 只做国内精准匹配）
            chain = self._route_l2(intent)
            if not chain.sites:
                chain = self._route_l3(intent)
            return chain

        # 国内分支：L1 → L2 → L3 逐级降级
        chain = self._route_l1(intent)
        if not chain.sites:
            chain = self._route_l2(intent)
        if not chain.sites:
            chain = self._route_l3(intent)
        return chain

    def _route_l1(self, intent: QueryIntent) -> RouteChain:
        """L1 精准匹配层：仅处理国内标准，按标准前缀 + 领域精准匹配。"""
        # 硬性前置条件：L1 不处理国际标准
        assert not intent.is_international, "L1 不处理国际标准"

        candidates = self.quota.get_available_sites("L1", intent)
        # 精准筛选：标准前缀命中 且（站点无领域限制 或 领域匹配）
        matched = [
            s
            for s in candidates
            if intent.std_type in s.capabilities.supported_types
            and (not s.capabilities.industries or intent.industry in s.capabilities.industries)
        ]
        # 排序：按历史命中率降序
        matched.sort(key=lambda s: s.status.historical_hit_rate, reverse=True)
        return RouteChain(
            sites=[s.site_id for s in matched],
            decisions=[f"L1 exact match: {s.site_id} (std_type={intent.std_type})" for s in matched],
        )

    def _route_l2(self, intent: QueryIntent) -> RouteChain:
        """L2 综合兜底层：有明确标准号但 L1 未命中时，走综合站兜底。"""
        candidates = self.quota.get_available_sites("L2", intent)

        if intent.is_international:
            # 国际查询：只选覆盖国际标准的综合站
            matched = [s for s in candidates if s.capabilities.is_international]
        else:
            # 国内查询：选无领域限制的综合站（industries 应为空）
            matched = [s for s in candidates if not s.capabilities.industries]

        # 排序：按 reliability 权重降序
        matched.sort(key=lambda s: self._reliability_weight(s.capabilities.search_reliability), reverse=True)
        return RouteChain(
            sites=[s.site_id for s in matched],
            decisions=[
                f"L2 comprehensive fallback: {s.site_id} (is_international={intent.is_international})" for s in matched
            ],
        )

    def _route_l3(self, intent: QueryIntent) -> RouteChain:
        """L3 探索层：模糊关键词或前两层无结果时的最终兜底，全部标记低置信。"""
        candidates = self.quota.get_available_sites("L3", intent)
        matched = sorted(
            candidates,
            key=lambda s: self._reliability_weight(s.capabilities.search_reliability),
            reverse=True,
        )
        # L3 所有站点的 decision 必须标记 low_confidence_exploration
        return RouteChain(
            sites=[s.site_id for s in matched],
            decisions=[f"L3 low_confidence_exploration: {s.site_id} (keyword_query)" for s in matched],
        )

    @staticmethod
    def _reliability_weight(reliability: str) -> float:
        """返回 reliability 对应的排序权重，未知评级回退 0.0。"""
        return RELIABILITY_WEIGHTS.get(reliability, 0.0)


# ── 能力模型加载 ──────────────────────────────────────────


def load_capabilities(yaml_path: str) -> list[SiteCapability]:
    """从 site_capabilities.yaml 加载站点能力模型为 SiteCapability 列表。"""
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    result: list[SiteCapability] = []
    for entry in data.get("sites", []):
        classification = entry.get("classification", {})
        capabilities = entry.get("capabilities", {})
        constraints = entry.get("constraints", {})
        status = entry.get("status", {})

        result.append(
            SiteCapability(
                site_id=entry["site_id"],
                classification=Classification(
                    level1=classification.get("level1", ""),
                    level2=classification.get("level2", ""),
                ),
                capabilities=Capabilities(
                    supported_types=list(capabilities.get("supported_types", [])),
                    industries=list(capabilities.get("industries", [])),
                    is_international=bool(capabilities.get("is_international", False)),
                    search_reliability=capabilities.get("search_reliability", "unknown"),
                ),
                constraints=Constraints(batch_limit=int(constraints.get("batch_limit", 50))),
                status=Status(historical_hit_rate=float(status.get("historical_hit_rate", 0.0))),
                notes=entry.get("notes", "") or "",
            )
        )
    return result


# ── 路由服务封装（阶段三：接入查询执行链路的适配层）──


def default_capabilities_path() -> str:
    """返回 site_capabilities.yaml 的默认路径（项目根 config/ 目录）。"""
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    return str(project_root / "config" / "site_capabilities.yaml")


def is_v2_enabled() -> bool:
    """判断是否启用 v2 路由引擎（灰度开关，默认关闭，保持 v1 行为）。"""
    import os

    return os.getenv("ROUTING_ENGINE_VERSION") == "v2"


class AllRoutesExhaustedException(Exception):
    """路由链上所有站点均失败或返回空结果时抛出的聚合异常。"""


class RoutingService:
    """路由服务封装：屏蔽 v2 引擎内部复杂性，提供正交的路由与配额接口。

    供查询执行器消费：
    - get_route_chain 输入查询字符串，输出有序路由链（含 decisions 可观测性）
    - consume_quota 在发起网络请求前扣减批次配额
    """

    def __init__(self, capabilities_path: str) -> None:
        self.parser = IntentParser()
        self.capabilities = load_capabilities(capabilities_path)
        self.quota = QuotaManager(self.capabilities)
        self.engine = RouterEngine(self.capabilities, self.quota)

    def get_route_chain(self, query: str) -> RouteChain:
        """对外暴露的核心方法：输入查询，输出有序路由链。"""
        intent = self.parser.parse(query)
        return self.engine.route(intent)

    def consume_quota(self, site_id: str) -> bool:
        """供执行器在发起请求前扣减配额。"""
        return self.quota.consume(site_id)


# 全局单例 + 初始化锁：批量任务的所有 Worker 必须共享同一实例，
# 避免每个 Worker 内部重新加载 YAML 与配额状态。
_ROUTING_SERVICE_SINGLETON: RoutingService | None = None
_ROUTING_SERVICE_LOCK = threading.Lock()


def get_routing_service(capabilities_path: str | None = None) -> RoutingService:
    """返回全局单例 RoutingService（双重检查锁，线程安全惰性初始化）。"""
    global _ROUTING_SERVICE_SINGLETON
    if _ROUTING_SERVICE_SINGLETON is None:
        with _ROUTING_SERVICE_LOCK:
            if _ROUTING_SERVICE_SINGLETON is None:
                _ROUTING_SERVICE_SINGLETON = RoutingService(capabilities_path or default_capabilities_path())
    return _ROUTING_SERVICE_SINGLETON
