# 模块：项目/查询/路由/核心脚本
# 阶段3.1:路由评分器—数据驱动、配置化的适配器优先级评分
# 分隔
# 设计原则：
# 1.所有评分参数来自__合并请求（可被配置脚本覆盖）
# 2.评分器不排除——排除逻辑保留在_路由脚本/__补丁脚本硬编码层
#   3. 运行时状态（冷却/配额/批次计数）通过参数传入，评分器无副作用

from __future__ import annotations

import logging
import re
import time as _time
from dataclasses import dataclass, field
from typing import Any

from pilotstd.query.site_config import ADAPTER_DEFAULT_PROFILES

logger = logging.getLogger(__name__)

# ── 预编译正则（性能优化，避免每次调用重新编译）─────────────────

# 标准号前缀提取：匹配开头的1-4个大写字母，可选跟/或/后缀
STD_PREFIX_PATTERN = re.compile(r"^([A-Z]{1,4})(?:/T|/Z)?$")

# 行业关键词 → 正则映射（预编译）
_INDUSTRY_KEYWORD_MAP = {
    "能源": re.compile(r"能源|电力|光伏|风电|核电|新能源|NB|DL", re.IGNORECASE),
    "交通": re.compile(r"交通|运输|JT", re.IGNORECASE),
    "工业": re.compile(r"工业|信息化|YD|SJ", re.IGNORECASE),
    "环保": re.compile(r"环保|生态|HJ", re.IGNORECASE),
    "食品": re.compile(r"食品|安全|添加剂", re.IGNORECASE),
    "计量": re.compile(r"计量|JJG|JJF", re.IGNORECASE),
    "铁路": re.compile(r"铁路|TB", re.IGNORECASE),
    "自然资源": re.compile(r"自然资源|土地|矿产|DZ|TD", re.IGNORECASE),
    "文物": re.compile(r"文物|保护|WW", re.IGNORECASE),
    "工程建设": re.compile(r"工程建设|CECS", re.IGNORECASE),
}


# ── 数据结构 ──────────────────────────────────────────────────


@dataclass
class ScoreResult:
    """单个适配器的评分结果。"""

    score: int
    reasons: list[str] = field(default_factory=list)


# ── 关键词提取 ────────────────────────────────────────────────


def extract_keywords(query: str) -> list[str]:
    """从查询词中提取关键词：标准号前缀 + 行业关键词匹配。

    返回去重后的关键词列表。
    """
    keywords: list[str] = []

    # 1. 标准号前缀提取（正则匹配大写字母开头，去除非字母前缀）
    q = query.strip().upper()
    for part in q.split():
        m = STD_PREFIX_PATTERN.match(part)
        if m:
            keywords.append(m.group(1))
            break  # 只取第一个匹配的标准号前缀

    # 2. 行业关键词匹配
    text = query.upper()
    for industry, pattern in _INDUSTRY_KEYWORD_MAP.items():
        if pattern.search(text):
            keywords.append(industry)

    return list(set(keywords))  # 去重


# ── 画像读取 ──────────────────────────────────────────────────


def get_profile(adapter_name: str) -> dict:
    """获取适配器画像：默认值 + config.json 用户覆盖。

    用户覆盖通过 ConfigManager 读取 query.sites.{name} 下的字段，
    仅覆盖已有键（不追加新键）。
    """
    profile = ADAPTER_DEFAULT_PROFILES.get(adapter_name, {}).copy()
    if not profile:
        return {}

    # 阶段3.1:从配置脚本读取用户覆盖值
    try:
        from pilotstd.core.config.manager import ConfigManager

        cfg = ConfigManager()
        user_overrides = cfg.get(f"query.sites.{adapter_name}", {})
        if isinstance(user_overrides, dict):
            # 仅覆盖分析中已有的顶层键
            for key in profile:
                if key in user_overrides and key != "rate_limit":
                    profile[key] = user_overrides[key]
            # _子字典逐字段覆盖
            if "rate_limit" in user_overrides and isinstance(user_overrides["rate_limit"], dict):
                profile.setdefault("rate_limit", {}).update(user_overrides["rate_limit"])
    except Exception:
        logger.debug("读取站点配置覆盖失败: %s", adapter_name, exc_info=True)

    return profile


# ── 运行时日限额（来自 create_default_sites，含 config.json 覆盖）──

_SITE_LIMIT_MAP: dict[str, int] | None = None


def _get_site_limit_map() -> dict[str, int]:
    """返回 {site_name: daily_limit}，来自 create_default_sites()（含 config.json UI 覆盖）。

    模块级缓存：硬编码默认值与 UI 覆盖都在启动时确定，首次构建后缓存即可。
    """
    global _SITE_LIMIT_MAP
    if _SITE_LIMIT_MAP is None:
        from pilotstd.query.site_config import create_default_sites

        _SITE_LIMIT_MAP = {s.name: s.daily_limit for s in create_default_sites()}
    return _SITE_LIMIT_MAP


