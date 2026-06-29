# 架构合规性整改 — 设计文档

日期：2026-06-29

## 目标

修复审计报告的全部违规项：P0 导入违规 2 处、P1 API 直连 DB 21 处 + 7 文件业务逻辑迁移、P2 端侧重复 1 处、P3 前端 1 处。

## 架构变更

```
整改前                                整改后
────────────────────              ────────────────────
Core 惰性导入 docker.websocket    →   回调注入 ws_broadcast
Monitor 直接 import Manager       →   构造函数依赖注入
API 端点直连 Database()           →   委托新建 Service 类
API 端点含业务逻辑                →   迁移到 Manager 层 Service
UI workers 含重复路径逻辑         →   调用 Manager 方法
App.vue 缺 defineOptions          →   添加
```

## 新建 Service

| Service | 职责 | 迁移来源 |
|---------|------|---------|
| `ValidityService` | 时效性历史查询、文件入队 | `validity.py` history + enqueue |
| `UserService` | 用户 CRUD | `user.py` 全部端点 |
| `StandardStatsService` | 标准状态统计 | `standards.py` stats + list |

## 文件变更总览

15 个文件：P0(2) + P1(10) + P2(1) + P3(1) + 测试(1)
