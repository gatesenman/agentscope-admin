# 工作流编排 / Workflow

Dify 风格的可视化 DAG 工作流：前端用 Vue Flow 画布编辑节点/连线，后端 `app/workflow/engine.py` 做拓扑排序并按 SSE 流式逐节点执行。

- 模型：`Workflow.graph`（`{nodes:[...], edges:[...]}`）。
- 端点：`GET/POST /admin/workflows/`、`GET/PATCH/DELETE /admin/workflows/{id}`、`POST /admin/workflows/{id}/run`。
- 前端：`apps/web-ele/src/views/agentscope/workflow/{index,editor,FlowNode}.vue`。

## 节点目录（覆盖 Dify 全节点 + 本体节点）

| 分类 | 节点 | type | 说明 |
| --- | --- | --- | --- |
| 输入/触发 | Webhook 触发 | `trigger-webhook` | |
| | 定时触发 | `trigger-schedule` | |
| | 开始 | `start` | 定义输入变量 |
| AI | LLM | `llm` | 调用大模型，支持系统/用户提示词与模型参数 |
| | 智能体 | `agent` | 调用一个已配置的智能体 |
| | 问题分类器 | `question-classifier` | 多分支：每个类别一个输出分支 |
| | 参数提取 | `parameter-extractor` | 按 schema 从文本抽取结构化参数 |
| 知识/数据 | 知识检索 | `knowledge` | 检索知识库，输出命中片段 |
| | 知识写入 | `knowledge-index` | 写入/索引到知识库 |
| | 数据源 | `datasource` | 提供文本/文件等数据 |
| | 文档提取 | `document-extractor` | 从文档抽取文本 |
| | **本体操作** | `ontology` | query / traverse / execute_action（Palantir 风格） |
| 逻辑 | 条件分支 | `condition` | IF/ELSE，多条件 |
| | 代码执行 | `code` | Python/JS 代码（CodeMirror 编辑器） |
| | 模板转换 | `template` | 变量插值模板 |
| | HTTP 请求 | `http-request` | 调用外部 HTTP（JSON 编辑器配 body） |
| | 工具 | `tool` | 调用内置/外部工具 |
| | 列表操作 | `list-operator` | 过滤/排序/切片列表 |
| 流程 | 迭代 | `iteration` | 对列表逐项执行子流程 |
| | 循环 | `loop` | 条件循环 |
| | 人工输入 | `human-input` | 暂停等待人工输入 |
| 变量 | 变量聚合 | `variable-aggregator` | 合并多路变量 |
| | 变量赋值 | `assigner` | 赋值/写会话变量 |
| 输出 | 回复 | `answer` | 流式回复文本 |
| | 结束 | `end` | 结束并产出最终输出 |

## 变量引用

节点输出可被下游用 `{{节点id.字段}}` 引用（如 `{{start.query}}`、`{{kb.text}}`、`{{code1.total}}`）。编辑器的「变量选择器」会列出上游节点的可用变量，避免手敲出错。

## 本体操作节点

`ontology` 节点把本体能力直接搬进工作流，操作切换时配置字段动态变化：

- `query`：对象类型 / 搜索词 / 过滤 / 数量
- `traverse`：连接类型 / 源对象 ID
- `execute_action`：动作 / 对象 ID / 参数（执行时若动作绑定连接器则写回外部）

## 运行调试

「运行」抽屉以 Dify 风格逐节点显示输出：每个节点完成后内联打印其输出（文本或格式化 JSON），便于调试数据如何在节点间流转。例如：
`start{n:"4"} → code1{squares:[1,4,9,16],total:30} → tpl1「平方序列=… 平方和=30」→ 最终回复`。

## 节点配置控件（按类型匹配）

- 代码 → CodeMirror 代码编辑器（语法高亮、行号、语言切换）
- JSON 类（HTTP body、工具参数、提取 schema）→ JSON 编辑器（高亮 + 格式化 + 校验）
- 变量/表达式 → 表达式输入框 + 上游变量自动补全
- 选择/数值/布尔/密钥 → 下拉 / 步进 / 开关 / 凭证选择器

复用组件见 `apps/web-ele/src/views/agentscope/components/`：`CodeEditor.vue`、`JsonEditor.vue`、`VarInput.vue`、`PanelSection.vue`。

## 节点错误处理与重试（对齐 Dify error-handling）

每个执行型节点都有「错误处理与重试」分组，可配置：

- **失败重试次数 / 重试间隔**：节点抛错时按次数与间隔重跑。
- **重试用尽后的策略 `error_strategy`**：
  - `fail`（默认）：终止整个工作流并报错。
  - `default`：用配置的「默认输出值」兜底，流程继续往下跑。
  - `branch`：走该节点的 `fail` 失败分支（需在画布上连出失败边）。

引擎实现见 `engine.py` 的 `_run()` 重试循环（包裹 `_dispatch_node()`）；运行抽屉会展示「重试中 / 出错」事件。三种策略均经真机验证。

## LLM 节点结构化 JSON 输出（对齐 Dify / OpenAI structured output）

LLM 节点「输出」分组可切换输出格式：

- `text`（默认）：输出纯文本，引用 `{{节点.text}}`。
- `json`（结构化）：给出 JSON Schema 后，模型按约束输出；引擎用容错解析（`_parse_json_lenient`，兼容 ```json ``` 围栏 / 前后缀噪声），解析结果挂在 `{{节点.json}}`，且字典的各字段提升到顶层可直接 `{{节点.字段名}}` 引用。解析失败时写 `error` 触发错误处理策略。

真机验证：抽取 `{name:张三, age:28, city:上海, job:工程师}`，下游用 `{{llm.name}}` 等逐字段正确注入。

## 工作流变量体系（对齐 Dify 三类变量）

工作流编辑器顶部「全局变量」可维护三类命名空间，变量选择器按 `sys / env / conversation` 分组展示：

- `sys.*`：系统变量（只读），如 `sys.query`、`sys.files`，运行时由引擎注入。
- `env.*`：环境变量（只读），保存在 `graph.env_variables`，用于密钥/常量等。
- `conversation.*`：会话变量（可写），保存在 `graph.conversation_variables`，可被「变量赋值 `assigner`」节点写入，跨节点保持可变状态。

引擎在运行/单节点调试前调用 `_seed_variable_namespaces()` 注入这三类命名空间。

## 单节点试运行 + 必填校验（Dify step-debug 体验）

- **单节点试运行**：配置面板点「试运行」打开调试抽屉，可单独运行某个节点而无需跑整图：
  - 「系统输入」区列出 `sys.*` 输入框。
  - 「上游变量（手动注入）」区**图感知**地预填上游节点输出字段骨架 JSON（例如下游 LLM 节点会预填 `start.query / ont.text / ont.objects / …`），手动填值即可。
  - 后端 `run_single(node_id, inputs, upstream)` 复用 `_dispatch_node()` 只执行该节点并经 SSE 回传执行日志 + 节点输出。
  - 端点：`POST /admin/workflows/{id}/run-node`；前端 `runWorkflowNode()`（`api/agentscope/workflow.ts`）。
- **必填项校验高亮**：配置面板顶部按节点类型列出缺失的必填项（如 LLM 节点缺 `credential_id`/`model`），随配置变更实时重算（`missingFields` 计算属性 + `requiredFieldsFor()` 规则）。
