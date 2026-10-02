# 事件通知模块重构设计（i18n / 模板 / 文案 / 覆盖度 / 聚合）

> 编写日期：2026-09-26
> 编写方式：**先实地侦察全部代码与门禁，再出方案**（R-004 实证优先 / P-105 先实测后交付）
> 技术栈（实测认定）：Python 3.12 + FastAPI（`docker/`）+ PyQt6 桌面（`pilotstd/ui/`）+ Vue 3 / PrimeVue（`web/`）
> 状态：**设计文档，本轮零代码改动**

---

## 〇、侦察方法与可复现证据

所有结论均可按下列命令复算，不接受"凭记忆下结论"（R-004）。

| 证据 | 采集命令 | 实测输出 |
|------|---------|---------|
| 事件/构建器/调用点/吞错 | `python scripts/audit_notification_chain.py` | 事件 35、构建器 36、调用点 47、吞错模式 3、问题总数 74、**退出码 1**（**第 13 批 L-08 修复后实测：39 / 40 / 50 / 0 / 0 / 退出码 0**） |
| 覆盖度四向交叉 | 上者 `--json` 后按 `events / builders / call_sites` 求差集 | 见 §4.1 |
| 语言包规模 | `json.load` + 递归摊平 | Python 侧 zh_CN 664 / en 660 / zh_TW 581；Web 侧三语各 860 |
| 硬编码中文 | 正则扫 `pilotstd/**/*.py` 字符串字面量 | **`notification` 包内 0 处**；全库 300 文件 3605 处 |
| 术语漂移 | 语言包内同义键比对 | 见 §3.1 |
| 关键逻辑 | 人工精读 | `aggregate_buffer.py` / `renderer.py` / `manager.py` / `_policy.py` |
| 回归基线 | `pytest tests/test_aggregate_buffer.py tests/test_notification_renderer.py tests/test_platform_notify.py -q` | **78 passed**（改动前基线，重构后须保持） |

### 0.1 五个痛点的真实缺口（本文件的存在理由）

提示词给的是通用模板，其中"现状问题"与实测**大面积不符**。若照模板作答，会产出大量与现状重复的方案。

| # | 模板假设 | 实测结论 | 缺口性质 |
|---|---------|---------|---------|
| 1 | 硬编码多、语言包混乱、无插值 | 通知链路**已零硬编码**（186 键已插值）；Web 侧三语 860 键**完全对齐**；Python 侧 zh_TW 缺 83、en 缺 4；**`t()` 无 Fallback 链** | 已解决 ~75%，缺**门禁**与**回退** |
| 2 | 纯文本拼接、无视觉层次 | **已实现** Block 结构化 + 5 渠道渲染器；但同一 `ListBlock` 三渠道三种布局、飞书表头用原始英文键 | 已解决 ~80%，缺**规范固化**与**字段名 i18n** |
| 3 | 措辞不一致、魔法字符串 | 文案已集中；但**术语漂移已真实存在**（归档/保存、失败/未命中、扫描完成歧义） | **真实痛点，ROI 最高** |
| 4 | 关键节点无通知 | **已有** `audit_notification_chain.py` + `notification_trigger_candidates.md`；但审计脚本**未接入 CI** | 工具已有，缺**接入**与**误报修正** |
| 5 | 聚合粒度粗糙 | 已有双聚合器；但 **`target_id` 全链路透传却从未参与分组**，"关联实体"维度是死代码 | **真实缺陷，改动最小** |

**核心判断**：本项目不需要"从零建设五大能力"，需要的是**①给已有能力补门禁 ②修已发现的确定性缺陷 ③把隐性约定固化成规范**。

---

## 一、任务 1：i18n 国际化改造

### 1.1 问题分析（实测）

