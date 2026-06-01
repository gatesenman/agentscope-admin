# 知识库与流水线编排 / Knowledge & Pipeline

知识库支持按行业标准选择**制作方式**，并提供可视化的**流水线编排**与**召回测试**。后端在 `app/knowledge/`（`service.py` 摄取、`pipeline.py` 流水线、`graph.py` 知识图谱、`tools.py` 智能体工具）。

- 端点前缀：`/admin/knowledge-bases`
- 前端：`apps/web-ele/src/views/agentscope/knowledge/{index,pipeline,PipelineNode}.vue`

## 制作方式：分块策略 × 索引方式

创建知识库时二维选择：

**分块策略 `chunk_strategy`**
- `general`：通用分块（chunk_size / overlap / separator）
- `parent_child`：父子分块（大父块给上下文、小子块用于检索）

**索引方式 `index_method`**
- `keyword`：关键词（TF-IDF 词频）
- `vector`：向量嵌入（embedding）
- `knowledge_graph`：语义知识图谱（用 LLM 抽取实体/关系三元组，GraphRAG 风格）
- `hybrid`：混合（关键词 + 向量）

> 选择知识图谱方式时，会出现抽取用的凭证/模型字段（`kg_credential_id` / `kg_model`）。

## 流水线（Pipeline）

`build_pipeline(chunk_strategy, index_method)` 根据上面两维派生出阶段列表，前端按这个列表渲染可视化链路；摄取（`service.ingest_document`）严格按同一列表执行，做到「所见即所跑」：

```
提取文本 → 清洗 → [通用分块 | 父子分块] → (向量嵌入?) → (语义知识图谱?) → 建立索引
```

- 向量 / 混合方式追加「向量嵌入」阶段。
- 知识图谱方式追加「语义知识图谱（抽三元组）」阶段。

每个知识库可在管理抽屉打开「流水线编排」（Vue Flow 节点链：数据源 → 提取 → 清洗 → 分块/父子 → QA → 嵌入/建图 → 索引），保存即重建索引。

## 召回测试

`POST /admin/knowledge-bases/{kb_id}/retrieve`：按当前方式返回命中片段、分数、父块上下文（父子分块）、三元组（知识图谱）。前端「召回测试」面板可切换方式查看效果。

## 工作流知识检索节点的高级参数（对齐 RAG 标准）

工作流 `knowledge`（知识检索）节点支持检索高级参数，对齐行业 RAG 实践：

- **检索方式覆盖 `retrieval_method`**：可在节点层覆盖知识库默认方式（关键词 / 向量 / 知识图谱 / 混合），切换会改变命中排序。
- **Top-K `top_k`**：返回的最大命中片段数。
- **Score 阈值 `score_threshold`**：过滤低于阈值的低相关命中（如 `0.5` 会过滤掉 0.336 的弱命中）。

真机验证：同一查询在 关键词(0.3361)/向量(0.3550)/混合(0.3456) 下分数不同；设 `score_threshold=0.5` 时命中数由 1 降为 0。

## 文档与重建索引

| 操作 | 端点 |
| --- | --- |
| 列文档 / 加文档 | `GET/POST /admin/knowledge-bases/{kb_id}/documents` |
| 删文档 | `DELETE .../documents/{doc_id}` |
| 重建单文档 | `POST .../documents/{doc_id}/reindex` |
| 重建全部 | `POST /admin/knowledge-bases/{kb_id}/reindex` |
| 列分块 / 三元组 | `GET .../chunks`、`GET .../triples` |

## 作为智能体工具与工作流节点复用

同一套检索能力以三种方式复用：

1. 智能体工具 `knowledge_search`（按 owner 限定可见知识库）。
2. 工作流 `knowledge` 节点（知识检索）/ `knowledge-index` 节点（知识写入）。
3. 知识库页面的召回测试面板。
