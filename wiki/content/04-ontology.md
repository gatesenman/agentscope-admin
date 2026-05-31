# 本体与语义层 / Ontology

平台的核心抽象，对齐 **Palantir Foundry Ontology**。智能体绑定本体后，即可基于语义做**查询**与**操作**（含连接器写回外部系统），而不必直接面对底层数据表与外部 API。

## 1. 概念分层（自上而下）

```
本体 Ontology  ── 命名空间，聚合下面所有定义
│
├── 数据源 Datasource        ← 对象类型的「后端数据来源」(dataset / REST / SQL / inline)
│      └── 列 Columns         (name, data_type)
│
├── 连接器 Connector          ← 外部系统(rest/webhook/sql/internal)，动作借它把变更写回
│      └── 操作 Operation      (api_name, method, path, params)
│
├── 对象类型 ObjectType       ← 一类实体（“类”），backing = 某个 Datasource + 表
│      └── 对象属性 PropertyType   ← 字段；每个属性映射到 Datasource 的一列 (column_mapping)
│
├── 连接类型 LinkType         ← 两个对象类型之间关系的「定义/Schema」(含基数 cardinality)
│
├── 动作类型 ActionType       ← 对对象的参数化操作(create/modify/delete/custom)；
│                               可绑定 Connector 的某个 Operation（写回外部）
│
└── 实例层（运行期数据）
       ├── 对象实例 ObjectInstance   ← 对象类型的一行具体数据(properties)
       └── 对象关系 LinkInstance      ← 连接类型的一条具体边(source → target)
```

## 2. 六个核心概念

| 概念 | 角色 | 类比(关系库) | 类比(Palantir) |
| --- | --- | --- | --- |
| **本体 Ontology** | 命名空间，一套语义模型 | database / schema | Ontology |
| **对象类型 ObjectType** | 实体的“类” | 表 (table) | Object Type |
| **对象属性 PropertyType** | 对象类型上的字段 | 列 (column) | Property |
| **连接类型 LinkType** | 两类对象间关系的**定义** | 外键约束/关联定义 | Link Type |
| **对象关系 LinkInstance** | 关系的**实例**（一条边） | 关联表里的一行 | Link |
| **动作类型 ActionType** | 对对象的参数化写操作 | 存储过程/写事务 | Action Type |

> 「连接类型」与「对象关系」是同一关系的两层：连接类型是 schema 级定义（谁连谁、基数），对象关系是其运行期实例。

## 3. 两组关键映射（平台的精髓）

### 3.1 对象属性 ↔ 数据集字段（Property ↔ Dataset Column）

每个对象类型由一个数据源支撑；对象类型的每个属性映射到该数据源的某一列：

```
ObjectType(account)  ──backing──>  Datasource(core_banking, kind=sql, table=ACCOUNTS)
   PropertyType(account_no)  ──column_mapping──>  列 "ACCT_NO"
   PropertyType(balance)     ──column_mapping──>  列 "BAL_AMT"
   PropertyType(status)      ──column_mapping──>  列 "ACCT_STATUS"
```

- 作用：让对象具备**数据血缘/出处**，查询结果可追溯到来源列。
- 模型字段：`ObjectType.datasource_id` + `ObjectType.backing_table`；`PropertyType.column_mapping`。

### 3.2 动作类型 ↔ 连接器操作（Action ↔ Connector Operation）

动作类型除了在本体内部 create/modify/delete，还能绑定一个连接器的具体操作，把变更**写回外部系统**：

```
ActionType(freeze_account)  ──>  Connector(payments_core, kind=rest)
                                   └─ Operation: "freeze"  POST /accounts/{id}/freeze
   parameter_bindings: { reason -> "freeze_reason" }     # 动作参数 → 操作字段
```

执行 `freeze_account` 时：① 本体内把账户 status 改为 frozen；② 调用 payments_core 的 freeze 操作写回，结果记入 `connector_result`（写回失败不阻断本体变更）。

- 模型字段：`ActionType.connector_id` + `connector_operation` + `parameter_bindings`。

## 4. 智能体如何「语义查询 + 语义操作」

绑定本体后注入到智能体的工具（见 `app/ontology/tools.py`）：

| 工具 | 作用 |
| --- | --- |
| `ontology_list_object_types` | 发现有哪些对象类型/属性（含数据源来源与列映射），先调它了解数据 |
| `ontology_query_objects` | 按对象类型 + 过滤/搜索做语义查询 |
| `ontology_traverse_link` | 沿连接类型遍历到关联对象 |
| `ontology_list_actions` | 发现可执行的动作 + 参数 + 连接器写回映射 |
| `ontology_execute_action` | 执行动作：内部改图 +（若绑定）经连接器写回外部 |

典型语义任务：

> “冻结风险评分>0.8 的电汇交易对应的收款账户，并在工单系统立案。”
> → list → query(交易) → traverse(收款账户) → execute_action(freeze_account，经 payments_core 写回) → execute_action(open_investigation，经 case_management 建单)。

## 5. 标准数据：企业风控本体

seed 脚本 `server/scripts/seed_risk_ontology.py` 会灌入一套自洽的「企业风控」本体：组织 / 人员 / 账户 / 交易 / 订单 / 产品 / 供应商 / 制裁名单 / 风险事件等 9 个对象类型，4 个数据源、4 个连接器、5 个动作（其中 4 个绑定连接器写回），以及对象/关系实例。

运行：

```bash
cd server && python scripts/seed_risk_ontology.py
# 或经 CLI：
agentscope-admin seed --risk-ontology
```

> 重要：seed 是**幂等**的——重灌时会级联删除旧本体的全部子表（对象类型/实例/属性/动作/数据源/连接器），并自动把指向旧本体的智能体绑定重新指到新本体，避免出现「智能体绑在已删本体上、读到孤儿数据」的问题（见 commit `c0abf6c`）。

## 6. 前端本体管理页

`apps/web-ele/src/views/agentscope/ontology/index.vue`：

- 对象类型表显示所属**数据源/数据表**；展开行显示属性 ↔ 字段映射（如 交易 `amount→AMT`、`risk_score→RISK_SCORE`）。
- 动作类型表的「写回操作」列（如 `aml_engine.flag`、`payments_core.freeze`；未绑定显示「仅本体内部」）。
- 「数据源」「连接器」Tab 分别展示各自的列 / 操作定义。
- 本体关系图（`GET /ontology/{id}/graph`）。