| 编号 | 事实 | 位置 | 后果 |
|------|------|------|------|
| I-1 | `t()` 缺键时 `return key`，**无任何回退与告警** | [i18n/__init__.py:60-66](pilotstd/i18n/__init__.py#L60-L66) | 用户直接看到 `notification.scan.scan_complete.title` 这类 key |
| I-2 | zh_TW 缺 83 键、en 缺 4 键 | `pilotstd/i18n/*.json` | 繁体用户大面积回显 key；英文用户 4 处 |
| I-3 | CI 门禁 `check_i18n_key_count.py` **只扫 `web/src/locales`** | [check_i18n_key_count.py:28](scripts/check_i18n_key_count.py#L28) | Python 侧语言包**无任何门禁**，I-2 无人拦 |
| I-4 | 插值参数命名不统一：`{s}`/`{n}`/`{e}` 单字母与 `{standard_number}` 长名混用 | `zh_CN.json` 132 处命名插值 + 27 处 positional `{}` | 可读性差，占位符与参数错配无保护（`format()` 抛 `KeyError` 而非静默） |
| I-5 | 复数无语义化支持，靠 `title.success` / `title.with_failure` 手工分叉 | `_builders_batch.py:113-117` | 可接受但无规范，后续易分裂 |

**结论**：不要引入 `gettext`/`Babel`/`fluent`。理由——现有 key 体系（664 键扁平 JSON + `t()` 调用 1328 处）已深度嵌入，换库等于全量重写，且个人项目无需 PO 文件编译链。**渐进式增强 `t()` 即可**。

### 1.2 方案设计

#### A. 语言包组织：确认现状为规范（不重组）

现有 `notification.{category}.{event}.{field}` 三级结构（二级分布：validity 32 / system 27 / common 23 / archive 21 / announce 17 / download 10 / aggregated 9 …）**就是"按模块 + 按字段角色"的混合结构，已是正解**。理由：

- 按**模块**（validity/archive/announce）切分 → 定位时按业务域找，符合"改哪个功能看哪个文件"；
- 按**字段角色**（`.title` / `.body` / `.body.stats`）收尾 → 同一事件的标题、正文、明细天然聚拢；
- 顶层 `notification.` 隔离 → 与 UI 历史扁平键（`btn_ok` 等）物理分开，可独立门禁。

**唯一建议的规范补充**：新增 key 必须写全三级（`notification.<category>.<event>.<field>`），禁止再往顶层加扁平键。理由：顶层现有 664 键里约 478 个是历史扁平键，继续增长会让"通知文案"边界模糊。

#### B. 插值最佳实践：命名插值 + 参数即数据

```python
# ✅ 推荐：key 用长名占位符，调用点用关键字传参（自文档化 + 参数名错配立即报错）
t("notification.download.download_complete.body.file_path", p=file_path)

# ✅ 数量类：count 是保留名，决定单复数与量词
t("notification.validity.standard_first_registered.body.count", n=3)

# ❌ 禁止新增：positional 占位符（现有 27 处存量不动，逐步偿还）
"notification.renderer.list_count": "（共 {} 条）"
```

#### C. Fallback 机制（I-1 修复）

**回退链**：`当前语言 → en → zh_CN → key 本身`。最后一级保留 key 是为了"fail-loud"（现有测试依赖此行为捕获缺键，见 [test_template_i18n_runtime.py](tests/unit/core/notification/test_template_i18n_runtime.py)），但必须**同时告警**，否则查不出问题（这正是 `docs/reference/i18n-troubleshooting-sop.md` 记载的线上事故形态）。

```python
# pilotstd/i18n/__init__.py —— 增强 t()，保持 _(key) 与 _current 语义不变（最小改动）
import logging
import threading

logger = logging.getLogger(__name__)

_FALLBACK_CHAIN = ("en", "zh_CN")
_missing: set[str] = set()
_missing_lock = threading.Lock()


def t(key: str, **kwargs: object) -> str:
    """翻译 + 插值 + 回退链（fail-loud）。

    回退顺序：当前语言 → en → zh_CN → key 本身。
    缺键记录到 _missing 并 WARNING（同一 key 只报一次，避免刷日志）。
    """
    _ensure_loaded()
    template = _current.get(key)
    if template is None:
        for lang in _FALLBACK_CHAIN:
            if lang == _lang:
                continue
            candidate = _translations.get(lang, {}).get(key)
            if candidate is not None:
                template = candidate
                _report_missing(key, resolved_by=lang)
                break
    if template is None:
        _report_missing(key, resolved_by=None)
        return key
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        # 占位符与参数错配：宁可返回原文，也不让通知链路抛异常中断
        logger.error("i18n 占位符错配: key=%s kwargs=%s template=%r", key, sorted(kwargs), template)
        return template


def _report_missing(key: str, *, resolved_by: str | None) -> None:
    """缺键上报：WARNING 一次 + 聚合到 _missing 供 CI 拉取。

    resolved_by=None 表示四级全缺（真正缺失）；否则表示当前语言缺、回退命中。
    """
    with _missing_lock:
        if key in _missing:
            return
        _missing.add(key)
    if resolved_by:
        logger.warning("i18n 键在当前语言缺失，已回退 %s: %s", resolved_by, key)
    else:
        logger.error("i18n 键四级全缺: %s", key)


def missing_keys() -> frozenset[str]:
    """导出运行期缺键集合（供测试/CI 断言，如 e2e 跑完末尾检查）。"""
    return frozenset(_missing)
```

**注意**：`_()`（[第 55 行](pilotstd/i18n/__init__.py#L55)）是 UI 侧旧入口，**本轮不动**——它没有插值需求，改动只会扩大回归面（R-002 精准修改）。

#### D. 复数处理（I-5，轻量语义化）

不引入 ICU。约定 `count` 为保留参数名，按英文复数规则分叉：

```json
{
  "notification.download.batch_download_complete.body.stats.one": "成功：{success}，失败：{failed}，跳过：{skipped}",
  "notification.download.batch_download_complete.body.stats.other": "成功：{success}，失败：{failed}，跳过：{skipped}"
}
```

```python
def t_plural(key_base: str, count: int, **kwargs: object) -> str:
    """按 count 选择 .one / .other 变体；无变体时回退 key_base 本身。

    zh_CN/zh_TW 无复数变化，两个变体填相同文案即可（翻译成本为零）。
    """
    suffix = ".one" if count == 1 else ".other"
    return t(f"{key_base}{suffix}", **kwargs) if _has_key(f"{key_base}{suffix}") else t(key_base, **kwargs)
```

**落地判据**：只有当某条文案在中/英下**句式必须不同**时才拆 `one`/`other`；纯数字替换（如"共 {n} 条"）**不要拆**——避免为不存在的问题付维护成本（R-008 简洁至上）。

### 1.3 配置/门禁示例（补 I-2、I-3）

新增 `scripts/check_i18n_python_keys.py`（对齐既有 `check_i18n_key_count.py` 的风格与退出码约定）：

```python
#!/usr/bin/env python3
"""Python 侧语言包键完整性门禁（G-041）。

背景：check_i18n_key_count.py 只扫 web/src/locales，Python 侧
pilotstd/i18n/*.json 长期无门禁，实测 zh_TW 缺 83 键、en 缺 4 键无人拦。
判定：以 zh_CN.json 为唯一数据源（SSOT），要求 zh_TW/en 键集合与之完全一致。
用法：python scripts/check_i18n_python_keys.py [--fix-report]
退出码：0 = 三语键集合一致；1 = 存在缺失或多余键。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "pilotstd" / "i18n"
SSOT = "zh_CN"  # 唯一数据源：新增 key 必须先落 zh_CN
LANGS = ("zh_CN", "zh_TW", "en")


def load(lang: str) -> dict[str, str]:
    return json.loads((BASE / f"{lang}.json").read_text(encoding="utf-8"))


def main() -> int:
    packs = {lang: load(lang) for lang in LANGS}
    ssot = set(packs[SSOT])
    failed = False
    for lang in LANGS:
        if lang == SSOT:
            continue
        missing = sorted(ssot - set(packs[lang]))
        extra = sorted(set(packs[lang]) - ssot)
        if missing:
            failed = True
            print(f"::error::{lang}.json 缺 {len(missing)} 键（相对 {SSOT}）")
            for k in missing[:20]:
                print(f"  缺: {k}")
            if len(missing) > 20:
                print(f"  ... 另有 {len(missing) - 20} 键")
        if extra:
            failed = True
            print(f"::error::{lang}.json 多 {len(extra)} 键（{SSOT} 无对应，疑似已删文案残留）")
            for k in extra[:20]:
                print(f"  多: {k}")
    if not failed:
        print(f"OK: 三语键集合一致（{len(ssot)} 键）")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

> **首次接入前置动作**：先补齐 zh_TW 的 83 键与 en 的 4 键，否则门禁一上线即红。补齐缺键清单可由
> `python -c "import json,pathlib; ..."`（§1.1 统计脚本）直接导出。

CI 接入位置（追加到既有 i18n 门禁之后）：

```yaml
# .github/workflows/ci.yml，紧随 G-040 硬编码检查
      - name: G-041 — Python 语言包三语键完整性
        run: python scripts/check_i18n_python_keys.py
```

### 1.4 注意事项

1. **`format()` 的错误处理是新增行为**：现有 `t()` 不回退也不捕获，改成"捕获并返回原文"后，原本会崩的路径变成静默降级。**必须靠 §1.3 的门禁 + 单测覆盖"占位符错配"**，否则等于把异常藏起来（违反 P-104 门禁不绕过精神）。
2. **两套语言包不做收敛**（本轮决策）：Python 664 键 vs Web 860 键，交集仅 `notification.*` 的 120 键，且**用途不同**——Python 侧产出通知正文（服务端渲染），Web 侧渲染 UI 标签。硬收敛需要人工建立 540 个键的映射表，收益与风险不成比例。**改为约定：`notification.*` 命名空间两侧语义一致，UI 标签各自维护。**
3. **`set_language` 的进程内全局性**：`_lang`/`_current` 是模块级全局，多线程下切换语言会影响并发请求。现状已如此（既有测试靠 `conftest` 的 `_restore_i18n_language` 兜底），**本轮不修**——修复需改为 contextvars 或显式传 lang，属独立技术债，建议单独排工单（P-107 预存问题告知但不越界修）。

---

## 二、任务 2：通知模板显示效果优化

### 2.1 问题分析（实测）

架构**已经是对的**：`NotificationMessage.blocks`（结构化）→ `BlockRenderer` 子类（渠道适配）→ 渠道发送。不存在"纯文本拼接"问题。真实缺陷是**渠道间的渲染口径不一致**与**字段名未本地化**。

| 编号 | 缺陷 | 位置 | 实测表现 |
|------|------|------|---------|
| T-1 | **飞书表格表头取 dict 原始键**，不做 i18n | [renderer.py:339-340](pilotstd/core/notification/renderer.py#L339-L340) | 表头显示英文 `number` / `name`，而 `ListBlock.items` 的键正是 `{"number":…, "name":…}`（[_builders_batch.py:142](pilotstd/core/notification/_builders_batch.py#L142)） |
| T-2 | **同一 `ListBlock` 三渠道三种布局** | `renderer.py` 各子类 `_render_list` | Telegram：`• **GB/T 1** \| 标准名`（丢弃键名）；Markdown：`- number: GB/T 1 \| name: 标准名`（保留英文键）；Desktop：`number：GB/T 1`（中文冒号 + 英文键） |
| T-3 | `MarkdownRenderer` **不转义**，`FeishuCardRenderer` 状态变更换行符不一致 | [renderer.py:215-255](pilotstd/core/notification/renderer.py#L215-L255) vs [312-316](pilotstd/core/notification/renderer.py#L312-L316) | 标准名称含 `*` `_` 会破坏钉钉/企微 Markdown 排版；飞书状态块用 `\n`、Markdown 用 `\n\n` |
| T-4 | 标题层级无统一口径 | `_render_title` 各子类 | Markdown `## {title}`、Telegram `*{title}*`、Desktop 裸标题、飞书走 header |
| T-5 | Telegram 列表**整条渲染后**加粗 number，转义边界脆弱 | [renderer.py:171-180](pilotstd/core/notification/renderer.py#L171-L180) | `_escape` 后再拼 `*…*`，若 value 含 `*` 会产生未配对标记 |

### 2.2 方案设计

#### A. 模板引擎：**不引入**（明确否决）

理由（可执行判据，非泛泛而谈）：

- 现有 Block 模型的表达能力已覆盖全部 36 个构建器的需求：文本 / 键值 / 状态变更 / 列表，**没有一个构建器需要循环、条件嵌套或模板继承**；
- 引入 Jinja2/Handlebars 需要把 36 个纯函数构建器改写为模板文件，**同时失去**：类型检查（`mypy`）、单测直接断言 Block 结构（[test_message_builders_snapshot.py](tests/unit/core/notification/test_message_builders_snapshot.py) 748 行已覆盖全部构建器）、`_build_*_message(data: dict)` 的可测签名；
- 个人项目，**表达式能力是负债不是资产**：模板里的逻辑无法被 `ruff`/`mypy` 约束。

**结论：Block 模型即模板引擎**。要增强就增强 Block 类型（如新增 `ActionBlock`），而不是引入外部 DSL。

#### B. 基础通知 UI 规范（T-1/T-4 固化）

统一"标题—摘要—明细—操作"四层，各渠道按能力降级：

| 层 | 语义 | Block 类型 | 副标题/说明 |
|----|------|-----------|------------|
| L1 标题 | 一句话说清**发生了什么**（含结果态） | `NotificationMessage.title` | ≤ 20 字；失败类前缀 `[失败]`/`[警告]` 由 `level` 驱动，不写进文案 |
| L2 摘要 | **总量 + 关键数字**，决定用户是否要展开 | `TextBlock`（第一条） | 必须包含全部计数字段，如"成功：8，失败：2，跳过：1" |
| L3 明细 | 可执行信息（哪条失败了、路径、标准号） | `ListBlock` / `KeyValueBlock` | 上限 5 条 + "等 N 条"；**超限必须给 `detail_url`** |
| L4 操作 | 跳转入口 | `ListBlock.detail_url` | 飞书渲染为按钮，Markdown 渲染为链接，Telegram/Desktop 渲染为裸 URL |

**时间戳规范**：只在"状态变更"类事件出现（`StatusChangeBlock`），统一 `YYYY-MM-DD`（现有 `notification.common.changed_at` 已符合）；聚合消息的 `changed_at` 用 `notification.aggregated.status.time_suffix` 收尾。**禁止**把相对时间（"3 分钟前"）写进模板——服务端渲染与用户阅读时刻不一致。

#### C. 渠道能力矩阵与降级契约（T-2/T-4 固化）

| 能力 | 微信 | 钉钉 | 飞书 | Telegram | 桌面 | Web | 邮件 |
|------|------|------|------|---------|------|-----|------|
| 加粗 | ✅ `**` | ✅ `**` | ✅ | ✅ `*` | ❌ | ✅ | ✅ |
| 标题层级 | `##` | `##` | header | `*…*` | 裸文本 | 原生 | 原生 |
| 表格 | ❌→列表 | ❌→列表 | ✅ 原生 table | ❌→列表 | ❌ | 原生 | ❌→列表 |
| 按钮 | ❌→链接 | ❌→链接 | ✅ action | ❌→裸 URL | ❌ | 原生 | ✅ 超链接 |
| 空值 | `(无数据)` | 同 | 同 | 同 | 同 | 同 | 同 |

**降级契约**：`detail_url` 在"无按钮能力"的渠道**必须**渲染为可点击 URL（现状 Telegram 渲染裸 URL ✅、Desktop 渲染裸 URL ✅ 符合契约）；`ListBlock` 在无表格能力的渠道渲染为 `- 条目` 列表（现状 ✅）。

#### D. 修复 T-1：表头本地化（改动最小、收益立现）

`ListBlock` 的 `items` 键是**数据字段名**，不应直接当展示文字。两种方案，推荐 **D-1**：

**D-1（推荐，零 API 变更）**：渲染器查表把字段名映射为展示名。

```python
# pilotstd/core/notification/renderer.py —— 新增模块级映射 + FeishuCardRenderer 表头本地化
# 字段名 → i18n 键（渲染期取 t()，禁止模块级求值，否则语言固化在 import 时刻）
_LIST_FIELD_KEYS = {
    "number": "notification.renderer.field.number",
    "name": "notification.renderer.field.name",
    "status": "notification.renderer.field.status",
    "detail": "notification.renderer.field.detail",
    "path": "notification.renderer.field.path",
    "reason": "notification.renderer.field.reason",
}


def _field_label(key: str) -> str:
    """把 ListBlock.items 的数据字段名翻译为展示名；未登记字段原样返回（不抛错）。"""
    i18n_key = _LIST_FIELD_KEYS.get(key)
    if not i18n_key:
        return key
    # t() 缺键回退返回 key 本身，此时展示原始字段名，不阻塞渲染
    return t(i18n_key)
```

对应语言包新增（zh_CN / zh_TW / en 三语同步）：

```json
{
  "notification.renderer.field.number": "标准号",
  "notification.renderer.field.name": "名称",
  "notification.renderer.field.status": "状态",
  "notification.renderer.field.detail": "详情",
  "notification.renderer.field.path": "文件",
  "notification.renderer.field.reason": "原因"
}
```

**D-2（不推荐）**：给 `ListBlock` 加 `field_labels: dict[str,str]`，由构建器传入。理由：36 个构建器都要改，且展示名应由渲染层决定（构建器注入展示名会让"数据"与"呈现"重新耦合，正是本项目已解决的旧问题）。

#### E. 模板继承/复用策略（"同一事件、不同渠道"）

**现状即是正解，固化为约定**：复用**不在模板层而在 Block 层**。

```
事件 → 1 个构建器（产出 blocks）→ N 个渲染器（渠道适配）
```

- **共享**：文案（i18n key）、结构（blocks）、语义（level / event_type / link）；
- **各渠道独立**：格式标记、转义、长度截断、交互元素。

**明确禁止**：为某渠道单独写一套构建器（如 `_build_xxx_for_telegram`）。若某渠道需要**额外信息**（如桌面要更短），在 `BlockRenderer` 子类里做降级（现状 `DesktopRenderer._render_list` 只取首条首字段做预览 ✅ 符合约定），**不改数据层**。

### 2.3 注意事项

1. **Telegram 转义边界（T-5）是已知脆弱点**：`_escape` 只应作用于用户数据，绝不能作用于已加格式标记的字符串。现状注释已声明该约定（[renderer.py:193](pilotstd/core/notification/renderer.py#L193)）但无测试保护。**建议补一个测试**：构造 `name = "A*B_C"`，断言渲染结果中 `*` 被转义为 `\*` 且加粗标记配对。
2. **不要给 `MarkdownRenderer` 加转义**：钉钉/企微的 Markdown 不支持反斜杠转义，加转义会**显示**出反斜杠（比排版错乱更糟）。若需防注入，正确做法是**在构建器里剥离** Markdown 控制字符，而非渲染器转义——但这属于新需求，本轮不做。
3. **UI 规范落地位置**：建议写入 `docs/reference/ui-components.md`（AGENTS.md 8.1 已登记"涉及前端 UI 组件"必读该文档），避免新建第 211 个 md 文件。

---

## 三、任务 3：通知用语统一性治理

### 3.1 问题分析（实测：术语漂移已真实存在）

| 编号 | 漂移 | 位置 | 实测证据 |
|------|------|------|---------|
| C-1 | **同一动作三个词**：`归档` / `保存` / `已归档` | `notification.archive.archive_complete.body.count` = "已归档：{n} 个文件" vs 扁平键 `save_results_success` = "保存成功: {} 个"；`toolbar_save` = "归档" | 通知正文说"已归档"，工具栏按钮说"归档"，结果弹窗说"保存成功" |
| C-2 | **失败语义三分**：`失败` / `无法识别` / `未命中` | `scan_complete.body.stats` = "…失败：{f} 个"；`msg_scan_complete` = "…{failed} 个无法识别"；`query_empty.body` = "全部未命中" | 同一批文件，扫描完成通知说"失败"，桌面状态栏说"无法识别" |
| C-3 | **标题歧义**：`scan_complete` 与 `scan_empty` 标题**完全相同** | `notification.scan.scan_complete.title` = "扫描完成"、`notification.scan.scan_empty.title` = "扫描完成" | 用户只能从正文区分"扫到 30 个"还是"没发现新文件" |
| C-4 | 单字母占位符 `{s}`/`{n}`/`{e}` 与 `{t}`（total 还是 time？） | `notification.announce.announcement_check_complete.body.summary` = "公告总数：{t}，国标：{g}…" | `{t}` 在 `standard_first_registered.body.item` 语义不同，可读性差 |
| C-5 | 文案散落在语言包但**无使用约束** | `pilotstd/constants/` 仅 2 文件（`announce_types.py`/`group_std_orgs.py`），无术语表 | 新文案靠"看邻居"，漂移必然复发 |

### 3.2 方案设计

#### A. 《通知文案风格指南》（可直接入库为 `docs/reference/notification-copywriting.md`）

**一、语态与时态**

| 规则 | 说明 | 示例 |
|------|------|------|
| 用**完成态陈述**，不用进行时 | 通知在动作结束后发出 | ✅"扫描完成：30 个文件" ❌"正在扫描" |
| 用**主动语态**，省略主语（默认"系统"） | 主语永远是系统 | ✅"已归档 3 个文件" ❌"文件被系统归档了" |
| 结果态写在**标题**，过程数据写在**正文** | 标题决定是否展开 | ✅ 标题"扫描完成（2 个失败）" |
| **禁止第二人称** | 不假设用户视角 | ❌"你提交的任务失败了" |

**二、术语表（唯一口径）**

| 概念 | 标准用词 | 禁用词 | 理由 |
|------|---------|--------|------|
| 文件进入标准库的动作 | **归档** | 保存、入库、收纳 | `toolbar_save` 已用"归档"，以工具栏为准 |
| 归档完成的通知标题 | **归档完成** | 保存完成、已归档 | 与 `toolbar_save` 一致 |
| 文件名无法匹配标准 | **无法识别** | 失败、未命中、解析失败 | "失败"隐含系统错误，语义不符 |
| 站点查询无结果 | **未查询到** | 未命中、失败、查无 | |
| 标准状态变为失效 | **已废止** | 已作废、失效、过期 | 与 `notification.common.abolished` 一致 |
| 网络/接口异常 | **失败** | 错误、异常、出错 | 保留给真实错误 |
| 任务被中断 | **已取消** | 已终止、已停止 | |
| 时间点 | **YYYY-MM-DD** | 相对时间 | 服务端渲染 ≠ 用户阅读时刻 |

**三、标点与格式**

- 中文用全角：`：` `，` `（）`；英文用半角。**同一字符串内不混用**；
- 计数统一"`N 条` / `N 个文件` / `N 项`"，不写"N 个标准"（标准用"条"）；
- 列表项前缀统一 `•`（现状 `notification.announce.announcement_fetch_complete.body.item` = "• {t}" ✅）；
- 冒号仅在键值对使用，正文句中**不用**冒号引导列表；
- **禁止 emoji 出现在错误类通知**（现状 `notification.aggregated.body.header` = "📦 聚合通知（{n} 条）"、`validity_system_failed.body.hint` = "💡 …" 混用，错误类应去 emoji）。

**四、被禁用的表达**

- 技术黑话：`payload`、`endpoint`、`null`、`None`、`stack trace`（应说"详细错误已记录至系统日志"——现状 `validity_system_failed.body.hint` 已是正解 ✅）；
- 裸异常：`str(e)` 直出（现状 `test_message_builders_snapshot.py:230` 已记录该修复：不再直出 raw 异常 ✅）；
- 空泛词：`操作`、`处理`、`异常发生`；
- 客套话：`亲`、`请您`、`麻烦`。

#### B. 文案注册中心（杜绝魔法字符串）

**现状已解决 90%**：所有通知文案都在 `pilotstd/i18n/*.json`，`notification` 包内**零硬编码中文**（实测）。所以**不需要**新建 `constants/copy.py` 常量类——那会造成"文案两处定义"（JSON + Python 常量）的新漂移源。

真正缺的是**三层约束**：

**第 1 层：key 命名门禁**（新增，可扩展 `check_i18n_python_keys.py`）

```python
# 追加到 scripts/check_i18n_python_keys.py
import re

NOTIFICATION_KEY_RE = re.compile(
    r"^notification\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$"
)
# 允许的二级分类（与现有 16 个分类一致，新增需显式登记）
ALLOWED_CATEGORIES = frozenset({
    "validity", "system", "common", "archive", "announce", "download",
    "aggregated", "channel_test", "scan", "query", "channel", "renderer",
    "desktop", "api", "manager", "fallback",
})


def check_key_naming(packs: dict[str, dict[str, str]]) -> bool:
    """校验 notification.* 键的命名规范：三级以上 + 二级分类在白名单内。"""
    ok = True
    for key in packs[SSOT]:
        if not key.startswith("notification."):
            continue
        if not NOTIFICATION_KEY_RE.match(key):
            print(f"::error:: 键命名不合规（需 notification.<category>.<event>.<field>）: {key}")
            ok = False
            continue
        category = key.split(".")[1]
        if category not in ALLOWED_CATEGORIES:
            print(f"::error:: 未登记的二级分类 '{category}': {key}")
            ok = False
    return ok
```

**第 2 层：占位符一致性检查**（新增，防 `{s}` 与 `{standard_number}` 混用）

```python
def check_placeholder_consistency(packs: dict[str, dict[str, str]]) -> bool:
    """同一 key 在三语中的占位符集合必须完全一致。

    否则 zh_CN 用 {n} 而 en 用 {count} → 英文用户看到 KeyError 降级原文。
    """
    import re as _re
    ph = _re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
    ok = True
    for key in packs[SSOT]:
        base = set(ph.findall(packs[SSOT][key]))
        for lang in LANGS:
            if lang == SSOT:
                continue
            cur = set(ph.findall(packs[lang].get(key, "")))
            if cur != base:
                print(f"::error:: {lang}.json 占位符与 {SSOT} 不一致: {key} "
                      f"({SSOT}={sorted(base)} vs {lang}={sorted(cur)})")
                ok = False
    return ok
```

**第 3 层：禁用词扫描**（新增，把 §3.2 A 的术语表变成可执行检查）

```python
# scripts/check_copywriting.py（新增门禁 G-042）
"""通知文案风格门禁：扫描 language pack 的 notification.* 值，命中禁用词即失败。

只查 notification.* —— UI 历史文案（664 键中的扁平键）存量不清理，避免一次性
把门禁变成"永远红"（与 check_i18n_hardcoded.py 的基线策略同源）。
"""
BANNED = {
    "保存完成": "改用「归档完成」（遵循 toolbar_save 口径）",
    "已作废": "改用「已废止」（遵循 notification.common.abolished）",
    "未命中": "改用「未查询到」",
    "解析失败": "改用「无法识别」（文件名场景）",
    "payload": "技术黑话，改为业务语言",
    "stack trace": "改用「详细错误已记录至系统日志」",
}
```

**落地顺序（关键）**：先按术语表**修正存量**，再开门禁；否则门禁一上线即红。存量修正范围可控——`notification.*` 仅 186 键。

#### C. 典型事件 Before / After

**C-1 归档完成（消除"归档/保存"漂移）**

| | 现在 | 建议 |
|---|------|------|
| 标题 | `notification.archive.archive_complete.title` = "归档完成" | **不变** ✅ |
| 正文 | `body.count` = "已归档：{n} 个文件" | "已归档 **{n} 个文件**"—统一量词与加粗 |
| 结果弹窗 | `save_results_success` = "保存成功: {} 个" | **"归档成功：{n} 个文件"** ← 修正漂移 |
| 工具栏 | `toolbar_save` = "归档" | **不变**（作为术语基准） |

**C-2 扫描完成（消除"失败/无法识别"+ 标题歧义）**

| | 现在 | 建议 |
|---|------|------|
| 标题（有文件） | `scan_complete.title` = "扫描完成" | **"扫描完成（{failed} 个无法识别）"**（失败数写进标题，用户不展开即知） |
| 标题（无文件） | `scan_empty.title` = "扫描完成" | **"扫描完成，无新增文件"** ← 消除 C-3 歧义 |
| 正文 | `scan_complete.body.stats` = "已扫描：{t} 个文件，成功：{s} 个，失败：{f} 个" | "共扫描 {t} 个文件：识别成功 {s} 个，**无法识别 {f} 个**" |
| 明细头 | `scan_complete.body.failed_header` = "失败文件：" | **"无法识别的文件："** |
| 桌面状态栏 | `msg_scan_complete` = "扫描完成：{success} 个识别成功，{failed} 个无法识别" | **以此为准**（已经是正确口径） |

**C-3 站点查询无结果（消除"未命中"）**

| | 现在 | 建议 |
|---|------|------|
| 标题 | `query_empty.title` = "查询完成" | "查询完成" ✅ |
| 正文 | `query_empty.body` = "共 {total} 条标准，全部未命中" | **"共 {total} 条标准，均未查询到结果"** |
| 查询分类 | `query_cat_not_found` = "未查询到" | **不变**（作为术语基准） |

**C-4 自动备份失败（消除技术黑话与裸异常）**

| | 现在 | 建议 |
|---|------|------|
| 标题 | `auto_backup.title.failed` = "自动备份失败" | 不变 ✅ |
| 正文 | `auto_backup.body.error` = "备份失败：{err}" | **"备份失败：{err}"** → 但 `{err}` 必须是**已翻译的错误分类**，不是 `str(e)`（现状由 `notification.common.error.*` 的 6 个分类键提供，✅ 已是正解） |

**C-5 有效性系统级失败（emoji 与语气）**

| | 现在 | 建议 |
|---|------|------|
| 标题 | `validity_system_failed.title` = "有效性检查系统级失败" | "有效性检查失败（系统级）"—括号补充比连写更易读 |
| 正文 | `body.hint` = "💡 详细错误堆栈已记录至系统日志，请联系管理员查看。" | **"详细错误已记录至系统日志。"** ← 错误类去 emoji；个人项目无"管理员"，删去该词 |

### 3.3 注意事项

1. **不要新增 Python 常量层**（重申）：文案唯一数据源是 JSON，常量类会制造第二份真相。
2. **术语表要能被机器检查**：§3.2 C 的 `BANNED` 字典就是术语表的可执行形态。**只写进文档的规范一定会腐化**——这是本项目 `check_i18n_hardcoded.py` 基线策略已经验证过的经验。
3. **改动文案会影响快照测试**：[test_message_builders_snapshot.py](tests/unit/core/notification/test_message_builders_snapshot.py) 有 **约 14 处硬编码中文断言**（如 154 行 `"检查总数：100"`、259 行 `"已归档：3 个文件"`、262 行 `"国标：2 条，化工：1 条"`）。改文案必须同步改断言，**且这些断言本身也违反 i18n 原则**（在 en 语言下会失败）。这部分重构风险真实存在，建议**单独一个 commit**，便于回溯。

---

## 四、任务 4：事件通知覆盖度补全

### 4.1 问题分析（实测四向交叉）

用 `audit_notification_chain.py --json` 的 `events` / `builders` / `call_sites` 求差集：

| 检查方向 | 结果 | 解读 |
|---------|------|------|
| 有定义、**无专用构建器** | **0 个** | ✅ `event → builder` 100% 覆盖 |
| 有定义、**无任何调用点** | 1 个：`archive_complete` | ⚠️ **误报**——调用点写的是常量 `EVENT_ARCHIVE_COMPLETE`（[_organize.py:219](pilotstd/manager/facade/_organize.py#L219)），审计脚本未解析常量 |
| 有调用点、**未在 events.py 定义** | 2 个：`desktop_toast`、`<const:EVENT_ARCHIVE_COMPLETE>` | 🔴 `desktop_toast` 是**真实缺口**：`notification_aggregator.py:226` 的桌面路径发的事件不在 SSOT 内 |
| 有构建器、无事件定义 | 1 个 `_build_fallback_message` | ✅ 设计如此（兜底构建器） |

**审计工具自身的可信度问题**（必须先修，否则门禁无法上线）：

| 编号 | 误报 | 位置 | 根因 |
|------|------|------|------|
| A-1 | **72 个 `empty_text_risk`（P1）全是误报** | 审计报告 74 个问题中的 72 个 | 判定逻辑要求构建器填充 `body` 字段，但 [channel.py:22-23](pilotstd/core/notification/channel.py#L22-L23) 明确 `body` 是"向后兼容：blocks 为空时回退渲染"，**载荷是 `blocks`**。36 个构建器全部产出 blocks，`body` 留空是**正确设计** |
| A-2 | `missing_null_guard`（P2）判定过粗 | 36 个构建器全部告警 | 用 `data.get("x", 0)` 提供默认值即视为"无守卫"，但**取默认值本身就是 null 处理**。应为"既无默认值又无 `if not` 检查"才算问题 |
| A-3 | 常量引用未解析 | `_organize.py:219` | AST 扫描只认字符串字面量 |

### 4.2 方案设计

#### A. 事件覆盖度自查清单（模板）

**按用户生命周期 / 资源 CRUD / 权限 / 异常 / 定时任务五维度**，每个维度给出"当前状态"实测：

| 维度 | 检查项 | 当前事件 | 状态 |
|------|--------|---------|------|
| **用户生命周期** | 登录（新设备/IP） | — | 🔴 **缺失** |
| | 登录失败（连续 N 次） | — | 🔴 **缺失**（安全相关，高优先） |
| | 用户创建/删除 | — | 🔴 **缺失**（多用户已支持，见 `notification_policy.user_id`） |
| | 偏好/密码变更 | — | 🔴 **缺失** |
| **资源 CRUD** | 标准创建（首次登记） | `standard_first_registered` ✅ | ✅ |
| | 标准状态变更 | `standard_status_changed` ✅ | ✅ |
| | 收藏创建 | `favorite_created` ✅ | ✅ |
| | **收藏删除** | — | 🔴 **缺失** |
| | 配置文件导入/导出 | — | 🟡 中优先 |
| | 数据库清理（`notification_cleanup`） | — | 🟡 中优先（删了多少条无感知） |
| **权限变更** | 角色变更 | — | 🔴 **缺失**（有 `require_role` 但无审计通知） |
| | 凭证更新（webhook/token） | — | 🔴 **缺失**（安全相关） |
| | 可信 IP 变更 | `trust_ip_update` ✅ | ✅ |
| **系统异常** | 定时任务失败 | `task_execution_failed` ✅ | ✅ |
| | 后台线程异常 | `worker_error` ✅ | ✅ |
| | 下载失败 | `download_failed` ✅ | ✅ |
| | **适配器连续失败熔断** | — | 🟡 中优先（`quota_exhausted` 只覆盖配额） |
| | **磁盘空间不足** | — | 🟡 中优先（备份失败会暴露，但滞后） |
| **定时任务** | 自动备份 | `auto_backup` ✅ | ✅（成功+失败双分支） |
| | 公告抓取 | `announcement_fetch_complete` / `announcement_fetch_failed` / `announce_fetch_summary` ✅ | ✅ |
| | 自动扫描 | `auto_scan_failed` ✅（仅失败） | ✅ 符合"日常归档不必通知" |
| | 日期提醒 | `date_reminder` ✅ | ✅ |
| | 有效性检查 | `validity_batch_report` / `validity_round_summary` / `validity_standard_failed` / `validity_system_failed` ✅ | ✅ |
| | 静音补发 | `release_suppressed`（无通知，仅日志） | 🟡 补发本身无需通知 |
| **聚合/链路自检** | 桌面 toast | `desktop_toast`（**不在 SSOT**） | 🔴 **需登记** |

**基于通用 SaaS/工具类项目经验推断的"最可能被遗漏"高优先级事件**（结合本项目实测，按优先级）：

| 优先级 | 事件 | 理由 | 触发点 |
|--------|------|------|--------|
| **P0** | `auth_login_failed` | 安全事件。多次失败是入侵信号，用户必须知道 | `docker/api/login` |
| **P0** | `credential_changed` | webhook URL / token / 密码被改写。若被恶意替换，通知会流向攻击者——**变更本身必须通知到旧渠道** | `docker/api/notification.py` PUT |
| **P1** | `favorite_deleted` | 有创建无删除，用户会怀疑"我删的收藏怎么还在下载队列" | `docker/api/favorites.py` DELETE |
| **P1** | `role_changed` | 权限变更静默，多用户场景下是审计盲区 | `require_role` 相关接口 |
| **P2** | `disk_space_low` | 备份/下载失败的根因，提前告警优于事后失败 | 备份任务前置检查 |
| **P2** | `adapter_circuit_broken` | 适配器连续失败后熔断，用户需知"这个站点暂时不可用" | `daily_quota` / 适配器重试层 |
| **P2** | `desktop_toast`（登记进 SSOT） | 消除"有调用点无定义" | `notification_aggregator.py:226` |

#### B. 代码层面自动发现未接入通知的业务方法

**推荐方案：AST 静态扫描 + 白名单基线**（与 `audit_notification_chain.py`、`check_i18n_hardcoded.py` 的既有治理模式一致）。理由：

- **不推荐装饰器/中间件自动发通知**：装饰器无法知道"这次操作是否值得通知"，也无法拿到通知正文所需的数据（如"成功了几个、失败几个"）。强行自动发通知只会产出 §3 批判的空泛文案（"操作成功"）；
- **不推荐运行时中间件**：本项目是 CLI + 桌面 + FastAPI 三入口，中间件覆盖不全；且静态扫描能在 CI 阶段拦住，无需运行。

**扩展 `audit_notification_chain.py`（新增 `--coverage` 模式）**：

```python
# scripts/audit_notification_chain_scan.py —— 新增业务入口发现
# 判定"业务方法"的特征：装饰器或命名前缀命中下列任一，且位于 CALL_SITE_DIRS
BUSINESS_MARKERS = {
    "decorator": ("router.post", "router.put", "router.delete", "router.patch"),
    "func_prefix": ("_do_", "handle_", "run_", "execute_", "process_", "check_"),
}
# 已知"不需要通知"的方法（白名单，显式登记 + 理由，禁止无理由豁免；P-104）
NOTIFY_EXEMPT = {
    "get_": "纯读取，无状态变更",
    "_render_": "纯渲染",
    "list_": "纯查询列表",
}
```

产物：**未接入通知的业务方法清单**（写入 `docs/pending/notification-coverage-gap.md`），每条含文件:行号 + 是否在白名单 + 理由。人员审阅后决定"接入通知"或"登记豁免"。

**接入 CI（关键，当前最大缺口）**：现状 `audit_notification_chain.py` **不在 CI 中**（`.github/workflows/ci.yml` 只跑了 `check_i18n_key_count.py` 与 `check_i18n_hardcoded.py`），所以 74 个问题无人处理、退出码 1 无人看见。

```yaml
# .github/workflows/ci.yml —— 新增
      - name: 事件通知全链路审计（缺守卫 / 吞错 / 覆盖度）
        run: python scripts/audit_notification_chain.py --json -o notif-audit.json
        # 注意：必须先修 A-1/A-2/A-3 误报，否则 74 个问题会让门禁永远红
```

**门禁上线顺序（不可颠倒）**：
1. 修 A-1（`body` 误报）→ 问题数从 74 → **2**（仅剩 3 个吞错 + 常量误报，实际约 2）；
2. 修 A-2（null guard 判定过粗）；
3. 修 A-3（常量解析）；
4. 处理剩余真实问题（3 个 `channels/*.py` 的 `except Exception: pass`）；
5. **然后**接入 CI。

### 4.3 注意事项

1. **3 个吞错告警需要人工判断**：[dingtalk.py:99](pilotstd/core/notification/channels/dingtalk.py#L99)、[feishu.py:66](pilotstd/core/notification/channels/feishu.py#L66)、[wechat.py:58](pilotstd/core/notification/channels/wechat.py#L58)。需先读上下文确认是"签名/构造回退路径"还是真实吞错——**在设计文档阶段不做断言**，留给实施阶段（R-005 先析再答）。
2. **`notification_trigger_candidates.md` 已存在于 `docs/archive/2026-07-16-audit-reports/`**：该文档已覆盖 A/B 类触发点评估。**不要重复产出**，应把它从 `archive/` 提升为活文档，或新建 §4.2 A 的清单并在其中回引。
3. **P0 的 `credential_changed` 有实现陷阱**：通知凭证变更时，若先写入新 webhook 再通知，通知会发到**新**地址（攻击者控制）；必须先向**旧**渠道发送再落库。实施时务必按此顺序。

---

## 五、任务 5：消息聚合策略优化

### 5.1 问题分析（实测：三套机制 + 实体维度失效）

| 编号 | 事实 | 位置 | 后果 |
|------|------|------|------|
| G-1 | **`target_id` 全链路透传却从未参与分组** | [manager.py:267](pilotstd/core/notification/manager.py#L267) → `enqueue(msg, ch, target_id=…)` → [aggregate_buffer.py:128-131](pilotstd/core/notification/aggregate_buffer.py#L128-L131) 只按 `msg.event_type` 建 buffer | `channel.py:31` 注释承诺"同 event_type 下按 target_id 分组"**是假的**；三维模型的"关联实体"维度是死代码 |
| G-2 | 聚合器配置**默认值双源不一致** | [defaults.py:79](pilotstd/core/config/defaults.py#L79) = `True`；[manager.py:122](pilotstd/core/notification/manager.py#L122) 回退 `False` | 缺该键的旧配置文件会**静默关闭聚合**，与 `events.py` 文档"所有事件均经聚合器"矛盾 |
| G-3 | **三套聚合机制职责重叠** | ① `aggregate_buffer.NotificationAggregator`（跨渠道，事件级）② `core/notification_aggregator.py`（桌面专用，含 `_extract_topic` + 自动暂停）③ `platform/notify.py:_check_dedup`（3s 同标题去重） | 调一次通知可能经过 2 层合并，行为难以推理 |
| G-4 | `_extract_topic` **靠中文标题子串分类** | [notification_aggregator.py:73-97](pilotstd/core/notification_aggregator.py#L73-L97) | 检测 `"完成"`/`"失败"`/`"扫描"`/`"归档"`…——切到 en 语言后**全部失效**，topic 退化为 `_<标题前8字符>`，聚合分组崩坏 |
| G-5 | 合并消息**只保留第一条的 blocks** | [aggregate_buffer.py:228](pilotstd/core/notification/aggregate_buffer.py#L228) `merged_blocks = first_msg.blocks or []` | N 条标准状态变更合为一条时，用户只能在正文看到 5 条摘要的**首行**（`_PREVIEW_ITEMS=5` + `_PREVIEW_CHARS=60`），**其余明细的 blocks 全丢** |
| G-6 | 实体级摘要模板缺失 | [aggregate_buffer.py:266-277](pilotstd/core/notification/aggregate_buffer.py#L266-L277) | 摘要只有"📦 聚合通知（{n} 条）"+ 逐条首行，没有"张三 等 5 人 评论了…"这类**实体聚合句式** |

### 5.2 方案设计

#### A. 三维聚合模型（时间窗口 × 事件类型 × 关联实体）

**分组键设计**（G-1 修复）：

```python
# pilotstd/core/notification/aggregate_buffer.py
def _group_key(self, msg: NotificationMessage) -> str:
    """三维分组键：事件类型 × 关联实体。

    实体维度（target_id）语义：同一业务对象的标识
      - 单对象事件（如 standard_status_changed）→ 标准号
      - 批量事件（如 scan_complete）→ target_id 为空，退化为纯事件类型分组
    空 target_id 不参与分组，避免所有"无实体"消息挤进同一组而互相掩盖。
    """
    entity = (msg.target_id or "").strip()
    return f"{msg.event_type}\x1f{entity}" if entity else msg.event_type
```

`enqueue` 改造（**保持 `push()`/`flush()` 公开签名不变**，仅内部键语义变化）：

```python
    def enqueue(self, msg: NotificationMessage, target_channels: list[str], target_id: str = "") -> bool:
        """入队一条消息。分组键 = 事件类型 × 关联实体（三维聚合的实体维度）。"""
        event_type = msg.event_type
        if event_type in self._bypass:
            self._callback(msg, target_channels)
            return True
        # 兼容旧签名：显式 target_id 参数优先于 msg.target_id（manager 两处都传，取并集语义）
        if target_id and not msg.target_id:
            msg.target_id = target_id
        group = self._group_key(msg)          # ← 唯一的语义变更点
        now = time.monotonic()
        with self._lock:
            self._buffers.setdefault(group, []).append((msg, target_channels, now))
            if self._timers.get(group) is None:
                self._window_start[group] = now
                timer = threading.Timer(self._window, self._on_timer, args=(group,))
                timer.daemon = True
                timer.start()
                self._timers[group] = timer
            if len(self._buffers[group]) >= self._max:
                entries = self._buffers.pop(group, [])
                t = self._timers.pop(group, None)
                if t:
                    t.cancel()
                self._window_start.pop(group, None)
                self._send_merged(event_type, entries)
            return False
```

`_send_merged` 需把 `event_type` 从分组键还原（因为它被 `_group_key` 编码过）：

```python
    def _send_merged(self, group: str, entries: list[_Entry]) -> None:
        """合并发送。group 是编码后的分组键，需还原真实事件类型。"""
        event_type = group.split("\x1f", 1)[0]
        …
```

#### B. 实时通知 vs 摘要通知的触发条件

| 条件 | 行为 | 依据 |
|------|------|------|
| `level ∈ {warning, error}` | **实时**（`_window` 上限 5s），但同实体同类事件仍合并 | 错误必须及时；同实体重复错误合并为"失败 N 次"更有用 |
| `level == info` 且窗口内**首次** | 延迟到窗口结束合并发送（现状 60s） | 批量操作场景，避免轰炸 |
| 单条且窗口内无同类 | **不特殊化**，走统一合并流程（现状已如此，`_send_merged` 单条渲染全文 ✅） | 避免"单条直通"分支导致行为分叉（现状注释已声明该原则） |
| 条数 ≥ `batch_size`（现状 20） | 立即触发 | 防单次批量操作打爆通知 |
| 达到 `MAX_WINDOW_SECONDS`（现状 300s） | 强制发送 | 防窗口无限续期导致永不发送 |
| 用户处于静音时段 | 存 DB（`status='suppressed'`），到期补发 | 现状 [manager.py:340](pilotstd/core/notification/manager.py#L340) ✅ |

**配置化默认值修正（G-2）**：把 `manager.py:122` 的回退值与 `defaults.py:79` 对齐为 `True`，或在 `manager.py` 注释中明确"回退值仅在 defaults 未注册时生效"。**推荐前者**（一行改动，消除语义双源）。

#### C. 聚合消息展示模板与实体句式（G-5/G-6）

**实体聚合句式**（新增语言包键）：

```json
{
  "notification.aggregated.entity.header_one": "{entity} 有 1 项新动态",
  "notification.aggregated.entity.header_other": "{entity} 等 {n} 项新动态",
  "notification.aggregated.entity.header_actor": "{actor} 等 {n} 人 关注了你的标准",
  "notification.aggregated.entity.footer": "共 {n} 项，{first} 起",
  "notification.aggregated.entity.overflow": "另有 {n} 项未展示，点击查看完整列表"
}
```

**摘要生成改进**（同时修 G-5 的信息丢失）：

```python
    def _build_summary(self, entries: list[_Entry], event_type: str) -> str:
        """摘要：单条渲染全文；多条用实体句式 + 明细 + 溢出提示。

        G-5 修复：不再只取第一条 blocks —— 溢出部分给出 detail_url，
        让合并消息始终指向完整列表，而不是静默丢失。
        """
        if len(entries) == 1:
            msg = entries[0][0]
            return self._renderer.render(msg) or msg.title or _fallback_text()

        first_msg = entries[0][0]
        entity = (first_msg.target_id or "").strip()
        entity_label = _entity_label(first_msg)  # 从 blocks 提取可读实体名（如标准号）
        lines: list[str] = []

        if entity and entity_label:
            lines.append(
                t("notification.aggregated.entity.header_other", entity=entity_label, n=len(entries))
                if len(entries) > 1
                else t("notification.aggregated.entity.header_one", entity=entity_label)
            )
        else:
            lines.append(t("notification.aggregated.body.header", n=len(entries)))

        for msg, _ch, _ts in entries[:_PREVIEW_ITEMS]:
            rendered = self._renderer.render(msg)
            first_line = rendered.split("\n")[0].strip() if rendered else (msg.title or _fallback_text())
            lines.append(t("notification.aggregated.body.item", line=first_line[:_PREVIEW_CHARS]))

        if len(entries) > _PREVIEW_ITEMS:
            # 溢出提示区分"有无跳转链接"：有链接可点，无链接只报数
            if first_msg.link:
                lines.append(t("notification.aggregated.entity.overflow", n=len(entries) - _PREVIEW_ITEMS))
            else:
                lines.append(t("notification.aggregated.body.more", n=len(entries)))
        return "\n".join(lines)
```

**展示对比（用户实际看到的）**：

```
【现状】按 event_type 分组，5 条标准状态变更合为一条：
  📦 聚合通知（5 条）
  • GB/T 1-2024 状态变更
  • GB/T 2-2024 状态变更
  • GB/T 3-2024 状态变更
  • GB/T 4-2024 状态变更
  • GB/T 5-2024 状态变更

【目标】实体句式 + 溢出可点：
  GB/T 1-2024 等 12 项新动态
  • 已废止: 现行 → 废止
  • 已废止: 现行 → 废止
  • 即将实施: 制定中 → 现行
  • 已废止: 现行 → 废止
  • 已废止: 现行 → 废止
  另有 7 项未展示，点击查看完整列表 → /standards/GB%2FT%201-2024
```

#### D. 聚合状态存储方案

**结论：不引入 Redis**。理由（可执行判据）：本项目是**单进程**（FastAPI 容器内 `NotificationAggregator` 单例 + PyQt 桌面进程各一份），`aggregate_buffer.py` 已用 `threading.Lock` + `threading.Timer` 实现线程安全；跨进程共享聚合窗口**没有业务需求**（桌面与 Web 各自聚合是合理行为）。引入 Redis 会新增一个生产依赖，违反个人项目轻量化原则。

| 存储内容 | 方案 | 位置 | 生命周期 |
|---------|------|------|---------|
| 缓冲条目 | 进程内 `dict[str, list[_Entry]]` + `threading.Lock` | `aggregate_buffer.py:_buffers` | 窗口结束即清空 |
| 计时器 | `threading.Timer`（daemon） | `_timers` | 发送后 cancel |
| 窗口起点 | `dict[str, float]`（`time.monotonic`） | `_window_start` | 发送后 pop |
| 事件特定格式化器 | `dict[str, Callable]` | `_formatters` | 进程级注册 |
| **暂停状态** | **配置文件持久化**（重启保留） | `ConfigManager` 的 `notification.pause_state` | 现状 ✅ |
| **静音期压制消息** | **DB 表**（`notification_log.status='suppressed'`） | `manager.py:340` | 到期补发，现状 ✅ |
| 补发调度 | APScheduler `release_suppressed`（每 5 分钟） | `docker/scheduler.py:170-184` | 现状 ✅ |

**若未来需要多进程/多实例**：优先用 **SQLite 表**（项目已有 DB）而非 Redis——`notification_log` 已在 DB 中，新增窗口表与静音补发复用同一套读写路径，运维面不变。

#### E. 三套机制职责收敛（G-3，渐进式）

**不做一次性合并**（风险高：涉及桌面 UI 与 WebSocket 两条链路）。**按层明确职责，用注释与测试固化**：

| 层 | 组件 | 唯一职责 | 禁止 |
|----|------|---------|------|
| L1 事件级聚合 | `aggregate_buffer.NotificationAggregator` | 按 `event_type × target_id` 合并、生成摘要 | 禁止做 UI 暂停、禁止读写配置 |
| L2 桌面协调 | `core/notification_aggregator.NotificationAggregator` | 暂停/恢复、自动暂停触发、config 持久化、桥接 L1 | **禁止自己实现主题提取**（G-4 的 `_extract_topic` 应删除——L1 已用 `target_id` 做实体分组，中文子串匹配是重复且语言相关的实现） |
| L3 展示 | `platform/notify.py` | 系统托盘渲染（图标、时长） | **禁止去重**（`_DEDUP_WINDOW` 与 L1/L2 重叠，应删除或缩到"同一秒内完全相同的 title+body"防重绘） |

**G-4 修复（删除 `_extract_topic`）**：该函数的预期是产出 `target_id`，但 `target_id` 现在由 L1 直接从消息字段派生，无需从标题猜。删除它同时消除了"en 语言下聚合失效"的隐患。

### 5.3 注意事项

1. **`enqueue` 的 `target_id` 参数与 `msg.target_id` 双源**：现状 [manager.py:267](pilotstd/core/notification/manager.py#L267) 两个都传（`msg` 里已有 `target_id`，又传 `target_id=msg.target_id`）。改造时**必须统一为单一来源**，否则分组键在两个来源不一致时行为不可预测。建议：**以 `msg.target_id` 为唯一来源**，`enqueue` 的 `target_id` 参数仅用于 `push()` 兼容路径，并在文档里标注废弃。
2. **改造 `_buffers` 键语义会影响 `flush()`**：`flush(event_type)` 的语义从"刷新某事件类型"变成"刷新某分组"。**公开 API 变更**，需 grep 全库调用点（`manager.shutdown()` 走 `flush_all()` ✅ 不受影响）。实测当前无按 event_type 精确 flush 的调用点，但仍需在实施时确认（R-003 删除必扫）。
3. **`_MAX_WINDOW_SECONDS` 续期逻辑有边界缺陷**：`_on_timer` 在 `elapsed < MAX_WINDOW_SECONDS` 时"发送当前缓冲并续期"，意味着**每 60s 都可能发一条**，`MAX_WINDOW_SECONDS` 只在"再次到期时"判断——实际最长延迟可能超过 300s 一个窗口。属预存问题，**本轮告知不修**，建议单独排工单。
4. **摘要模板改动影响快照测试**：`test_aggregate_buffer.py` 有聚合摘要断言，改 `_build_summary` 签名（新增 `event_type` 参数）必须同步更新。

---

## 六、重构优先级排序表（按 ROI）

**ROI = 收益 × 确定性 ÷ 成本**。成本单位为"人日"（个人项目口径）。

| 排名 | 任务项 | 成本 | 收益 | 确定性 | 风险 | 依赖 |
|------|--------|------|------|--------|------|------|
| **1** | **修聚合实体维度**（G-1 `target_id` 分组 + G-2 默认值对齐） | 0.5 | 高：让已有的三维模型真正生效；消除 `channel.py:31` 的虚假承诺 | 极高（缺陷确定性，实测可复现） | 低（改 `_group_key` 一处 + 一行默认值） | 无 |
| **2** | **审计工具误报修正 + 接入 CI**（A-1/A-2/A-3 + §4.2 B） | 1.0 | 高：把 74 个噪声降到 ~2 个真实问题；让覆盖度回归可持续 | 高 | 低（只改脚本，不碰业务） | 无 |
| **3** | **Python 语言包三语键门禁 + 补 87 缺键**（I-2/I-3 + §1.3） | 1.0 | 高：消除繁体用户回显 key；建立长效防漂移 | 高 | 低（补齐数据 + 新增脚本） | 无 |
| **4** | **`t()` Fallback 链 + 参数错配保护**（I-1 + §1.2 C/D） | 1.0 | 中高：缺键不再裸露给用户；复数有规范 | 中高（回退链行为需测试覆盖） | 中（`t()` 是全库 1328 处调用的公共入口） | 建议在 #3 之后（先补齐数据，再改行为，便于区分"回退生效"与"数据缺失"） |
| **5** | **术语表 + 禁用词门禁**（§3.2 A/B） | 1.5 | 高：用户可感知的专业度；把规范变成可执行检查 | 中（术语表的"标准答案"需人工确认） | 中（改文案会波及 ~14 处快照断言） | 无（但建议与 #6 同批，避免两次改文案） |
| **6** | **文案改写存量修正**（§3.2 C 的 5 个事件） | 1.0 | 中高：消除 C-1~C-3 的实际歧义 | 高 | 中（快照测试同步改） | 依赖 #5 的术语表定稿 |
| **7** | **飞书表头 i18n + 渠道渲染口径统一**（T-1/T-2 + §2.2 D） | 1.0 | 中：跨渠道体验一致；消除英文键裸露 | 高 | 低（新增映射表 + 6 个语言包键） | 无 |
| **8** | **P0 缺失事件接入**（`auth_login_failed` / `credential_changed`） | 1.5 | 高（安全）| 中（需确认现有鉴权流程的接入点） | 中（`credential_changed` 有"先发旧渠道"的顺序陷阱） | 依赖 #2（否则新事件会让审计噪声加剧） |
| **9** | **删除 `_extract_topic` + 三套机制职责固化**（G-3/G-4 + §5.2 E） | 1.0 | 中：消除 en 语言下聚合失效；降低推理成本 | 高（G-4 缺陷确定） | 中（涉及桌面链路，需要 GUI 手工验证） | 依赖 #1（先修 L1 实体分组，再删 L2 的重复实现） |
| **10** | **聚合摘要实体句式 + 溢出跳转**（G-5/G-6 + §5.2 C） | 1.5 | 中高：直接改善用户可读性 | 中 | 中（改 `_build_summary` 签名 + 快照测试） | 依赖 #1、#7（需要实体标签与 detail_url 先就绪） |
| **11** | **覆盖度自查清单 + `--coverage` 自动发现**（§4.2 A/B） | 2.0 | 中高：长效防遗漏 | 中（白名单需人工审阅） | 低 | 依赖 #2 |
| **12** | **P1/P2 缺失事件 + 邮件/App 推送渠道** | 3.0+ | 中（覆盖面） | 低（需求待确认） | 高（新渠道 = 新依赖 + 新凭证管理） | 建议延后，按实际需求驱动 |
| **13** | **全库 3605 处硬编码中文 i18n 化** | 15+ | 中（仅影响非中文用户） | 低 | 高（300 文件） | 建议**不做**，或按模块专项排期；现状 `check_i18n_hardcoded.py` 只拦前端新增，Python 侧尚无门禁——若要治理，先加"只拦新增"的基线门禁，而非全量重写 |

### 6.1 推荐实施分批（每批独立可验证、可回滚）

| 批次 | 内容 | 为什么这样切 | 验证方式 |
|------|------|-------------|---------|
| **第 1 批**（0.5 天）| #1 聚合实体维度修复 | 最小改动、缺陷确定、无依赖，立刻让已有架构生效 | 新增单测：同 event_type 不同 target_id 必须分两组；跑 `pytest tests/test_aggregate_buffer.py` |
| **第 2 批**（1 天）| #2 审计误报修正 + CI 接入 | 先让"体检报告"可信，后续所有改动才有回归网 | `python scripts/audit_notification_chain.py` 退出码应为 0 或仅剩已确认的真实问题 |
| **第 3 批**（1 天）| #3 补 87 缺键 + 三语键门禁 | 纯数据 + 新脚本，零业务风险；且为 #4 提供干净基线 | `python scripts/check_i18n_python_keys.py` 输出 OK |
| **第 4 批**（1 天）| #4 `t()` Fallback 链 | 公共入口改动，单独一批便于定位回归 | `pytest tests/unit/core/notification/` 全绿 + 新增缺键回退用例 |
| **第 5 批**（2.5 天）| #5 + #6 术语表 + 文案改写 | 改文案会动快照断言，合并为一批避免反复改测试 | `pytest tests/unit/core/notification/test_message_builders_snapshot.py` 全绿；`check_copywriting.py` 通过 |
| **第 6 批**（1 天）| #7 飞书表头 + 渠道口径 | 独立小改动 | `pytest tests/test_notification_renderer.py` |
| **第 7 批**（1.5 天）| #8 P0 安全事件 | 独立业务接入 | 手工触发登录失败 / 改 webhook，验证通知到达**旧**渠道 |
| **第 8 批**（2.5 天）| #9 + #10 机制收敛 + 摘要句式 | 依赖前序，合并减少桌面链路验证次数 | GUI 手工验证 + 聚合快照测试 |

**第 1~4 批合计约 3.5 人日，即可拿到"实体聚合生效 + 体报告可信 + 缺键不再裸露 + 长效门禁"四项确定性收益**——这是本设计的核心建议。

---

## 七、总注意事项与约束遵循

1. **不引入新依赖**：本设计**零新增第三方依赖**。明确否决了 i18n 库（gettext/Babel/fluent）、模板引擎（Jinja2/Handlebars）、聚合存储（Redis），理由已在 §1.1 / §2.2 A / §5.2 D 逐条给出。若实施中确需某项，应先提交 ADR（`docs/adr/`）说明替代方案已被否决的原因。
2. **两处结构性决策已按"不动结构"执行**：① Python/Web 双语言包不收敛（§1.4 注 2）；② 三套聚合机制不合并，改为职责固化（§5.2 E）。
3. **预存问题（本轮不修，建议单独排工单，P-107）**：
   - `i18n._lang` 模块级全局在多线程下的语言串扰（§1.4 注 3）；
   - `_on_timer` 续期导致最长延迟可能超过 `MAX_WINDOW_SECONDS`（§5.3 注 3）；
   - `MarkdownRenderer` 不转义带来的 Markdown 注入面（§2.3 注 2）；
   - Python 侧 3605 处硬编码中文无门禁（§6 排名 13）。
4. **门禁不得绕过**（P-104）：本设计新增的 3 个门禁脚本（`check_i18n_python_keys.py` / `check_copywriting.py` / `audit_notification_chain.py --coverage`）**一律禁止**以 `# noqa`、基线放宽、`continue-on-error` 的方式接入。
5. **文档联动（R-006 / AGENTS.md 8.2）**：实施时若改动 `pilotstd/core/notification/`（属 `pilotstd/core/`），`git commit` 前必须跑 `python scripts/generate_capabilities.py` 并把 `capabilities_registry.md` 纳入同一 commit（AGENTS.md 七、能力矩阵触发）。若新增 ADR 或改 `docs/` 治理文档，同样触发。
6. **验证口径（R-004）**：每批改动的"完成"判定必须是**跑过命令 + 看过输出 + 真实数据 ≥3 条**。本设计给出的验证命令均为可复跑形式，不接受"应该没问题"。

---

## 附录 A：本设计的实测数据来源

| 数据 | 值 | 采集方式 |
|------|-----|---------|
| 事件总数 | 35 | `audit_notification_chain.py` |
| 构建器总数 | 36 | 同上 |
| 调用点总数 | 47 | 同上 |
| 审计问题总数 | 74（其中 72 为 `body` 误报） | 同上 + 人工核对 `channel.py:22-23` |
| Python 语言包 | zh_CN 664 / en 660 / zh_TW 581 | `json.load` 统计 |
| Web 语言包 | 三语各 860，Leaf 完全对齐 | 递归摊平求集合 |
| `notification.*` 键数 | 186 | 前缀统计 |
| `t()` 调用点 | 1328 处，679 个唯一键 | 正则扫 `pilotstd/**/*.py` |
| 通知包内硬编码中文 | **0 处** | 正则扫字符串字面量 |
| 全库硬编码中文 | 300 文件 / 3605 处 | 同上 |
| 通知测试基线 | **78 passed** | `pytest tests/test_aggregate_buffer.py tests/test_notification_renderer.py tests/test_platform_notify.py -q` |

## 附录 B：本设计**未**做的事（避免越界）

- 未修改任何代码文件（本轮仅新增本设计文档）；
- 未修改任何语言包 JSON；
- 未新增/调整 CI 配置；
- 未删除 `aggregate_buffer.py` 中的 `_extract_topic`（已在 §5.2 E 提出，但属实施阶段动作）；
- 未对 §4.3 注 1 的 3 个吞错点下结论（需实施阶段先读上下文）。
