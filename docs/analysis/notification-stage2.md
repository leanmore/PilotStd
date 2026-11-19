# 通知阶段 2 分析报告（D-2）

> 2026-11-19。只分析，不实现。范围：wechat / telegram / dingtalk / feishu。

## 1. 是否有统一语义层

有，但只在“消息内容”层：

- 事件 → `NotificationMessage`（`pilotstd/core/notification/` 的 builder/event_spec），内容是平台无关的 `TextBlock` / `KeyValueBlock` / 列表块；
- 渠道层（`channels/*.py`）负责把同一 `NotificationMessage` 渲染成各平台载荷：微信 markdown/text、Telegram HTML、钉钉/飞书卡片/文本；
- 发送重试/限流/Retry-After/错误去重已提升到 `channels/base.py`，四家共用。

结论：**不是各自为战**；语义转换层存在，但“渲染”仍分散在各 channel。

## 2. 模块化程度（新增渠道）

新增一个渠道需要改：
1. `pilotstd/core/notification/channels/` 新增 channel 类（transport + 渲染）；
2. 渠道注册/配置（`channel_spec_data.py`、能力矩阵、设置项）；
3. 事件规格/策略（是否需要该渠道默认开启）；
4. 测试（channel guard、render、发送失败/限流）。

约 3~5 处；渲染语义由各渠道自己实现，是阶段 2 的主要耦合点。

## 3. 日志中的语义一致性

`notification_log` 的 `event_type/title/body` 由统一 builder 生成，同一事件跨渠道标题/正文一致；差异只在渠道格式与长度截断。已发现的问题：
- `status` 是**投递状态**，IP 更新失败时渠道投递成功仍为 `success`，业务失败只在正文；已加 `level`（security_alert→warning、task_failure→error）缓解，但根上仍缺“业务结果”字段；
- 渠道长度限制（Telegram 4096、微信 Markdown）各自截断，长批次报告可能出现渠道间内容不一致。

## 4. 阶段 1 缺什么

1. 渠道渲染没有统一模板/能力声明（markdown/html/card 差异靠各 channel 手写）；
2. 业务结果与投递结果未分离；
3. 无 dry-run/站内渠道（dry-run 已补，见 A-45）；
4. 渠道降级/回退（一个渠道失败是否换渠道）未实现；
5. 长消息截断/分片策略不统一。

## 5. 阶段 2 建议

- 引入“渠道能力声明 + 渲染适配器”：`supports_markdown/html/card`、`max_len`，由统一 renderer 选择降级格式；
- `NotificationMessage` 增加 `business_status`/`level`，日志拆 `delivery_status` 与 `business_status`；
- 统一分片/截断（按块切分，保留标题与计数）；
- 渠道失败回退策略（可选：按优先级 fallback，默认关闭）；
- 先做 1（能力声明 + 统一 renderer）与 2（状态分离），再做 3/4。

**范围建议**：阶段 2 只做“语义/状态/渲染一致性”，不重写各渠道 transport。
