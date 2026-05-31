# 二次开发指南 / Developer Guide

面向「在本项目上继续开发（含 AI 续接）」的实操配方。更完整版本见仓库根的 `DEVELOPER.md`。

## 约定

- 后端共享 SQLite 会话依赖：`from ..ontology.db import get_session`。
- 调用方身份：通过 `X-User-ID` 头读取（见 `publish/router.py` 的 `_owner` 依赖），业务表以 `owner_user_id` 归属隔离。
- 前端每个后端模块对应一个强类型客户端 `apps/web-ele/src/api/agentscope/<module>.ts`，并从 `index.ts` 再导出。
- 流式接口统一走 SSE；前端用 `fetch` + `ReadableStream` 解析。

## 配方 1：新增一个工作流节点类型

以新增 `http` 节点（GET 一个 URL，输出 `{{<id>.text}}`）为例。

**后端**（`server/app/workflow/engine.py`）—— 第一步：在 `run()` 里新增分支：

```python
elif ntype == "http":
    output = self._run_http(data)
```

第二步：实现 runner（接收节点 `data`，返回写入 `self.context[nid]` 的 `output`）：

```python
def _run_http(self, data: dict[str, Any]) -> dict[str, Any]:
    import requests
    url = _resolve(data.get("url", ""), self.context)
    resp = requests.get(url, timeout=30)
    return {"text": resp.text, "status": resp.status_code}
```

若节点需向 UI 流式输出文本，参考 `_run_llm`：写成 async 生成器，yield `(frame, text)`，`frame` 为 `_event({"type":"text_delta","node_id":nid,"delta":...})`。

**前端**（`workflow/`）：① 在 `FlowNode.vue` 的 `META` 注册该 type 的颜色/图标/标签；② 在 `editor.vue` 的左侧节点面板与右侧配置面板加入它（小表单，绑定到 `node.data`）。

> 节点配置是图里的自由 JSON，无需数据库迁移。

## 配方 2：新增一个后端接口 / 功能模块

新增功能域 `foo` 的步骤：

1. 建 `server/app/foo/{__init__.py,models.py,router.py}`。
2. `models.py` 定义 SQLModel 表（`class Foo(SQLModel, table=True)`）。
3. `router.py` 定义路由（见下方代码）。
4. 在 `server/app/main.py` 挂载：`from .foo.router import router as foo_router` 后 `app.include_router(foo_router)`。
5. **确保建表**：`server/app/ontology/db.py:init_db()` 要 import 到 `app.foo.models`（它统一 import 所有模型模块以补全 metadata）。
6. 加前端客户端 `apps/web-ele/src/api/agentscope/foo.ts` 并从 `index.ts` 再导出。

`router.py` 范式：

```python
from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from ..ontology.db import get_session

router = APIRouter(prefix="/admin/foos", tags=["foo"])

@router.get("/")
def list_foos(session: Session = Depends(get_session)) -> dict:
    rows = list(session.exec(select(Foo)))
    return {"items": rows, "total": len(rows)}
```

## 配方 3：新增一个后台页面（前端）

1. 建 `apps/web-ele/src/views/agentscope/foo/index.vue`。
2. 在 `src/router/routes/modules/agentscope.ts` 加路由 + 菜单项。
3. 在 `locales/langs/zh-CN/agentscope.json` 与 `en-US/agentscope.json` 同步 i18n key（标题用 `$t('agentscope.menu.foo')`）。
4. 用 `foo.ts` 客户端取数；复用 `SchemaForm.vue`、`StatusTag.vue` 与 Element Plus 的 `el-table`/`el-drawer`/`el-dialog`（参考 `views/agentscope/agents/index.vue` 范式）。

## 配方 4：知识库流水线与检索

知识库由「分块策略 × 索引方式」决定；`build_pipeline()`（`knowledge/pipeline.py`）据此派生阶段列表，前端 `buildPreview()` 镜像同一逻辑做实时预览。阶段：`extract → clean → split|split_parent_child → [embed|build_graph] → index`。

- `keyword` → 仅 TF-IDF；`vector` → `embed`（hash 256 维 L2 向量，无外部依赖）；`knowledge_graph` → `build_graph`（`graph.py` 用 LLM 抽三元组，需 `kg_credential_id`/`kg_model`）；`hybrid` → graph + keyword 混合。
- 召回测试 `POST /admin/knowledge-bases/{id}/retrieve` 按方式返回分数/父块上下文/三元组，可按查询覆盖方式。

## 配方 5：新增一个多智能体编排模式

在 `orchestration/engine.py` 为新 `pattern` 增加协调逻辑分支，并在 `GET /admin/orchestrations/patterns` 暴露元信息；前端编排页根据 pattern 渲染对应的成员/协调器配置。

## CLI

`agentscope-admin`（`server/app/cli.py`）：`serve`（起服务）、`seed`（灌数据，含 `--risk-ontology`）、`agents`、`knowledge`、`workflow`、`publish`、`keys` 等子命令。详见 [运行与开发](14-running.html)。

## 本地开发回路

```bash
./start-dev.sh            # 后端(:8000) + 前端(:5777)
./start-dev.sh --seed     # 顺带灌入风控本体
cd server && ./start.sh   # 仅后端
cd server && ./seed.sh    # 仅灌数据
# 校验：后端 ruff/格式化；前端 pnpm -F @vben/web-ele typecheck / lint
```
