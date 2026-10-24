# 实现摘要（Implementation Digest）

> **层**：历史 ｜ **性质**：46 篇过程稿的精华沉淀，原件已移出 git（本地 `docs/.local/archive/2026-10-24/`）
> **用途**：回答"这个功能当初为什么这么做、踩过什么坑"，避免 AI 与后来者重新推演
> **边界**：只写**已实现**的结论；未实现的期望见 `docs/ROADMAP.md`
> **写法**：每条结论都能独立成立；需要细节时按 §六 索引回查原件

---

## 一、通知系统（一期，2026-10 交付）

### 1.1 三层模型（整个设计的骨架）

| 层 | 是什么 | 数量 |
|---|---|---|
| 业务事件 | 后端发生的事，如"扫描完成""某标准下载失败" | **41** 个（`event_spec_data.py` 的 `EventSpec` 声明）+ 1 个平台层 `desktop_toast` |
| 通知事件层 | 面向用户的 7 个类别（聚合/路由/订阅粒度） | 7 |
| 消息形态 | `blocks` 结构化正文 + 4 渠道渲染器 | 4 渠道 |

**关键判断**：41 不是"太多"，而是比 MoviePilot 的 9 类**更细一层**——MoviePilot 放弃了事件身份，所以做不到"可订阅、可审计"。

### 1.2 15 项裁决（2026-10-02，节选）

| 裁决 | 结论 |
|---|---|
| 类别粒度 | 双层配置：10 类为主 + 折叠"按业务事件细分" |
| 平台层事件登记 | 正式登记（`desktop_toast` 等），不再用"摘要声明"逐个解释 |
| Web 实时通道 | 不重建，阶段 0 清掉 WS 死代码 |
| 聚合 | 全部事件走同一聚合器，开关交给用户 |
| 静默期 | 静默判断留在 `_do_send`；功能关闭判断前移到 `send_event` 早段 |

### 1.3 六阶段交付

| 阶段 | 内容 | 结果 |
|---|---|---|
| 0 | WS 死代码清理 + 前端轮询改造 | 已交付 |
| 1 | 12 个新字段 + 迁移（1a/1b/1c） | 已交付，零行为变更 |
| 2 | 状态投影 + 映射（2a/2b/2.5a） | 已交付 |
| 3 | 渠道交互（回调、动作、过期降级） | 已交付 |
| 4 | 配置模型 schema 化（4 个模板块 → schema 驱动） | 已交付 |

### 1.4 聚合规则（现行）

- 首次延时 **5s**，窗口上限 **300s**，单批上限 **50 条**；
- 桌面端另有本地聚合与去重；
- 用户可在设置页关闭聚合（`notification.aggregate_enabled`）。

### 1.5 渠道现状

| 渠道 | 形态 | 能力边界 |
|---|---|---|
| Telegram | Bot API | MarkdownV2 需 18 类字符转义；可编辑 |
| 钉钉 | 机器人卡片 | 消息更新走"卡片更新"（`outTrackId`），不是编辑 API |
| 飞书 | Webhook | **不返回 `message_id`**，无法原地更新 |
| 企业微信 | Webhook | 卡片模板形态；回调用加密回调 |

### 1.6 五条教训（都是踩过的坑）

1. **聚合器合并消息会丢 `blocks`** —— 曾只保留空 `body`，Telegram 渲染出空文本。修法：合并时保留结构化正文。
2. **统计数字不得手算** —— 影响面表曾把 12/8 写错，导致"六类合计 43 ≠ 41"。唯一数据源是 `mapping.py`。
3. **"全量套件 65 项失败"多数不是产品缺陷** —— 是测试库隔离只 patch 了一半、历史测试数据污染；先分清"我引入的"和"本来就在的"。
4. **静态字符串匹配判断触发点不可靠** —— 首轮靠"事件键是否出现在文件里"得出 3 处误报，改用**运行时插桩**才拿到真实触发地图。
5. **安全告警必须绕过聚合与静默** —— 且要同步阻塞发送成功后才写库，否则告警会"看起来发了其实没发"。

### 1.7 遗留（未实现，见 ROADMAP S2~S4）

事件清单 4 份拷贝（后端/e2e/门禁/前端，前端已漂移 6 个事件）、渠道定义 11 处、`manager.py` 偏厚、分档通知与静默期冲突。

---

## 二、站点分类与路由

- **21 个生产站点**按"可靠性 × 覆盖度"分类，分类结果来自 `ADAPTER_DEFAULT_PROFILES`，落到 `config/site_capabilities.yaml`；分类数据源是 `docs/analysis/site_classification_partial.md`（活文档，未归档）。
- **v1 → v2 路由**：三级漏斗（精确匹配 → 分类优先 → 兜底），灰度期用"双跑对比"评估，未达 1000 次查询前不清理 v1。
- **一个被证伪的判断**：gongbiaoku 搜不到 ISO 等国际标准，不是搜索逻辑 bug，而是**源站不支持**（类型 B）。代码层把关键词原样传递，无截断、无编码问题。
- **另一个纠错**：GB 是"全行业国标"，不能按行业过滤，否则会漏。

