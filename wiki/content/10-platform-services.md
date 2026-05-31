# 平台服务 / Platform Services

汇总其余横向能力模块：MCP、可观测性、RBAC、定时任务、看板。

## MCP 服务器（`app/mcp_registry/`）

持久化的 MCP 服务器注册表，会话创建时自动挂载已启用的服务器。

- transport：`stdio`（command/args/env）或 `http`（url/headers）。
- 工具开关：`enable_tools` / `disable_tools`（allow/deny）。
- 一键 `test`：用真实 MCPClient 连接 + 工具发现，回写 `last_status`（healthy/unhealthy）。
- 端点：`GET/POST /admin/mcp-servers/`、`GET/PUT/DELETE /admin/mcp-servers/{id}`、`POST /admin/mcp-servers/{id}/test`、`GET /admin/mcp-servers/enabled/payloads`。
- 前端：`mcp/index.vue`。

## 可观测性（`app/observability/`）

两类数据：

**用量 UsageLog** — 从 `MODEL_CALL_END` 采集 token：
- `POST /admin/usage/`（记录）、`GET /admin/usage/summary`（汇总+预估成本）、`GET /admin/usage/recent`（明细）。

**执行链路 TraceSpan** — 一次 run 由多个有序 span 组成（model/tool/ontology/answer/confirm）：
- `POST /admin/trace/runs`（写入）、`GET /admin/trace/analytics`（看板：成功率/时延 P95/P99/Token 趋势/Top 工具）、`GET /admin/trace/agents`（按智能体聚合）、`GET /admin/trace/sessions`（某智能体的会话）、`GET /admin/trace/sessions/{session_id}`（单会话完整链路）。

前端 `observability/index.vue` + `TraceTimeline.vue` 支持 **智能体 → 会话 → run → span** 三级下钻，span 按类型着色，输入/输出可展开看完整 JSON。

> 实测一次会话完整链路：`查询对象类型→模型→查询交易→模型→回复`，100% 成功 / 3.81s / 15,634 token / $0.0046，全部正确渲染。

## 多租户 / RBAC（`app/rbac/`）

- `User` 表 + 角色目录（`admin` / `editor` / `viewer`，各带权限码）。
- 端点：`GET /admin/rbac/me`、`GET /admin/rbac/roles`、`GET/POST /admin/rbac/users`、`PUT/DELETE /admin/rbac/users/{user_id}`。
- 默认 `admin` 自动创建且禁止删除；各业务表用 `owner_user_id` 做归属隔离；调用方身份通过 `X-User-ID` 头传入。
- 前端：`users/index.vue`。

## 定时任务（AgentScope `/schedule`）

- cron 调度：`GET/POST /schedule/`、`PATCH/DELETE /schedule/{id}`、`GET /schedule/{id}/sessions`。
- 创建时从智能体「模型配置」预填凭证/模型/权限模式。
- 前端：`schedules/index.vue`。

## 看板（`app/dashboard/`）

- `GET /dashboard/stats`：跨智能体 / 凭证 / 会话 / 本体（对象类型/实例/动作/关系数）的聚合统计。
- 前端：`dashboard/index.vue`。

## 工作区（AgentScope `/workspace`）

- MCP：`GET/POST/DELETE /workspace/mcp`
- 技能 Skills：`GET/POST/DELETE /workspace/skill`
- 后台长任务：`GET /background-tasks/{session_id}`、`DELETE /background-tasks/{session_id}/{task_id}`
