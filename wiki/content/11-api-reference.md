# API 参考 / API Reference

> 由后端 OpenAPI 自动汇总。基址默认 `http://localhost:8000`。完整交互式文档见后端运行时的 `/docs`（Swagger）与 `/openapi.json`。

## 智能体 Agents

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/agent/` | Create a new agent |
| `GET` | `/agent/` | List all agents |
| `GET` | `/agent/schema` | Get JSON Schema fragments for the agent form |
| `PATCH` | `/agent/{agent_id}` | Update an agent |
| `DELETE` | `/agent/{agent_id}` | Delete an agent |

## 智能体模型配置 Agent Profiles

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/admin/agent-profiles/` | List Profiles |
| `GET` | `/admin/agent-profiles/{agent_id}` | Get Profile |
| `PUT` | `/admin/agent-profiles/{agent_id}` | Upsert Profile |
| `DELETE` | `/admin/agent-profiles/{agent_id}` | Delete Profile |

## 认证（兼容 vben 壳）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/auth/codes` | Codes |
| `POST` | `/auth/login` | Login |
| `POST` | `/auth/logout` | Logout |
| `POST` | `/auth/refresh` | Refresh |
| `GET` | `/menu/all` | Menu All |
| `GET` | `/user/info` | User Info |

## 后台任务

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/background-tasks/{session_id}` | List running background tasks for a session |
| `DELETE` | `/background-tasks/{session_id}/{task_id}` | Cancel a running background task |

## 对话 Chat

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/chat/` | Chat with an agent (streaming) |

## 凭证 Credentials

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/credential/` | Create a new credential |
| `GET` | `/credential/` | List all credentials |
| `GET` | `/credential/schemas` | List JSON schemas for all credential types |
| `PATCH` | `/credential/{credential_id}` | Update a credential |
| `DELETE` | `/credential/{credential_id}` | Delete a credential |

## 看板 Dashboard

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/dashboard/stats` | Get Stats |

## 知识库 Knowledge

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/admin/knowledge-bases/` | Create Kb |
| `GET` | `/admin/knowledge-bases/` | List Kbs |
| `GET` | `/admin/knowledge-bases/{kb_id}` | Get Kb |
| `PATCH` | `/admin/knowledge-bases/{kb_id}` | Update Kb |
| `DELETE` | `/admin/knowledge-bases/{kb_id}` | Delete Kb |
| `GET` | `/admin/knowledge-bases/{kb_id}/chunks` | List Chunks |
| `POST` | `/admin/knowledge-bases/{kb_id}/documents` | Add Document |
| `GET` | `/admin/knowledge-bases/{kb_id}/documents` | List Documents |
| `DELETE` | `/admin/knowledge-bases/{kb_id}/documents/{doc_id}` | Delete Document |
| `POST` | `/admin/knowledge-bases/{kb_id}/documents/{doc_id}/reindex` | Reindex Document |
| `POST` | `/admin/knowledge-bases/{kb_id}/reindex` | Reindex All |
| `POST` | `/admin/knowledge-bases/{kb_id}/retrieve` | Retrieve |
| `GET` | `/admin/knowledge-bases/{kb_id}/triples` | List Triples |

## MCP 服务器

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/admin/mcp-servers/` | Create Server |
| `GET` | `/admin/mcp-servers/` | List Servers |
| `GET` | `/admin/mcp-servers/enabled/payloads` | Enabled Payloads |
| `GET` | `/admin/mcp-servers/{server_id}` | Get Server |
| `PUT` | `/admin/mcp-servers/{server_id}` | Update Server |
| `DELETE` | `/admin/mcp-servers/{server_id}` | Delete Server |
| `POST` | `/admin/mcp-servers/{server_id}/test` | Test Server |

## 元信息

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | Health |

