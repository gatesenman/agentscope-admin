# 概览 / Overview

**AgentScope Admin** 是一个面向 B 端的智能体（Agent）全生命周期管理后台，核心特色是内置一套 **Palantir 风格的本体 / 语义层（Ontology）**，智能体绑定本体后即可进行精确的语义查询与动作执行（含连接器写回外部系统）。

- 前端：基于 [vue-vben-admin](https://github.com/vbenjs/vue-vben-admin)（Element Plus 版，`apps/web-ele`），Vue 3 + TypeScript + Vite。
- 后端：真实的 FastAPI 服务，直接构建在 AgentScope 的应用层（`agentscope.app`）之上——不是 mock。
- 持久化：AgentScope 自身状态（智能体 / 会话 / 凭证）走内置 `RedisStorage` + `LocalWorkspaceManager`；本体 / 知识库 / 工作流 / 发布应用等存于 SQLite（SQLModel）。

> 本 wiki 为**静态站点**：所有页面都是预渲染的 HTML，可直接用浏览器离线打开 `wiki/index.html`，无需启动任何服务。

## 能力总览（功能支柱）

| 支柱 | 说明 | 后端模块 | 前端页面 |
| --- | --- | --- | --- |
| 智能体生命周期 | 基于后端 JSON Schema 动态渲染表单，创建/编辑/删除智能体 | `agentscope.app` + `agent_profile` | `agents/` |
| 本体 / 语义层 | 对象类型/属性/连接类型/动作类型/实例 + 数据源 & 连接器映射 | `ontology` | `ontology/` |
| 模型配置 | 每个智能体的默认凭证/模型、生成参数、兜底模型、权限模式 | `agent_profile` | 智能体抽屉「模型配置」 |
| 凭证与模型 | LLM 厂商凭证（OpenAI/DashScope/DeepSeek/Anthropic…）管理 | `agentscope.app` | `credentials/` |
| 调试台 Playground | SSE 流式对话 + 工具调用/思考链 + 人在环工具确认 | `chat` | `sessions/` |
| 多智能体编排 | 6 种行业标准模式（顺序/并行/聚合/路由/主管-工人/交接） | `orchestration` | `orchestration/` |
| 工作流编排 | Dify 全节点 DAG 画布（含本体操作节点）+ 拓扑 SSE 执行 | `workflow` | `workflow/` |
| 知识库 + 流水线编排 | 分块策略 × 索引方式 + 可视化流水线 + 召回测试 | `knowledge` | `knowledge/` |
| 发布 | 将智能体冻结为公开 App（Web App / REST / 嵌入）+ API Key | `publish` | `publish/`, `webapp/` |
| MCP 服务器 | stdio/http MCP 注册表 + 工具开关 + 连通测试 | `mcp_registry` | `mcp/` |
| 可观测性 | Token 用量/成本 + 按智能体→会话→执行链路 trace 下钻 | `observability` | `observability/` |
| 多租户 / RBAC | 用户 + admin/editor/viewer 角色 + 按 owner 归属隔离 | `rbac` | `users/` |
| 定时任务 | cron 调度（基于 AgentScope `/schedule`） | `agentscope.app` | `schedules/` |
| 看板 | 跨智能体/凭证/会话/本体的聚合统计 | `dashboard` | `dashboard/` |

## 技术栈

- **前端**：Vue 3、TypeScript、Element Plus、Vue Flow（画布）、CodeMirror（代码编辑器）、Vite、pnpm monorepo（Turborepo）。
- **后端**：Python 3.12、FastAPI、SQLModel（SQLite）、AgentScope 2.0.0、Redis。
- **LLM**：默认对接 DeepSeek（兼容 OpenAI 接口），亦支持 DashScope / OpenAI / Anthropic 等。

## 阅读路线

1. 先看 [架构](02-architecture.html) 了解前后端如何组合与数据如何流转。
2. 看 [本体与语义层](04-ontology.html) 理解平台的核心抽象与两组关键映射。
3. 需要二次开发，直接跳到 [二次开发指南](12-developer-guide.html)（新增节点/接口/页面的配方）。
4. 需要查接口，见 [API 参考](11-api-reference.html)。
