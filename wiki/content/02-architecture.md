# 架构 / Architecture

## 顶层结构

```
agentscope-admin/
├── apps/web-ele/            # 前端：Vue 3 + Element Plus 管理后台 (vue-vben-admin)
│   └── src/
│       ├── api/agentscope/  # 后端的强类型 API 客户端（每个模块一个文件）
│       └── views/agentscope # 各功能页面（Dashboard/Agents/Ontology/...）
├── server/                  # 后端：FastAPI 服务
│   └── app/
│       ├── main.py          # 组合 agentscope.create_app() + 各路由 + 智能体工具工厂
│       ├── cli.py           # `agentscope-admin` 命令行
│       ├── ontology/        # Palantir 风格本体（SQLModel + SQLite）与智能体工具
│       ├── knowledge/       # 知识库、摄取流水线、检索 + 工具
│       ├── workflow/        # Dify 风格 DAG 工作流模型 + 拓扑 SSE 引擎
│       ├── orchestration/   # 多智能体编排（6 模式）+ SSE 引擎
│       ├── publish/         # 发布应用 + API Key（Web App / REST / 嵌入）
│       ├── mcp_registry/    # MCP 服务器注册表
│       ├── observability/   # 用量日志 + 执行链路 trace
│       ├── rbac/            # 多租户用户与角色
│       ├── agent_profile/   # 每个智能体的模型配置档案
│       ├── preferences/     # 用户偏好
│       └── dashboard/       # 聚合统计
└── wiki/                    # 本静态文档站点
```

## 前后端如何组合

后端在 `server/app/main.py` 中做了三件事：

1. 调用 AgentScope 的 `create_app()` 得到一个内置了「智能体 / 会话 / 凭证 / 模型 / 聊天 / 调度 / 工作区」等端点的 FastAPI 应用。
2. `include_router(...)` 挂载本项目自有的路由（ontology / knowledge / workflow / orchestration / publish / mcp / observability / rbac / dashboard / agent-profile / preferences / auth-compat）。
3. 注册一个**智能体工具工厂**：当某个智能体绑定了本体（`AgentBinding`），创建会话时会自动给它注入本体工具（语义查询 / 遍历 / 执行动作 / 列动作）以及 `knowledge_search`、已启用的 MCP 工具等。

前端通过 `apps/web-ele/src/api/agentscope/*.ts` 的强类型客户端访问后端；页面在 `apps/web-ele/src/views/agentscope/*` 下，与后端模块一一对应。

## 数据持久化的两套体系

- **AgentScope 内置状态**：智能体定义、会话、消息、凭证 —— 由 AgentScope 的 `RedisStorage` + `LocalWorkspaceManager` 管理（需要本地 Redis）。
- **本平台扩展状态**：本体、知识库、工作流、编排、发布应用、MCP、用量/trace、RBAC 用户 —— 存于 **SQLite**（通过 SQLModel）。数据库文件默认在 `server/` 下（见 `settings.py`）。

> 这种「双存储」设计的好处：扩展功能不污染 AgentScope 自身的存储格式，可独立演进；缺点是跨两套存储的统计需要在 `dashboard` 中聚合。

## 请求与流式（SSE）

大量交互（调试台对话、工作流运行、多智能体编排、发布 App 对话）都是 **SSE 流式**：

- 调试台 / 发布 App 对话：`POST /chat/`、`POST /public/apps/{token}/chat`、`POST /v1/apps/{token}/chat-messages`。
- 工作流运行：`POST /admin/workflows/{id}/run`，逐节点产出 `node_started / text_delta / node_finished / workflow_finished`。
- 多智能体编排：`POST /admin/orchestrations/{id}/run`，产出成员转写与最终聚合。

前端用 `fetch` + `ReadableStream` 解析 SSE，把增量文本、节点输出、工具调用、人在环确认事件实时渲染。

## 可观测性的数据采集

- **用量（UsageLog）**：从模型调用结束事件（`MODEL_CALL_END`）采集输入/输出 token，调试台 client 侧与发布代理 server 侧都会写 `usage_log`。
- **执行链路（TraceSpan）**：一次运行（run）由多个有序 span 组成（模型调用 / 工具调用 / 本体操作 / 回复 / 人确认），写入 `trace_span`，前端按 智能体 → 会话 → run → span 时间线下钻。

## 鉴权与多租户（现状）

当前为**单租户骨架**：通过 `X-User-ID` 头部标识调用者，各扩展表带 `owner_user_id` 字段做归属隔离；RBAC 模块提供用户与 admin/editor/viewer 角色目录。完整的多租户 / 团队 / 细粒度权限尚在规划中（见 [路线图与缺口](13-roadmap.html)）。