## 模型 Models

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/model/` | List all candidate models under the given credential type |

## 可观测性 Observability

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/admin/trace/agents` | Per-agent session/run/token aggregation |
| `GET` | `/admin/trace/analytics` | Aggregate analytics for the dashboard |
| `POST` | `/admin/trace/runs` | Ingest a run's execution-chain spans |
| `GET` | `/admin/trace/sessions` | Sessions for an agent with run aggregates |
| `GET` | `/admin/trace/sessions/{session_id}` | Full execution chain for a session |
| `POST` | `/admin/usage/` | Record a model-call usage event |
| `GET` | `/admin/usage/recent` | Recent model-call usage rows |
| `GET` | `/admin/usage/summary` | Aggregated token usage and estimated cost |

## 本体 Ontology

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/ontology/` | Create Ontology |
| `GET` | `/ontology/` | List Ontologies |
| `GET` | `/ontology/bindings/all` | List Bindings |
| `GET` | `/ontology/bindings/{agent_id}` | Get Binding |
| `PUT` | `/ontology/bindings/{agent_id}` | Upsert Binding |
| `DELETE` | `/ontology/bindings/{agent_id}` | Delete Binding |
| `GET` | `/ontology/{ontology_id}` | Get Ontology |
| `PATCH` | `/ontology/{ontology_id}` | Update Ontology |
| `DELETE` | `/ontology/{ontology_id}` | Delete Ontology |
| `POST` | `/ontology/{ontology_id}/action-types` | Create Action Type |
| `GET` | `/ontology/{ontology_id}/action-types` | List Action Types |
| `PATCH` | `/ontology/{ontology_id}/action-types/{action_type_id}` | Update Action Type |
| `DELETE` | `/ontology/{ontology_id}/action-types/{action_type_id}` | Delete Action Type |
| `POST` | `/ontology/{ontology_id}/actions/execute` | Run Action |
| `POST` | `/ontology/{ontology_id}/connectors` | Create Connector |
| `GET` | `/ontology/{ontology_id}/connectors` | List Connectors |
| `PATCH` | `/ontology/{ontology_id}/connectors/{connector_id}` | Update Connector |
| `DELETE` | `/ontology/{ontology_id}/connectors/{connector_id}` | Delete Connector |
| `POST` | `/ontology/{ontology_id}/datasources` | Create Datasource |
| `GET` | `/ontology/{ontology_id}/datasources` | List Datasources |
| `PATCH` | `/ontology/{ontology_id}/datasources/{datasource_id}` | Update Datasource |
| `DELETE` | `/ontology/{ontology_id}/datasources/{datasource_id}` | Delete Datasource |
| `GET` | `/ontology/{ontology_id}/graph` | Get Graph |
| `POST` | `/ontology/{ontology_id}/link-types` | Create Link Type |
| `GET` | `/ontology/{ontology_id}/link-types` | List Link Types |
| `PATCH` | `/ontology/{ontology_id}/link-types/{link_type_id}` | Update Link Type |
| `DELETE` | `/ontology/{ontology_id}/link-types/{link_type_id}` | Delete Link Type |
| `POST` | `/ontology/{ontology_id}/links` | Create Link |
| `POST` | `/ontology/{ontology_id}/object-types` | Create Object Type |
| `GET` | `/ontology/{ontology_id}/object-types` | List Object Types |
| `PATCH` | `/ontology/{ontology_id}/object-types/{object_type_id}` | Update Object Type |
| `DELETE` | `/ontology/{ontology_id}/object-types/{object_type_id}` | Delete Object Type |
| `POST` | `/ontology/{ontology_id}/object-types/{object_type_id}/objects` | Create Object |
| `GET` | `/ontology/{ontology_id}/object-types/{object_type_id}/objects` | List Objects |
| `PATCH` | `/ontology/{ontology_id}/object-types/{object_type_id}/objects/{object_id}` | Update Object |
| `DELETE` | `/ontology/{ontology_id}/object-types/{object_type_id}/objects/{object_id}` | Delete Object |
| `POST` | `/ontology/{ontology_id}/query` | Run Query |
| `GET` | `/ontology/{ontology_id}/traverse` | Run Traverse |

## 多智能体编排 Orchestration

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/admin/orchestrations/` | Create Orchestration |
| `GET` | `/admin/orchestrations/` | List Orchestrations |
| `GET` | `/admin/orchestrations/patterns` | List Patterns |
| `GET` | `/admin/orchestrations/{orchestration_id}` | Get Orchestration |
| `PATCH` | `/admin/orchestrations/{orchestration_id}` | Update Orchestration |
| `DELETE` | `/admin/orchestrations/{orchestration_id}` | Delete Orchestration |
| `POST` | `/admin/orchestrations/{orchestration_id}/run` | Run Orchestration |

