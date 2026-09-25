# 前端 UI 组件规范

## 技术栈

- Vue 3 + Composition API
- TypeScript 严格模式
- PrimeVue 组件库

## Token 语义基线（背景选择）

> 来源：日志栏主题化修复（2026-08）暴露的 `--p-surface-0` 语义陷阱。

| Token | 语义 | 适用场景 |
|---|---|---|
| `--bg` | 页面画布色（canvas） | **与页面背景无缝融合**的组件（内容流内嵌面板，如日志栏） |
| `--p-surface-0`（= 项目 `--surface`） | 卡片/面板表面色（surface） | **需要视觉抬升**的卡片/弹窗/浮层 |

规则：
- 凡与页面背景无缝融合的组件，一律用 `--bg`（深色下 surface 色比画布色浅一档，误用会造成"浮起"层级倒挂）
- 需要视觉抬升的卡片/弹窗，才用 `--p-surface-*`
- 禁止在背景上使用硬编码 hex 值（如 `#1a1a2e`），一律走 Token

## 组件复用原则

1. 新建组件前，必须搜索 `src/components/` 确认是否已有可复用组件
2. 禁止在多个页面中复制粘贴相同的 UI 逻辑
3. 通用组件放 `src/components/common/`，业务组件放对应模块目录

## 状态展示规范

- 同一数据源的状态标签，全局只允许一个展示入口
- 附件区域：无附件时必须使用 `v-if` 彻底隐藏操作按钮，禁止使用 `disabled`
- 空状态：仅展示提示文本，禁止渲染无效的操作元素

### 下载状态（`favorite_downloads.status`）

- 映射（文案键 + 颜色分级 + 未知值兜底）只有一处事实源：`web/src/utils/downloadStatus.ts`；页面禁止内联 `status === 'done' ? ...` 之类的判断
- 渲染只有一处入口：`FavoriteStatusTag.vue`（收藏页状态列与公告详情页收藏列共用）
- 数据库枚举 6 值：`pending` / `downloading` / `archiving` / `done` / `failed` / `abandoned`；表定义无 CHECK，未知值必须回退显示原文而非空白
- 第 7 个展示项 `download_status === null`（收藏已存在但队列行缺失，历史遗留）显示"**未加入队列**"（`download.status.notQueued`），属前端兜底而非数据库枚举。措辞刻意区别于"已入队"：这类行不会自动流转，说"待下载"会误导（第三轮 #18 B）

## 导航与布局

- 返回按钮使用次级文本色（`#a0aec0`），hover 时高亮
- 页面元素左边缘与导航对齐，保持统一页边距
- 卡片之间保持 `mb-4` 以上的呼吸间距

## API 类型约束

- 前端 API 类型定义必须与后端 Schema 保持一致
- 新增接口时，必须同步更新 `src/types/api.ts`
