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