## 用户偏好 Preferences

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/preferences/` | Get Preferences |
| `PUT` | `/preferences/` | Put Preferences |

## 发布 Publish

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/admin/published-apps/` | Publish App |
| `GET` | `/admin/published-apps/` | List Apps |
| `GET` | `/admin/published-apps/{app_id}` | Get App |
| `PATCH` | `/admin/published-apps/{app_id}` | Update App |
| `DELETE` | `/admin/published-apps/{app_id}` | Delete App |
| `POST` | `/admin/published-apps/{app_id}/keys` | Create Key |
| `GET` | `/admin/published-apps/{app_id}/keys` | List Keys |
| `POST` | `/admin/published-apps/{app_id}/keys/{key_id}/revoke` | Revoke Key |
| `GET` | `/public/apps/{token}` | Public App Meta |
| `POST` | `/public/apps/{token}/chat` | Public App Chat |
| `GET` | `/static/embed.js` | Embed Script |
| `POST` | `/v1/apps/{token}/chat-messages` | Api Chat Messages |

## 多租户/RBAC

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/admin/rbac/me` | Resolve the current caller's identity and role |
| `GET` | `/admin/rbac/roles` | List the role catalog |
| `POST` | `/admin/rbac/users` | Create a console member |
| `GET` | `/admin/rbac/users` | List console members |
| `PUT` | `/admin/rbac/users/{user_id}` | Update a console member |
| `DELETE` | `/admin/rbac/users/{user_id}` | Delete a console member |

## 定时任务 Schedule

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/schedule/` | Create a new schedule |
| `GET` | `/schedule/` | List all schedules |
| `PATCH` | `/schedule/{schedule_id}` | Update a schedule |
| `DELETE` | `/schedule/{schedule_id}` | Delete a schedule |
| `GET` | `/schedule/{schedule_id}/sessions` | List execution sessions for a schedule |

## 会话 Sessions

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/sessions/` | Create a new session |
| `GET` | `/sessions/` | List sessions for an agent |
| `PATCH` | `/sessions/{session_id}` | Update a session |
| `DELETE` | `/sessions/{session_id}` | Delete a session |
| `GET` | `/sessions/{session_id}/messages` | List messages for a session |

## 工作流 Workflow

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/admin/workflows/` | Create Workflow |
| `GET` | `/admin/workflows/` | List Workflows |
| `GET` | `/admin/workflows/{workflow_id}` | Get Workflow |
| `PATCH` | `/admin/workflows/{workflow_id}` | Update Workflow |
| `DELETE` | `/admin/workflows/{workflow_id}` | Delete Workflow |
| `POST` | `/admin/workflows/{workflow_id}/run` | Run Workflow |

## 工作区 Workspace

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/workspace/mcp` | Add Mcp |
| `GET` | `/workspace/mcp` | List Mcps |
| `DELETE` | `/workspace/mcp/{mcp_name}` | Remove Mcp |
| `POST` | `/workspace/skill` | Add Skill |
| `GET` | `/workspace/skill` | List Skills |
| `DELETE` | `/workspace/skill/{skill_name}` | Remove Skill |