---

## 三、重构史

| 重构 | 做法 | 结果与教训 |
|---|---|---|
| **T-41 大文件分拆** | 按"结构缝"逐子批拆，先补依赖图再动手 | 收官后仍有"伪公开面"（对外像 API、实际内部用）；**CSS/模板类问题只有生产构建能暴露**，测试全绿不代表镜像能构建 |
| **ExactMatchMixin 拆分** | 7 个匹配方法抽成独立 `ExactMatcher`（`pilotstd/scan/parser/_exact_matcher.py`） | 解析器从大类拆成"通道类"，可单独测 |
| **收藏分类（v57）** | 新增 `standard_type` 字段 + 去重 + 分类导出 | 设计稿→迁移脚本→前端同批，避免"字段先上、UI 后补" |
| **服务端会话存储** | `SessionStore` 独立于业务（`docker/session_store.py`） | 会话与业务解耦后，登录态可单独测 |
| **G-010 拆分治理** | 500 有效行阻断线 + 拆分证据 | 拆之前先估注释密度（G-012 ≥3%），否则拆完反而不达标 |

**通用教训**：先测再拆；拆完必须跑全量（含 GUI 与生产构建）；"没删干净的旧入口"比"没拆"更危险。

---

## 四、故障档案

### 4.1 收藏标准下载失败（分类与可重试性）

基于 **47,112 行生产日志** + 代码枚举，失败分四类：源站无全文 / 需登录或权限 / 网络与超时 / 文件名冲突。**只有后两类可自动重试**；前两类重试无意义，应直接提示用户。

### 4.2 `'super' object has no attribute 'request'`

容器内 `session.py` 与本地 HEAD 是**同一 blob**，说明不是"部署了旧代码"。根因在 `super()` 的父类解析（多重继承场景），修复落在子类实现而非调用点。

### 4.3 通知日志页的定位（产品结论）

通知日志页是"排查通知有没有发出去"的地方，**不是阅读通知的地方**；因此"已读"概念在该页不成立。曾按"阅读器"设计，方向错了。

### 4.4 SPPT 8087 地方标准平台

Task 0 评估结论：平台架构与国标站点差异大（接口、分页、字段都不同），不能复用现有适配器骨架。后续以 `sppt.py` / `sppt_local.py` 两个适配器落地。

---

## 五、一次性结论登记（已失效的快照，只留结论）

| 事项 | 结论 | 时效 |
|---|---|---|
| Handler 健康度（2026-08-02） | 清理后存活 Handler 无死代码；遗留耦合问题清单见原件 | 已过期，看 `docs/debt/` |
| 覆盖率调查（2026-07-31） | 当时**没有覆盖率工具链**，靠人工盘点 | 已被自动报告取代 |
| F-03 双源凭证审计 | 凭证有两条读取链，优先级不同；统一源是后续改造依据 | 已落地 |
| Aura Token 同步 | 组件文字 token 多为语义引用，直接值只有 surface 系色板 | 已落地 |
| 双端侦察 | 41 事件分端：Docker 25 / 两端共用 15 / Windows 1；Windows 端"信号呈现"是三层的，不是推送 | 结论仍有效 |
| MoviePilot 对标 | 9 类事件 / 116 调用点 / i18n 0 接线 / 13 处腐化 | 结论仍有效，仅作参照 |

---

## 六、原件索引（已移出 git，本地留存）

| 章节 | 原件（`docs/.local/archive/2026-10-24/` 下同名文件） |
|---|---|
| §一 通知 | `plans/notification-redesign/*`（18 篇）、`plans/notification-system-design/{01,03,04,05}`、`plans/moviepilot-investigation/*`、`plans/dual-end-investigation/*` |
| §二 路由 | `analysis/{gongbiaoku_search_audit,query_metrics_routing_mismatch_20260816,site_classification_partial_v1.0,v1_cleanup_readiness,v1_vs_v2_routing_comparison}`、`issues/router_v2_feedback` |
| §三 重构 | `architecture/exact_match_refactor_spec`、`designs/favorite-classification-design`、`development/session-store-design`、`plans/{P10_plan,batch2-security-audit-design,task-progress-reporting}` |
| §四 故障 | `reference/{diagnosis-favorite-download-failures,diagnosis-super-request-error,notification-effectiveness-analysis,sppt-8087-assessment}` |
| §五 快照 | `testing/{handler-health-report-2026-08-02,project-coverage-survey-2026-07-31}`、`investigations/*`（3 篇） |

> 其余 12 篇（精读笔记 8、迁移说明、诞生记、Q20 验证、决策摘要）无功能结论，未纳入本摘要，原件同样在本地归档目录。
