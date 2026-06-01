# 路线图与缺口 / Roadmap & Gaps

以「资深 AI 智能体研究员」视角，对照行业共识（Dify / Coze / LangGraph / Claude Agent SDK / OpenAI Assistants）、AgentScope 框架已支持但平台尚未配置化的能力，以及 B 端平台应有的工程/治理能力，给出已完成与待补清单。

## 已完成（本平台已具备）

- 智能体生命周期、模型配置、权限模式（对齐 Claude SDK `permission_mode`）
- Palantir 风格本体 + 两组关键映射（属性↔列、动作↔连接器）
- 工作流编排（Dify 全节点 + 本体节点）、知识库 + 流水线编排 + 召回测试
- 多智能体编排（6 模式）、发布（Web App / REST / 嵌入 + API Key）
- MCP 服务器管理、人在环工具确认、可观测性 v1（用量/成本 + 执行链路 trace）、多租户/RBAC 骨架、定时任务
- **工作流深化（第 4 阶段，对齐行业标准）**：节点错误处理+重试（Dify error-handling）、LLM 结构化 JSON 输出（Dify/OpenAI）、知识检索高级参数（Top-K / score 阈值 / 方式覆盖）、变量体系（sys/env/conversation）、单节点试运行 + 必填项校验（Dify step-debug 体验）

## P0（建议优先，性价比最高）

| 项 | 说明 | 状态 |
| --- | --- | --- |
| MCP 服务器管理 | `/workspace/mcp` 配置化 | ✅ 已完成 |
| 人在环工具确认 | 调试台识别 `REQUIRE_USER_CONFIRM` 并放行/拒绝 | ✅ 已完成 |
| 可观测性 v1 | 用量/成本 + 会话级执行链路 trace | ✅ 已完成 |
| 多租户/RBAC 骨架 | 用户 + 角色 + owner 归属 | ✅ 骨架完成 |

## P1（行业共识 / 框架已支持）

- 逐工具权限规则页（permission 引擎 ALLOW/DENY/ASK）
- 工作区/沙箱（Docker/E2B，会话绑定 `workspace_id`）
- 技能 Skills 页（`/workspace/skill`）、后台长任务监控（`/background-tasks`）
- 限流/配额/成本上限、审计日志、评测/回归
- 智能体版本管理与回滚（工作流变量体系 env/conversation/sys 已完成）
- Embedding 真实向量检索（现为 hash 向量 / TF-IDF）

## P2

- 护栏/内容安全、提示词库、自定义工具注册表、Webhook
- 长期记忆、标注反馈、导入导出
- 多模态输入、模型层 `max_retries`/高级参数、结构化输出 `summary_schema`

> 注：本页为规划性内容，描述方向与优先级；具体实现以仓库实际代码与提交为准。
