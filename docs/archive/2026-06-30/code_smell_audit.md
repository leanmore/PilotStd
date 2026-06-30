# 废弃API与代码异味扫描报告

> 调查日期：2026-06-29
> 范围：全项目代码库（docker/、pilotstd/、web/src/）

---

## 1. 废弃API

| # | 位置 | 废弃API | 严重度 | 说明 |
|---|------|--------|--------|------|
| 1 | [SettingsView.vue:203](web/src/views/SettingsView.vue#L203) | `document.execCommand('copy')` | 低 | 已弃用的剪贴板 API，但作为 HTTP 环境的降级方案可保留 |

**已修复项目**（之前的重构中消除）：
- `app.add_websocket_route()` → 已改为 `@app.websocket()` ✅
- `on_event("startup")` → 已使用 `lifespan` ✅
- 分散的中间件定义 → 已提取到 `docker/middleware.py` ✅

**验证通过项目**：
- 无 Pydantic v1 残留 ✅
- 无多个 exception_handler 分散 ✅
- @app.websocket 仅 app.py 一处 ✅

---

## 2. 重复代码

| # | 位置1 | 位置2 | 模式 | 建议 |
|---|------|--------|------|------|
| 1 | [app.py:242](docker/app.py#L242) | [system.py:159](docker/api/system.py#L159) | 两个健康检查端点 | 有意设计：`/api/health` 为 Docker HEALTHCHECK，`/api/system/health` 为详细状态。无需合并 |
| 2 | [announce.py:64,78](docker/api/announce.py#L64) | 同文件内 2 处 | `except Exception: pass` 吞异常 | 应至少记录日志 |
| 3 | [system.py:30,53,89](docker/api/system.py#L30) | 同文件内 3 处 | `except Exception: pass` | 容器检测失败可静默，可接受 |
| 4 | [validity.py:113](docker/api/validity.py#L113) | 1 处 | `except Exception: pass` | 应至少记录日志 |

**已验证无重复的项目**：
- 中间件类（已唯一） ✅
- 数据库连接创建（仅 app.py lifespan + facade.py） ✅
- 配置读取模式（统一通过 `mgr.cfg`） ✅

---

## 3. 架构问题

### 3.1 大文件（>500 行）

| # | 文件 | 行数 | 建议 |
|---|------|------|------|
| 1 | `pilotstd/manager/facade.py` | **1687** | 最大文件，应拆分（如提取 query/download/scan 子模块） |
| 2 | `pilotstd/query/engine.py` | 1139 | 可拆分为 adapter 初始化和查询逻辑两部分 |
| 3 | `pilotstd/scan/parser.py` | 962 | 解析规则可配置化或分类拆分 |
| 4 | `pilotstd/ui/main_window.py` | 942 | 已通过 mixin 模式拆分，主文件仍偏大 |
| 5 | `pilotstd/core/db.py` | 862 | 迁移 + 备份逻辑可独立 |
| 6 | `pilotstd/announcement/ocr.py` | 769 | 多 OCR 提供者可拆分为子模块 |
| 7 | `pilotstd/ui/workers.py` | 551 | — |
| 8 | `pilotstd/cli/commands.py` | 524 | 每个子命令可独立文件 |
| 9 | `pilotstd/manager/organizer_service.py` | 523 | — |
| 10 | `pilotstd/core/config.py` | 520 | 可拆分为读写分离 |
| 11 | `pilotstd/ui/controllers/query_mixin.py` | 508 | — |

### 3.2 裸 except

| # | 位置 | 代码 |
|---|------|------|
| 1 | `docker/api/announce.py:64` | `except Exception: pass` |
| 2 | `docker/api/announce.py:78` | `except Exception: pass` |
| 3 | `docker/api/system.py:30` | `except Exception: pass` |
| 4 | `docker/api/system.py:53` | `except Exception: pass` |
| 5 | `docker/api/system.py:89` | `except Exception: pass` |
| 6 | `docker/api/validity.py:113` | `except Exception: pass` |

### 3.3 层间依赖

| 检查项 | 结果 |
|--------|------|
| API → 业务层直接导入 | ✅ 仅 tasks.py 惰性导入 enum（合规） |
| Core → 上层导入 | ✅ 零命中 |
| 循环依赖 | ✅ 未发现 |

---

## 4. 前端问题

### 4.1 生产代码中的 console 调用

| # | 文件 | 代码 |
|---|------|------|
| 1 | `components/FileMonitor.vue:35` | `console.log('🚀 FileMonitor setup')` |
| 2 | `composables/useNotification.ts:70` | `console.error('解析通知消息失败:', e)` |
| 3 | `composables/useNotification.ts:126` | `console.error('标记已读失败:', e)` |
| 4 | `views/QualityView.vue:30` | `console.error('质量检查失败:', e)` |
| 5 | `views/SchedulerStatus.vue:38` | `console.error('获取调度器状态失败:', e)` |

### 4.2 其他

| 检查项 | 结果 |
|--------|------|
| Vue 2 遗留模式（`Vue.extend`, `this.$emit`） | ✅ 无 |
| Element UI / Element Plus 混用 | ✅ 无（纯 PrimeVue） |
| 分散的 `app.use/app.component` | ✅ 仅在 main.ts |
| `v-for` key 使用 index | ✅ 无 |

---

## 5. 统计摘要

| 维度 | 数量 | 严重度分布 |
|------|------|-----------|
| 废弃API | 1 处（低） | 低:1 |
| 重复代码 | 4 处 | 低:4（均为有意设计或可接受） |
| 架构问题 | 17 处 | 中:11（大文件）+ 低:6（裸 except） |
| 前端问题 | 6 处 | 低:6（console 调用 + 1 处废弃 API） |

---

## 6. 修复建议优先级

| 优先级 | 问题 | 建议 |
|--------|------|------|
| 低 | 6 处裸 except | 添加 `logger.warning` 记录异常上下文 |
| 低 | 5 处 console.log/error | 替换为统一的 logger 服务 |
| 低 | cli/commands.py (524行) | 每个子命令拆分为独立文件 |
| 远期 | facade.py (1687行) | 按业务域拆分为子模块 |
| 远期 | engine.py / parser.py / ocr.py | 按职责拆分 |

**结论**：代码库整体健康。主要重构已在五阶段文件夹整改中完成。剩余的"异味"均为低优先级，不影响功能或安全。
