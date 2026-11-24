# NEW-44 前端测试补齐 + 本轮发现的真实缺陷（2026-11-25）

> 目标：技术债清单第 104 项 NEW-44（`84 个前端源文件无同名测试`）归零。
> 方法：3 个并行 lane（文件集不相交，只新增测试文件、不改源码），主线复核并修缺陷。

## 1. 覆盖成果

| 批次 | 范围 | 新增文件 | 用例 |
|---|---|---|---|
| lane A | `api/*`（10）、根级 `api.ts`/`i18n.ts`/`router.ts`/`App.vue`、`config/themes.ts`、`lib/storage.ts` | 16 | 100 |
| lane B | `views/*`（9）、`views/settings/*`（7） | 16 | 100 |
| lane C | `components/*`（10）、`components/dashboard/widgets/*`（10）、`components/ui/*`（1）、`composables/*`（2） | 23 | 144 |
| **合计** | | **55** | **344** |

**前端测试基线**：93 文件 / 925 例（+3 P0 例）→ **148 文件 / 1275 例**。
四件套全绿（type-check / lint / test / build）。

## 2. 合理排除（9 个文件，不计入缺口）

| 文件 | 理由 |
|---|---|
| `types/adapter.ts` `types/api.ts` `types/route-tag.ts` `types/task.ts` `views/TaskView/types.ts` | 纯类型声明，无可测运行时行为 |
| `stores/app.native-test.ts` | 由 `pnpm test:native`（node --test）独立运行，非 vitest 源文件 |
| `test-env.ts` `test-helper.ts` `test-setup.ts` | 测试基建本身 |

## 3. 本轮修复的真实缺陷（4 个，均带回归用例）

### 3.1 `lib/storage.ts:26-33` —— 新旧 key 并存时读到**旧值**（数据陈旧）
`migrate()` 在新 key 已存在时仍 `return oldVal`，`getItem` 于是返回过期旧值并删除旧 key，
更新后的数据永远读不到。影响 `main.ts`（主题）、`i18n.ts`（语言）、`AnnounceView`（tab）、
`useUserPreferences`（布局）。
**修法**：新 key 存在时只清理旧 key 并返回空串，让 `getItem` 落到新 key。回归：
`lib/storage.test.ts::新 key 已存在时…且读取返回**新值**`。

### 3.2 `views/settings/SettingsTabSites.vue:185-193` —— **保存会静默覆盖后端真实配置**
后端 `SiteConfigResponse`（`docker/api/settings.py:79-93`）限额字段是 **camelCase**
（`coolingSeconds`/`requestInterval`/`remainingQuota`/`coolingRemaining`），
前端按 **snake_case** 读 → 全部 `undefined` → 落到默认 `600 / 0.5 / null`；
界面显示错误值，**点保存会把默认值 PUT 回后端**，真实冷却/间隔/额度被覆盖。
**修法**：按后端字段名读取；回归用例用与默认值不同的值（300 / 0.25 / 42 / 7）
锁定映射，并断言保存载荷是真实值而非默认值。

### 3.3 `views/PendingView.vue:47-48` —— 结果行 `_site` 被第二次 map 覆盖
两行连续赋值，第二行 `map(x => ({...x}))` 丢掉 `_site` → 模板的站点标签恒空。
**修法**：删除冗余第二行。

### 3.4 `views/OrganizeView.vue:40-45` —— 清理空目录无 `try/catch`
失败时产生未捕获 Promise rejection、用户无任何提示，且仍会刷新列表。
**修法**：`try/catch/finally` + 展示错误（新增 i18n key `organize.clean_failed` 三语对齐），
失败不再刷新。

## 4. 已记录、待修的缺陷（8 个，均有 `文件:行` 与复现描述）

> 均为 lane 复核时发现的**真实**问题（测试按现有行为锁定，未把错误行为写成期望）。
> 建议按「错误静默 → 用户误解」优先级分批修。

| # | 位置 | 问题 | 影响 |
|---|---|---|---|
| D-1 | `components/dashboard/widgets/PendingItemsCard.vue:15-21` | `try/finally` 无 `catch` | `GET /pending` 失败 → 渲染「全部处理完毕」，把故障报成"没有待办" |
| D-2 | `components/dashboard/widgets/SystemInfoCard.vue:20-32` | 同 D-1 | 任一接口失败 → 版本 `v`、标准数 0、适配器 0 在线、数据库「空库」，故障读成"系统是空的" |
| D-3 | `components/AppCalendar.vue:27`（注释 `:14,:16-23`） | `:locale` 不是 PrimeVue 4.5.5 `DatePicker` 属性（DOM 出现 `locale="[object Object]"`） | 运行中切换语言（不重挂载）月份/星期面板不更新，与文件头承诺不符 |
| D-4 | `composables/useUserPreferences.ts:28-32,58-68` | `readLocal` 有保护，`readPlainString` 与 4 处写入无保护 | localStorage 被禁用/配额满时模块导入或 watch 抛错 |
| D-5 | `views/settings/SettingsTabSites.vue:40-42` | `saved`/`errMsg` 从未被赋非默认值 | 模板两个 `<Message>` 是死 UI |
| D-6 | `views/StandardsStatusView.vue:115,139-141,197-203` | 分页模式（`VITE_USE_PAGINATED_RECORDS_API=true`）下 `loadList()` 首行 return | 「查询」按钮无效、「刷新」只清缓存不重拉列表（默认降级模式不暴露） |
| D-7 | `views/settings/SettingsTabUsers.vue:62` | `doDelete` 无错误处理 | 删除失败无提示 |
| D-8 | `views/DownloadImport.vue:53-55` | 提交失败静默 `result=null` | 用户无反馈 |

## 5. 方法复盘

- **lane 分工按目录边界切**（`api` / `views` / `components+composables`），文件集不相交 ⇒ 无写冲突。
- **质量约束前置写进派工 prompt**（3~10 例、禁快照-only/`expect(true)`、禁只断言"被调用过"、
  ≤150 行、必须自己跑绿 + type-check）⇒ 三 lane 一次交付出 344 例且四件套全绿。
- **补测的直接收益**：本轮 55 个测试文件立刻暴露了 12 个真实缺陷（4 修 8 记），
  其中 2 个是**数据/配置静默损坏**级别（storage 读到旧值、站点配置被默认值覆盖）——
  证明"补测试"不是形式主义，而是缺陷发现手段。
