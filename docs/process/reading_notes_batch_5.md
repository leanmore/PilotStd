# 精读笔记 — 第 5 批（设计 / 指南 / 分析类）

- **Created**: 2026-08-19T22:40:00+08:00
- **Updated**: 2026-08-19T22:40:00+08:00
- **批次状态**: 待确认（等待人类 Gate 确认）
- **精读深度判定留痕**: 依据审计描述「site_classification_v1=设计记录/v2 路由基础」「development/*=治理规则」「specs/=待确认过时」「guides/*-pattern=ADR 引用范式」→ site_classification_v1 **逐字精读**；documentation-policy/session-store **重点精读**；specs/ 两件 **速读确认过时**；guides 范式复用 ADR-002/003/004 精读结论（代表核验）。

---

## 1. 精读文档与结论

| 文档 | 判定 | 证据 |
| :--- | :--- | :--- |
| docs/design/site_classification_v1.md（71 行） | ✅ 有效保留 | v2 路由分类基础（L1 综合/特色、L2 四子类、计数规则、冲突优先级）；与 router_v2 三级漏斗对应；被 analysis/site_classification_partial.md 引用为方案版本 |
| docs/development/documentation-policy.md（198 行） | ✅ 有效保留，⚠️ 2 处内部矛盾 | 文档同步两路机制/PR 门禁/归档协议/GitHub 入仓标准——**与本次 DOCUMENTATION_MAP 任务直接相关**；见 §2 矛盾 |
| docs/development/session-store-design.md（158 行） | ⚠️ 待确认 | 服务端会话存储设计；**实际代码未采用文档中的固定密钥方案**（见 §2） |
| docs/development/g-010-enforcement.md | ✅ 有效 | G-010 门禁规则详情（与 gates.md 摘要-详情分工） |
| docs/specs/功能规格说明书.md（690 行） | 🔴 过时 → 建议归档 | 版本历史停留 1.15（2026-06-16）；7-8 月重构未反映 |
| docs/specs/模块与功能清单.md（85 行） | 🔴 过时 → 建议归档 | 2026-06-30 生成，Mixin→Handler/Q22 适配器未反映 |
| docs/guides/*-pattern（5 个范式） | ✅ 有效保留 | 被 ADR-002/003/004 与 architecture.md 引用的活跃范式（Engine 零 Qt/Handler 薄包装/I/O 隔离） |
| docs/guides/refactoring-lessons.md（144 行） | ✅ 有效保留 | 大函数拆分经验（知识沉淀） |
| superpowers/specs 近期（08-14/08-16 系列） | ✅ 有效保留 | 近期活跃设计记录（时效性表单重构/HTTP 解耦/任务进度恢复/悬浮按钮/轮转日志） |
| docs/guides/Docker使用指南.md / 人工测试方案.md / 用户帮助文档.md | ✅ 保留 | 操作指南（与 deployment/README 重叠已在 §7 记录） |

## 2. 证据链（规则 1 留痕）

| 发现 | 依据 | 状态 |
| :--- | :--- | :--- |
| documentation-policy L104 断链 | `docs/development/gate-15-enforcement.md` 不存在（G-015 实际脚本为 scripts/check_g_015_relative_imports.py） | 🔴 断链 |
| documentation-policy L20 声称 capabilities_registry"移出仓库" | `git ls-files docs/governance/capabilities_registry.md` 显示**在仓**（且 CLAUDE.md §8 强制提交它） | 🔴 文档与现状矛盾 |
| documentation-policy L197 声称 archive"仅本地保留不入仓" | `git ls-files docs/archive/*` 显示 **有文件被跟踪** | 🔴 文档与现状矛盾 |
| session-store-design L26 固定密钥方案 `"pilotstd_jwt_secret_2026_fixed_key"` | 实际 `docker/auth.py` 为 `SECRET = os.environ.get("JWT_SECRET") or secrets.token_urlsafe(32)`——**固定密钥未落地**，仍用随机 token | ⚠️ 文档与代码不一致（需确认文档应更新还是标记未采纳） |
| specs/功能规格说明书 过时 | 版本历史止于 1.15（2026-06-16），690 行 | 🔴 过时（Q2-2 批次已记录） |
| specs/模块与功能清单 过时 | 2026-06-30，被 docs/development.md 引用 | 🔴 过时 |

## 3. 重要认知

1. **documentation-policy.md 是本次任务的关键规范**：其"两路触发机制 + 归档协议 + 入仓标准"直接约束 DOCUMENTATION_MAP 的生成与维护方式（地图属于"入仓成品文档"）。整理时需以其为准并修正其内部矛盾。
2. **session-store-design 的固定密钥方案未落地**——说明该文档可能记录的是"被否决的备选方案"或"部分采纳"，需在阶段 B 确认是更新还是标注。
3. **specs/ 两件过时**：建议归档并在 DOCUMENTATION_MAP 标注"由 docs/architecture/modules/* 与 docs/adapters/README.md 取代"。

## 4. 操作需求草案（供阶段 B 汇总）

| 动作 | 目标 | 优先级 | 证据 |
| :--- | :--- | :--- | :--- |
| 修断链 | documentation-policy L104 gate-15-enforcement.md → 实际脚本 | P2 | §2 路径验证 |
| 修正矛盾 | documentation-policy L20/L197（capabilities_registry 在仓、archive 有入仓文件） | P2 | §2 git 实证 |
| 确认 | session-store-design 固定密钥方案：更新文档 or 标注"未采纳" | P1 | §2 代码对照 |
| 归档 | specs/功能规格说明书.md、specs/模块与功能清单.md | P2 | 版本停留证据 |
| 保留 | site_classification_v1、guides/*-pattern、superpowers 近期 | — | 有效 |