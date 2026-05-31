# 数据模型 / Data Model

本页汇总平台扩展部分（SQLite / SQLModel）的全部数据表。AgentScope 自身的智能体 / 会话 / 凭证由其内置存储管理，不在此列。

> 约定：所有表的主键 `id` 默认是 32 位十六进制 UUID；带 JSON 的字段以 `dict`/`list` 形式存于 SQLite 的 JSON 列；多数业务表带 `owner_user_id` 用于归属隔离。

## 本体相关（`app/ontology/models.py`）

### Ontology — 本体（命名空间）
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | str(PK) | |
| api_name | str(unique) | 程序名（唯一） |
| display_name | str | 展示名 |
| description | str | 描述 |
| created_at / updated_at | datetime | |

### Datasource — 数据源（对象类型的数据出处）
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | str(PK) | |
| ontology_id | FK→ontology | 所属本体 |
| api_name / display_name / description | str | |
| kind | enum | `dataset` / `rest_api` / `sql` / `inline` |
| connection | json | 连接细节（按 kind：dataset→path/format，rest→base_url/path，sql→dsn/table） |
| columns | json[] | 字段 schema：`[{"name":"AMT","data_type":"double"}, ...]` |

### Connector — 连接器（动作写回的外部系统）
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | str(PK) | |
| ontology_id | FK→ontology | |
| api_name / display_name / description | str | |
| kind | enum | `rest` / `webhook` / `sql` / `internal` |
| config | json | 连接级配置：base_url / headers / auth |
| operations | json[] | 命名操作：`[{"api_name":"freeze","method":"POST","path":"...","params":["reason"]}]` |

### ObjectType — 对象类型
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | str(PK) | |
| ontology_id | FK→ontology | |
| api_name / display_name / description | str | |
| icon / color | str | 展示用 |
| primary_key_property | str | 主键属性（默认 `id`） |
| title_property | str? | 标题属性 |
| **datasource_id** | FK→datasource? | 背靠的数据源（数据血缘） |
| **backing_table** | str | 数据源内具体表/对象 |

### PropertyType — 对象属性
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | str(PK) | |
| object_type_id | FK→object_type | |
| api_name / display_name | str | |
| data_type | enum | string/integer/double/boolean/date/timestamp/geo_point/array |
| required / is_primary_key / is_title | bool | |
| sort_order | int | |
| **column_mapping** | str | 映射到数据源的列名（空=与 api_name 同名） |

### LinkType — 连接类型（关系定义）
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | str(PK) | |
| ontology_id | FK→ontology | |
| api_name / display_name / description | str | |
| source_object_type_id / target_object_type_id | FK→object_type | 两端对象类型 |
| cardinality | enum | one_to_one / one_to_many / many_to_many |

### ActionType — 动作类型
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | str(PK) | |
| ontology_id | FK→ontology | |
| api_name / display_name / description | str | |
| object_type_id | FK→object_type? | 作用对象类型 |
| effect | enum | create / modify / delete / custom |
| parameters | json | 动作参数 schema |
| **connector_id** | FK→connector? | 写回目标连接器（可空=仅本体内部） |
| **connector_operation** | str | 连接器操作 api_name |
| **parameter_bindings** | json | 动作参数→操作字段映射（action_param→operation_field） |

### ObjectInstance / LinkInstance — 实例与关系
- `ObjectInstance`：某对象类型的一条具体记录，`properties` 为 JSON。
- `LinkInstance`：`link_type_id` + `source_object_id` + `target_object_id` 三元组。

### AgentBinding — 智能体↔本体绑定
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| agent_id | str(PK) | AgentScope 智能体 ID |
| ontology_id | FK→ontology | 绑定的本体 |
| enabled | bool | |
| allowed_object_types / allowed_actions | json[] | 允许清单（空=全部） |

## 知识库相关（`app/knowledge/models.py`）

- **KnowledgeBase**：`chunk_strategy`（general/parent_child）× `index_method`（keyword/vector/knowledge_graph/hybrid），`pipeline` 为可视化流水线阶段列表，含 `top_k`/`score_threshold`，知识图谱方式还带 `kg_credential_id`/`kg_model`。
- **Document**：原文 + `status`/`chunk_count`/`triple_count`。
- **Chunk**：分块文本，含 `term_freq`（关键词）、`embedding`（向量）、`parent_id`/`is_parent`（父子分块）。
- **KnowledgeTriple**：知识图谱三元组 `subject`/`predicate`/`object`。

## 其它模块

- **Workflow**（`app/workflow/models.py`）：`graph`（nodes/edges 的 JSON DAG）+ `owner_user_id` + `enabled`。
- **Orchestration**（`app/orchestration/models.py`）：`pattern`（6 选 1）+ `config`（members / coordinator / max_rounds）。
- **PublishedApp / AppApiKey**（`app/publish/models.py`）：公开 token、运行配置快照、开场白/建议问题、`allowed_origins`/`rate_limit_per_min`；API Key 存 SHA-256 哈希，仅创建时明文显示一次。
- **McpServer**（`app/mcp_registry/models.py`）：transport（stdio/http）、command/args/env 或 url/headers、工具 allow/deny、健康状态。
- **UsageLog / TraceSpan**（`app/observability/models.py`）：token 用量与执行链路 span。
- **User**（`app/rbac/models.py`）：username + role（admin/editor/viewer）。
- **AgentProfile**（`app/agent_profile/models.py`）：默认凭证/模型、生成参数、兜底模型、`permission_mode`、`stream`。
- **UserPreferences**（`app/preferences/models.py`）：前端偏好。

## 关系图（核心本体）

```
Ontology 1───* ObjectType *───1 Datasource
   │              │  *
   │              │  └── PropertyType  ── column_mapping ──▶ Datasource.columns[]
   │              *
   ├──* LinkType (source/target → ObjectType)
   ├──* ActionType ── connector_id/operation ──▶ Connector.operations[]
   ├──* Datasource
   ├──* Connector
   *
ObjectInstance *──* ObjectInstance  (via LinkInstance / LinkType)

AgentBinding: agent_id ──▶ Ontology
```
