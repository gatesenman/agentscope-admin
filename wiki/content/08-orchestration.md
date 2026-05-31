# 多智能体编排 / Multi-Agent Orchestration

把一组「成员」（agent persona，各带模型配置与指令）置于某种**协作模式**下协同。后端 `app/orchestration/engine.py`（SSE 引擎），前端 `apps/web-ele/src/views/agentscope/orchestration/index.vue`（实时协作面板）。

- 模型：`Orchestration.pattern` + `config`（`members[]` / `coordinator` / `max_rounds`）。
- 端点：`GET/POST /admin/orchestrations/`、`GET/PATCH/DELETE /admin/orchestrations/{id}`、`GET /admin/orchestrations/patterns`、`POST /admin/orchestrations/{id}/run`。

## 六种行业标准模式

| 模式 | 说明 |
| --- | --- |
| `sequential` | 流水线：每个成员在上一个输出上继续精炼。 |
| `parallel` | 扇出：同一任务并发分发给每个成员。 |
| `aggregation` | 并行扇出后，由一个聚合 LLM 综合所有成员输出为一个答案。 |
| `router` | 路由 LLM 选出最合适的单个成员来处理任务。 |
| `supervisor` | 主管 LLM 迭代地把子任务委派给工人成员，直到产出最终答案（主管-工人/编排者-工人）。 |
| `handoff` | 成员之间相互交接控制权（swarm），直到某成员标记完成或达到 `max_rounds`。 |

## 成员与协调器配置

- **成员 member**：`name` / `role` / `instruction` / `credential_id` / `type` / `model` / `parameters`。
- **协调器 coordinator**（用于 aggregation / router / supervisor）：自己的凭证/模型/参数 + 调度指令。
- `max_rounds`：handoff / supervisor 的最大轮数。

## 运行

`POST /admin/orchestrations/{id}/run` 返回 SSE：实时转写各成员输出，并在聚合/路由/主管模式下产出最终答案。前端协作面板按成员着色显示发言时间线。

> 实测：并行模式下「研究员 + 撰写者」两成员经 DeepSeek 流式输出并聚合最终答案。
