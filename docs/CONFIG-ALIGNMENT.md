# 智能体配置对齐：AgentScope ↔ Claude Agent SDK ↔ 本平台

> 目标：把 AgentScope 后端支持的全部配置「界面配置化」，并对齐业界标准（Claude Agent SDK `ClaudeAgentOptions`）的智能体配置面。本文逐项列出三方对照与本平台落地状态。

图例：✅ 已在 UI 配置化 ｜ 🟡 后端已支持，UI 部分/计划中 ｜ ⬜ 未实现

## 一、对照总表

| 配置项 | Claude Agent SDK | AgentScope 2.0 | 本平台 UI | 状态 |
| --- | --- | --- | --- | --- |
| 系统提示词 | `system_prompt` | `agent.system_prompt` | 智能体→身份信息 | ✅ |
| 模型 | `model` | `session.chat_model_config.model` | 智能体→模型配置 / 调试台 | ✅ |
| 兜底模型 | `fallback_model` | `session.fallback_chat_model_config` | 智能体→模型配置（兜底模型） | ✅ |
| 生成参数（温度/topP/maxTokens） | 模型参数 | `chat_model_config.parameters` | 智能体→模型配置 / 调试台 | ✅ |
| 流式输出 | （SDK 默认流式） | chat SSE | 智能体→模型配置（流式开关） | ✅ |
| **权限模式** | `permission_mode`(default/acceptEdits/plan/bypassPermissions) | `PermissionMode`(default/accept_edits/explore/bypass/dont_ask) | 智能体→模型配置 + 调试台 | ✅ |
| 最大轮次 | `max_turns` | `react_config.max_iters` | 智能体→推理配置 | ✅ |
| 拒绝后停止 | — | `react_config.stop_on_reject` | 智能体→推理配置 | ✅ |
| 上下文压缩（触发/保留比例、压缩提示、摘要模板） | （SDK 自动压缩） | `context_config.*` | 智能体→上下文配置 | ✅ |
| 工具结果截断 | — | `context_config.tool_result_limit` | 智能体→上下文配置 | ✅ |
| 结构化摘要 schema | — | `context_config.summary_schema` | — | ⬜ |
| 工具白名单/黑名单 | `allowed_tools`/`disallowed_tools`/`tools` | toolkit + `AllowedFunctionTool` | 本体绑定 allow-list（对象类型/动作） | 🟡 仅本体工具 |
| MCP 服务器 | `mcp_servers` | `/workspace/mcp`(stdio/http, shared/isolated/ephemeral) | — | 🟡 后端已通，计划出页面 |
| 技能(Skills) | setting_sources/skills | `/workspace/skill` | — | 🟡 后端已通，计划出页面 |
| 工作目录 | `cwd`/`add_dirs` | `session.workspace_id` + WorkspaceManager(local/docker/e2b) | — | 🟡 后端已通 |
| 定时任务 | — | `/schedule`(cron) | — | 🟡 API 已封装(`schedule.ts`)，计划出页面 |
| 后台任务 | — | `/background-tasks/{session_id}` | — | 🟡 计划 |
| 会话续聊/恢复 | `continue_conversation`/`resume`/`fork_session` | session 持久化 + `/sessions/{id}/messages` | 调试台会话内续聊 | 🟡 历史会话浏览计划中 |
| 预算上限(USD) | `max_buffer_size`/budget | — | — | ⬜（AgentScope 无对应） |
| 凭证管理 | API key（环境） | `/credential`(多 provider) | 凭证管理 | ✅ |
| 模型列表 | — | `/model?provider=` | 模型下拉自动拉取 | ✅ |
| Hooks | `hooks` | 框架内 hook | — | ⬜ |
| 并行工具调用 | （内置） | toolkit 支持 | — | ⬜ |

## 二、本平台已落地（本轮新增）

1. **模型与生成参数（agent 级，持久化）**：`agent_profile` 表 + `GET/PUT/DELETE /admin/agent-profiles/{agent_id}`。智能体抽屉「模型配置」Tab 配置默认凭证 / 默认模型 / temperature / top_p / max_tokens / 流式 / 兜底模型 / 标签 / 描述；调试台按 agent 自动预填。
2. **权限模式 permission_mode**：与 AgentScope `PermissionMode` 完全对齐（default / accept_edits / explore / bypass / dont_ask），存于 agent profile，调试台创建会话后通过 `PATCH /sessions/{id}` 应用，并提供现场切换。对应 Claude Agent SDK 的 `permission_mode`。

## 三、AgentScope 已支持、尚未在 UI 体现（后续优先级）

- **MCP 服务器管理**（`/workspace/mcp`）：stdio / http 两类，连接作用域 shared / isolated / ephemeral，含工具健康探测。→ 计划新增「工具与 MCP」页面。
- **技能 Skills**（`/workspace/skill`）：按 skill_path 注册/卸载。→ 同上页面。
- **定时任务 Schedule**（`/schedule`）：cron 周期触发 agent 会话；`schedule.ts` 已封装。→ 计划新增「定时任务」页面。
- **后台任务 / 长任务**（`/background-tasks/{session_id}`）：查看与取消。→ 计划并入调试台。
- **工作区后端**：LocalWorkspaceManager 已用；AgentScope 另支持 Docker / E2B 沙箱工作区，可作为系统设置项暴露。
- **结构化摘要 summary_schema**：上下文压缩的结构化输出 schema，可在「上下文配置」补充。

## 四、对齐结论

- **标准智能体配置面**（system prompt / model / 生成参数 / 兜底模型 / 权限模式 / max turns / 工具权限）已对齐 Claude Agent SDK 的核心字段，其中 `permission_mode`、`fallback_model` 为本轮补齐。
- **差异点**：本平台额外提供 Palantir 本体语义层（对象/关系/动作）作为「工具」来源，等价于 SDK 的自定义工具 + 严格 schema；预算上限(USD) AgentScope 暂无对应，可在平台层另做配额（列入 P2）。