# ── 评分核心 ──────────────────────────────────────────────────


def score_adapter(
    adapter_name: str,
    query: str,
    runtime_state: dict[str, Any] | None = None,
) -> ScoreResult:
    """对单个适配器评分：基础权重 + 前缀匹配 + 行业匹配 + 通用降权 - 运行时剔除。

    Args:
        adapter_name: 适配器 site_name
        query: 查询词（标准号或关键词）
        runtime_state: 运行时状态字典，包含以下可选键：
            - daily_used: int — 今日已使用次数
            - cooldown_until: float — 冷却到期时间戳（0=未冷却）
            - current_batch_count: int — 当前批次已处理数

    Returns:
        ScoreResult: score=0 表示该适配器当前不可用
    """
    if runtime_state is None:
        runtime_state = {}

    profile = get_profile(adapter_name)
    if not profile:
        return ScoreResult(score=0, reasons=["adapter_not_found"])

    score = profile.get("default_weight", 50)
    reasons = [f"base:{score}"]

    rate_limit = profile.get("rate_limit", {})
    daily_limit = _get_site_limit_map().get(adapter_name, 800)

    # 1. 标准号前缀精确匹配：+30
    for prefix in profile.get("std_prefixes", []):
        if query.upper().startswith(prefix.upper()):
            score += 30
            reasons.append(f"prefix_match({prefix}):+30")
            break

    # 2. 关键词/行业匹配：每个匹配 +20
    keywords = extract_keywords(query)
    industries = profile.get("industries", [])
    for kw in keywords:
        if kw in industries:
            score += 20
            reasons.append(f"industry_match({kw}):+20")

    # 3. 通用适配器降权：-10
    if profile.get("is_general", False):
        score -= 10
        reasons.append("general:-10")

    # 4. 日限额耗尽 → 直接剔除
    daily_used = runtime_state.get("daily_used", 0)
    if daily_used >= daily_limit:
        return ScoreResult(score=0, reasons=["daily_limit_exhausted"])

    # 5. 冷却中 → 直接剔除
    cooldown_until = runtime_state.get("cooldown_until", 0.0)
    if cooldown_until > _time.time():
        return ScoreResult(score=0, reasons=["in_cooldown"])

    # 6. 批次已满 → 直接剔除
    batch_count = runtime_state.get("current_batch_count", 0)
    batch_limit = rate_limit.get("batch_limit", 50)
    if batch_count >= batch_limit:
        return ScoreResult(score=0, reasons=["batch_limit_hit"])

    return ScoreResult(score=max(score, 0), reasons=reasons)


# ── 优先级链构建 ──────────────────────────────────────────────


def get_priority_chain(
    query: str,
    runtime_state: dict[str, Any] | None = None,
) -> list[str]:
    """返回按评分降序的适配器名称列表（仅包含分数 > 0 的适配器）。

    注意：此函数不排除 csres —— csres 排除由 _routing.py 硬编码层处理。

    Args:
        query: 查询词
        runtime_state: 可选，{adapter_name: {daily_used, cooldown_until, ...}} 格式的聚合状态。
                       若为 None，评分器使用默认空状态（不做运行时剔除）。
    """
    if runtime_state is None:
        runtime_state = {}

    results: list[tuple[str, int, list[str]]] = []
    for name in ADAPTER_DEFAULT_PROFILES:
        # 从聚合状态中提取该适配器的单独状态
        adapter_state = runtime_state.get(name, {}) if runtime_state else {}
        result = score_adapter(name, query, adapter_state)
        if result.score > 0:
            results.append((name, result.score, result.reasons))

    results.sort(key=lambda x: x[1], reverse=True)
    chain = [item[0] for item in results]

    logger.debug("评分器链 query=%r → %s", query, "→".join(chain) if chain else "(空)")
    return chain


def _collect_runtime_state(
    rotator: Any = None,
    quota: Any = None,
) -> dict[str, Any]:
    """从 rotator/quota 收集所有适配器的运行时状态字典。

    返回 {adapter_name: {daily_used, cooldown_until, ...}, ...}
    供评分器批量调用使用。
    """
    state: dict[str, Any] = {}
    now = _time.time()

    if rotator:
        for name, site in rotator._sites.items():
            entry: dict[str, Any] = {
                "cooldown_until": site.cooldown_until if site.cooldown_until > now else 0.0,
                "current_batch_count": site.request_count,
            }
            state[name] = entry

    if quota:
        for name in list(state.keys()):
            if name in state:
                state[name]["daily_used"] = quota.get_used(name)

    return state
