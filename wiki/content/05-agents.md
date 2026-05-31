# 智能体与模型配置 / Agents & Model Config

## 智能体生命周期

智能体本身由 AgentScope 的应用层管理，平台在其上提供 schema 驱动的表单（`GET /agent/schema` 返回 JSON Schema 片段，前端据此动态渲染身份 / 上下文 / ReAct 等配置）。

| 操作 | 端点 |
| --- | --- |
| 列表 | `GET /agent/` |
| 创建 | `POST /agent/` |
| 表单 schema | `GET /agent/schema` |
| 更新 | `PATCH /agent/{agent_id}` |
| 删除 | `DELETE /agent/{agent_id}` |

前端页面：`apps/web-ele/src/views/agentscope/agents/index.vue`。

## 模型配置（每个智能体一份档案）

`AgentProfile`（`app/agent_profile/`）持久化每个智能体的运行配置，调试台创建会话时自动预填：

- **默认模型**：`default_provider` / `default_credential_id` / `default_model`
- **生成参数**：`parameters`（temperature / top_p / max_tokens 等）
- **兜底模型**：`fallback_provider` / `fallback_credential_id` / `fallback_model`
- **流式**：`stream`
- **权限模式** `permission_mode`：与 AgentScope `PermissionMode` 对齐——
  - `default`（默认按需确认）/ `accept_edits` / `explore` / `bypass`（沙箱全放行）/ `dont_ask`

端点：`GET/PUT/DELETE /admin/agent-profiles/{agent_id}`。

## 凭证与模型

LLM 厂商凭证由 AgentScope 管理：

- `GET /credential/`、`POST /credential/`、`PATCH/DELETE /credential/{id}`
- `GET /credential/schemas` 列出各凭证类型的 JSON schema
- `GET /model/` 列出某凭证类型下的候选模型

支持 OpenAI / DashScope / DeepSeek / Anthropic 等。默认演示使用 **DeepSeek**（兼容 OpenAI 接口）。

## 调试台 Playground

`apps/web-ele/src/views/agentscope/sessions/index.vue` + `POST /chat/`（SSE 流式）：

- 实时渲染文本增量、**工具调用**与**思考链（ReAct）**。
- **人在环工具确认**：识别 `REQUIRE_USER_CONFIRM` 事件，渲染待确认工具卡片，用户点「批准/拒绝」后按同一 `reply_id` 回传 `USER_CONFIRM_RESULT` 续跑（无需用 bypass 绕过权限）。
- 自动预填该智能体保存的模型默认值与权限模式。
- 会话管理：`GET/POST /sessions/`、`PATCH/DELETE /sessions/{id}`、`GET /sessions/{id}/messages`。

## 智能体可用工具

创建会话时，后端的工具工厂会按需注入：

- 若该智能体有 `AgentBinding`：注入本体工具（见 [本体](04-ontology.html#4-智能体如何语义查询-语义操作)）。
- `knowledge_search`：检索其拥有的知识库。
- 已启用的 MCP 服务器暴露的工具。
- 内置工具（如计算器、当前时间、HTTP GET 等，取决于配置）。
