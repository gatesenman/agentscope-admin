# 前端通用组件规划（基于 vue-vben-admin / Element Plus）

作为前端工程师，开工前先规划好通用组件与目录约定，保证后续各业务模块复用一致、风格统一、UI 美观。

## 一、复用 vben 既有能力（不重复造轮子）

- **页面骨架** `Page`（`@vben/common-ui`）：统一标题、描述、内容区、底部操作栏。
- **表单** `useVbenForm`（已在 `apps/web-ele/src/adapter/form.ts` 适配 Element Plus）：schema 驱动表单、校验（zod）。
- **表格** `useVbenVxeGrid`（`apps/web-ele/src/adapter/vxe-table.ts`）：基于 vxe-table 的高级表格（分页、工具栏、远程加载、操作列）。
- **弹窗/抽屉** `useVbenModal` / `useVbenDrawer`（`@vben/common-ui`）：标准化的模态与抽屉。
- **请求** `@vben/request`：已封装的 axios 实例（拦截器、错误处理、鉴权）。
- **权限** `@vben/access`、**国际化** `@vben/locales`（中/英）、**主题** `@vben/preferences`。

## 二、本项目新增的业务通用组件（`apps/web-ele/src/components/`）

| 组件 | 作用 |
| --- | --- |
| `SchemaForm` | 消费 AgentScope `GET /agent/schema` 等 **JSON Schema**，动态渲染配置表单（string/number/boolean/enum/textarea/object），用于“全部配置界面化”。 |
| `JsonSchemaField` | SchemaForm 的递归字段渲染单元（含 `format: textarea`、范围 min/max、默认值、描述 tooltip）。 |
| `StatusTag` | 统一的状态标签（草稿/已发布/已归档、active/deprecated、运行中/失败）。 |
| `PageHeaderCard` / `StatCard` | 概览页统计卡片（数字、趋势、图标）。 |
| `CodeBlock` | 集成中心代码片段展示（高亮 + 复制），用于 cURL / Python / JS SDK 示例。 |
| `EntityDrawerForm` | 列表页通用「新建/编辑」抽屉表单封装（提交、loading、校验、成功回调）。 |
| `ConfirmDeleteButton` | 危险操作二次确认按钮。 |
| `KeyValueEditor` | 任意键值对编辑（headers、metadata、credential payload）。 |
| `TagsInput` | 标签/数组输入（input_types、关键词等）。 |

## 三、AI / 对话相关组件（`apps/web-ele/src/components/ai/`）

| 组件 | 作用 |
| --- | --- |
| `ChatWindow` | 调试 Playground 的对话窗口（消息列表 + 输入框 + 发送/停止）。 |
| `MessageBubble` | 单条消息气泡（user/assistant/tool，支持 markdown、工具调用块）。 |
| `ToolCallBlock` | 展示 ReAct 过程中的工具调用与结果（可折叠）。 |
| `StreamingText` | 流式 token 渲染。 |

## 四、本体（Ontology / Palantir 风格）相关组件（`apps/web-ele/src/components/ontology/`）

| 组件 | 作用 |
| --- | --- |
| `OntologyGraph` | 对象类型 + 关系的可视化图（节点=对象类型，边=Link 关系）。 |
| `ObjectTypeCard` | 对象类型卡片（属性数量、关系、绑定的动作）。 |
| `PropertyTable` | 对象属性表（名称/类型/主键/必填/描述）。 |
| `ActionTypeForm` | 动作类型定义（参数 schema、绑定对象类型、副作用）。 |
| `ObjectInstanceTable` | 对象实例数据浏览（按对象类型动态列）。 |

## 五、目录约定

```
apps/web-ele/src/
  api/agentscope/        # 后端接口封装（agent/model/credential/session/chat/ontology/...）
  components/            # 业务通用组件（见上）
    ai/  ontology/
  views/agentscope/
    dashboard/  agents/  ontology/  models/  credentials/
    sessions/  orchestration/  integration/  schedules/  workspace/  playground/
  router/routes/modules/agentscope.ts
  locales/langs/{zh-CN,en-US}/agentscope.json
  store/agentscope/      # 必要的 pinia store
```

## 六、设计规范

- 统一使用 `Page` 包裹，主操作放右上角，危险操作二次确认。
- 列表页：搜索区（VbenForm）+ 表格（VbenVxeGrid）+ 抽屉表单，分页统一。
- 配置页：左侧导航 Tab + 右侧 SchemaForm，保存/重置固定底部。
- 颜色与图标遵循 vben 主题变量，状态色统一（成功=绿、警告=橙、危险=红、信息=蓝）。
- 中英双语，所有文案走 i18n。
