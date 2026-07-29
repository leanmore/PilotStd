# i18n 翻译缺失 — 排查与修复 SOP

> 案例来源：2026-07-29 `fix(i18n): add missing translations for quick actions and download page`
> 关联技术债：docs/technical-debt.md #3 — i18n key 一致性自动化检查
> 关联脚本：scripts/check_i18n_key_count.py — CI 阈值监控

---

## 一、现象识别

用户报告 UI 中两处显示异常：
- 快捷操作卡片显示 `action.scan_index`（而非"扫描索引"）
- 侧边栏导航显示 `nav.download_import`（而非"导入下载"）

**特征**：显示的是 i18n key 路径字符串（`nav.xxx` / `action.xxx`），而非翻译后的文本。这是 vue-i18n `t()` 函数在找不到翻译时的降级行为——直接返回 key 本身。

---

## 二、根因定位（3 步）

### Step 1：确认 locale 文件结构

读取 `web/src/locales/zh-CN.json`，确认是嵌套对象结构（非扁平 key）。这决定了 key 查找方式为点号路径：`nav.download_import` → `zh["nav"]["download_import"]`。

### Step 2：精确提取代码中使用的 key

不要猜测 key 名。搜索两类位置：
- **路由 meta**：`router.ts` 中的 `titleKey` 字段
- **组件内 `t()` 调用**：`AppLayout.vue`、`QuickActionsCard.vue` 等

本次案例中：
- [router.ts:97](web/src/router.ts#L97) → `titleKey: 'nav.download_import'`
- [router.ts:106](web/src/router.ts#L106) → `titleKey: 'action.scan_index'`
- [AppLayout.vue:44](web/src/components/AppLayout.vue#L44) → fallback 中硬编码了 `'导入下载'`（未走 i18n）

### Step 3：交叉比对

将 Step 2 提取的 key 与 locale 文件中的 key 树做 diff：

| key | zh-CN.json | en.json |
|-----|-----------|---------|
| `nav.download_import` | ❌ 缺失 | ❌ 缺失 |
| `action.scan_index` | ❌ 缺失 | ❌ 缺失 |
| `nav.task` | ✅ "任务" | ❌ 缺失 |

---

## 三、修复执行（3 层）

### 层 1：补充缺失翻译

在 **所有** locale 文件中补全缺失 key，保持嵌套结构与现有一致。中英文双文件同步修改，禁止只改一个。

### 层 2：消除硬编码

搜索组件中未被 `t()` 包裹的中文字符串，替换为 `t('xxx')` 调用。本次案例中 [AppLayout.vue:44](web/src/components/AppLayout.vue#L44) 的 `'导入下载'` 硬编码即属此类，它绕过了语言切换。

### 层 3：修正错误翻译值

本次同时发现 `nav.organize: "文件管理"` 应为 `"整理"`、`nav.pending: "待确认"` 应为 `"待处理"`。这类问题不会触发"显示 key"现象，只在用户对照中英文时才会暴露。

---

## 四、验证清单

- [ ] `npm run dev` 启动后，两处 UI 均显示翻译文本而非 key
- [ ] 切换语言至英文，显示对应英文而非中文或 key
- [ ] 浏览器控制台无 `[vue-i18n]` 相关 warning
- [ ] `npx vitest run` 全量通过
- [ ] 运行 `python scripts/check_i18n_key_count.py` 确认 key 数量未超阈值且对齐

---

## 五、防回归措施

| 层级 | 措施 | 文件 |
|------|------|------|
| 即时 | PR 模板新增 i18n key 对齐确认 checkbox | `.github/PULL_REQUEST_TEMPLATE.md` |
| CI 预警 | 每次 PR 运行 `check_i18n_key_count.py`，key 数 ≥ 50 发出 workflow warning | `.github/workflows/ci.yml` → `test-frontend` job |
| CI 阻断 | key 数 ≥ 60 时阻断合并，强制启动自动化方案 | `scripts/check_i18n_key_count.py` |
| 技术债 | 登记 #3，含触发阈值 + 推荐工具 + 实施注意事项 | `docs/technical-debt.md` |

---

## 六、给 Reviewer 的关键检查点

1. 新增路由或组件时，是否同步在所有 locale 文件中添加了翻译？
2. 是否存在 `t('nav.xxx')` 调用但 key 未在任何 locale 文件中定义？
3. 是否有 Vue 模板中直接写中文字符串（应走 `t()` 或至少标记为 `<!-- i18n-ignore -->`）？
4. CI 中 `check_i18n_key_count.py` 是否有新的 warning/error？
