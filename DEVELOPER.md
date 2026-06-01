# Developer Guide (AI-friendly)

This document is written so that **a developer — or an AI coding agent — can extend the platform without re-reading the whole codebase**. It explains the architecture, the data models, and gives copy-pasteable recipes for the most common extension tasks (add a workflow node, add an API endpoint, add a page, add a knowledge pipeline stage).

If you only want to _run_ the project, see [README.md](README.md) and [server/README.md](server/README.md). For the agent-config feature matrix vs. AgentScope / Claude Agent SDK, see [docs/CONFIG-ALIGNMENT.md](docs/CONFIG-ALIGNMENT.md).

---

## 1. Big picture

```
┌──────────────────────────────┐        ┌─────────────────────────────────┐
│  apps/web-ele (Vue 3 + EP)    │  HTTP  │  server (FastAPI + AgentScope)  │
│  vue-vben-admin shell         │ <────> │  agentscope.app.create_app()    │
│  src/views/agentscope/*       │  /api  │  + our routers (ontology,       │
│  src/api/agentscope/* (client)│  proxy │    knowledge, workflow, …)      │
└──────────────────────────────┘        └─────────────────────────────────┘
                                              │            │
                                     Redis (AgentScope    SQLite (ontology,
                                     agents/sessions/     knowledge, workflow,
                                     credentials)         published apps)
```

- **Frontend** is the Element Plus edition of vue-vben-admin, trimmed to a single app (`apps/web-ele`). All product code lives under the `agentscope` namespace: `src/views/agentscope/*` (pages), `src/api/agentscope/*` (typed REST client), `src/components/agentscope/*` (shared widgets).
- **Backend** builds _directly_ on AgentScope's own FastAPI app (`agentscope.app.create_app`) and mounts extra routers for the features AgentScope doesn't ship: ontology, knowledge, workflow, publishing, dashboard, preferences, agent profiles, and a compat-auth shim for the vben login shell.
- **Identity**: there is no real auth. The acting user is taken from the `X-User-ID` header (default `admin`). The frontend request layer injects it; the CLI sends it via `--user`.
- **Persistence**: AgentScope-native state (agents, sessions, credentials) is in **Redis**. Everything we added is in **SQLite** (`server/data/ontology.db`) via SQLModel. Per-agent sandboxes live under `server/data/workspaces/`.

### Directory map

```
server/app/
  main.py            create_app() + router wiring + combined agent-tool factory
  settings.py        env-driven settings (AGENTSCOPE_ADMIN_* prefix)
  cli.py             `agentscope-admin` CLI (argparse + requests)
  ontology/          Palantir-style ontology: db, models, schemas, service,
                     router, tools (agent-callable ontology tools)
  knowledge/         models, pipeline (tokenize/split/index + TF-IDF rank),
                     service, router, tools (knowledge_search agent tool)
  workflow/          models, engine (topological executor + SSE), router
  orchestration/     models, engine (6 multi-agent patterns + SSE), router
  publish/           models (PublishedApp/AppApiKey), router (admin + public)
  agent_profile/     per-agent model defaults / params / permission_mode
  preferences/       per-user vben UI preference persistence
  dashboard/         aggregate stats
  compat_auth/       minimal /auth endpoints for the vben demo shell
  scripts/           seed_risk_ontology.py, seed_knowledge_workflow.py

apps/web-ele/src/
  api/agentscope/    one .ts module per backend area; index.ts re-exports
  views/agentscope/  dashboard agents ontology credentials sessions
                     orchestration integration publish webapp schedules
                     workflow knowledge
  components/agentscope/  OntologyGraph.vue SchemaForm.vue StatusTag.vue
  router/routes/modules/agentscope.ts   menu + routes
  locales/langs/{zh-CN,en-US}/agentscope.json   i18n
```

### Conventions

- Each backend feature is a self-contained package with `models.py` (SQLModel tables), `router.py` (an `APIRouter` with a `prefix`), and optionally `service.py` / `tools.py`. Admin endpoints use the `/admin/<area>` prefix.
- Every frontend page has a matching `src/api/agentscope/<area>.ts` client. Never call `fetch`/`axios` from a `.vue` file directly — go through the client so the `X-User-ID` header and base URL are consistent.
- Tables auto-create on startup via `init_db()` in `server/app/ontology/db.py` (it imports every model module so `SQLModel.metadata` is complete). **If you add a new SQLModel table, import its module in `db.py`** or the table won't be created.

---

## 2. Data models (what lives where)

| Concept | Store | Module | Key fields |
| --- | --- | --- | --- |
| Agent | Redis | AgentScope | `name`, `system_prompt`, `context_config`, `react_config` |
| Credential | Redis | AgentScope | `type` (provider), `api_key`, `base_url` |
| Session / messages | Redis | AgentScope | per-agent chat history |
| Agent profile | SQLite | `agent_profile` | `default_provider/credential/model`, `parameters`, `fallback_*`, `permission_mode` |
| Ontology | SQLite | `ontology` | object types, properties, link types, action types, object instances, **datasources, connectors** |
| Knowledge base | SQLite | `knowledge` | `KnowledgeBase` → `Document` → `Chunk` (with `term_freq`) |
| Workflow | SQLite | `workflow` | `graph = {nodes, edges}`, `enabled` |
| Published app | SQLite | `publish` | `token`, frozen model/params/permission snapshot, `enabled` |
| API key | SQLite | `publish` | `key_prefix`, `key_hash` (SHA-256), `revoked`, `last_used_at` |
| UI preferences | SQLite | `preferences` | per-user vben theme/layout JSON |

---

## 3. Workflow engine internals

A workflow is a JSON graph: `{ "nodes": [...], "edges": [...] }`. Each node is `{ id, type, position, data }`; each edge is `{ id, source, target, sourceHandle? }`.

The executor (`server/app/workflow/engine.py`) does:

1. **Topological sort** (`_topo_order`, Kahn's algorithm) over the edges.
2. **Reachability** tracking — a node runs only if an incoming edge was "taken". `start` nodes (no incoming edges) are seeded as reachable.
3. **Per-node dispatch** in the big `if ntype == ...` block inside `run()`.
4. **Template resolution** (`_resolve`) — replaces `{{node_id.field}}` tokens using the accumulated `self.context` (e.g. `{{start.query}}`, `{{kb.text}}`, `{{llm.text}}`).
5. **Branching** — a `condition` node writes `branch[nid] = "true"|"false"`; downstream edges are only activated if their `sourceHandle` matches.

Output is **Server-Sent Events**. Frame types (field `type`): `workflow_started`, `node_started` (carries `node_id` / `title`), `text_delta`, `node_finished` (carries `node_id` + the node's full `output` dict), `workflow_finished` (carries the final `output`), `error`. The frontend client (`src/api/agentscope/workflow.ts`) and the CLI (`workflow run`) both parse these.

The editor's **Run** drawer (`editor.vue → doRun()`) renders a Dify-style per-node execution trace: each `node_started` is logged by title and each `node_finished` prints that node's output (its `text`, or pretty-printed JSON) inline, so you can debug how every node transformed the data before the final answer.

Built-in node types — the engine covers the **full Dify node catalogue** plus our Palantir-style `ontology` node:

| Group | Node types (`data.type`) |
| --- | --- |
| Entry / trigger | `start`, `trigger-webhook`, `trigger-schedule`, `trigger-plugin` |
| LLM / reasoning | `llm`, `agent`, `question-classifier`, `parameter-extractor` |
| Knowledge | `knowledge` (retrieval), `knowledge-index` (write-back), `document-extractor`, `datasource` |
| Logic / control | `condition` (IF/ELSE), `iteration`, `loop`, `variable-aggregator`, `assigner` (variable assign) |
| Transform / tools | `code`, `template`, `http-request`, `tool`, `list-operator` |
| Ontology (ours) | `ontology` (query / traverse / execute_action) |
| Human / output | `human-input`, `answer` (alias `end`) |

The `question-classifier` node emits **one output branch per class** (multi-handle: `sourceHandle` = the class label), mirroring Dify; downstream edges are gated by matching handle the same way `condition` gates `true`/`false`. Trigger nodes are treated like `start` (seeded reachable, inputs land in `self.context["start"]`).

The **`ontology`** node (Palantir-style) runs one of three operations against a bound ontology and is handled by `_run_ontology()` in `engine.py`:

- `query` — semantic search over object instances (`object_type`, `search`, `filters`, `limit`)
- `traverse` — follow a link from a source object (`link_type`, `source_object_id`)
- `execute_action` — invoke an action type, mutating instance state (`action`, `object_id`, `parameters`)

Its result is exposed as both `{{<id>.result}}` (structured) and `{{<id>.text}}` (JSON string). The editor config panel (`views/agentscope/workflow/editor.vue`) shows operation-dependent fields, driven by `selectedNode.data.operation`.

### 3b. Ontology concept model & the two mappings

The ontology mirrors Palantir Foundry. Concept relationships:

```
Ontology (本体)  ──< ObjectType (对象类型) ──< PropertyType (对象属性)
       │                  │                        │  column_mapping
       │                  │  datasource_id          ▼
       │                  └────────────────►  Datasource (数据集/字段)
       │
       ├──< LinkType (连接类型) ──► LinkInstance (对象关系, concrete edges)
       │
       └──< ActionType (动作类型) ──┐ connector_id + connector_operation
                                    │  parameter_bindings
                                    ▼
                              Connector (连接器, external operations)
```

Two mapping layers make the ontology operable by agents:

1. **对象属性 ↔ 数据集字段映射** — every `ObjectType.datasource_id` points at a `Datasource` (`kind = dataset | rest_api | sql | inline`, declares `columns`), and `ObjectType.backing_table` names the table/dataset within it. Each `PropertyType.column_mapping` maps the property to a column (empty ⇒ falls back to `api_name`). This is data lineage: where each object/property comes from.
2. **动作类型 ↔ 连接器操作映射** — an `ActionType` may bind to a `Connector` (`kind = rest | webhook | sql | internal`, exposes named `operations`) via `connector_id` + `connector_operation`, with `parameter_bindings` mapping action params → operation fields. On `execute_action`, `_invoke_connector()` (`service.py`) resolves the binding, builds the payload, and either issues a real HTTP request (REST/webhook with a reachable `base_url`) or returns a deterministic `simulated` record (when `config.simulate` is set or no base_url). The connector call never aborts the ontology mutation; its outcome is appended as `connector_result`.

CRUD lives under `/ontology/{oid}/datasources` and `/ontology/{oid}/connectors`. Agents discover all of this through tools (`server/app/ontology/tools.py`): `ontology_list_object_types` now reports the backing datasource + per-property `column`, and the new `ontology_list_actions` reports each action's `writes_back_to` connector/operation. Seed a self-consistent example with `scripts/seed_risk_ontology.py`.

### 3c. Workflow variable system (system / environment / conversation)

Beyond `{{<node>.<field>}}` references to upstream node outputs, a workflow exposes three Dify-style built-in variable scopes, seeded into the run context by `WorkflowEngine._seed_variable_namespaces()` before any node runs:

| Scope | Reference | Source | Mutable |
| --- | --- | --- | --- |
| System | `{{sys.query}}`, `{{sys.files}}`, `{{sys.user_id}}`, `{{sys.workflow_id}}`, `{{sys.workflow_run_id}}` | injected at run time from the request inputs / engine | no |
| Environment | `{{env.<name>}}` | `graph.environment_variables` (`[{name, value, type}]`, `type ∈ string\|number\|secret`) | no (read-only config / secrets) |
| Conversation | `{{conversation.<name>}}` | `graph.conversation_variables` (`[{name, value, type}]`, `type ∈ string\|number\|json`) | yes — the `assigner` node writes them |

- `_coerce_var_list()` (engine.py) turns each list into a `name → value` dict, coercing `number` to int/float and parsing `json` values. Environment vars are read-only; conversation vars start at their declared defaults.
- The **`assigner`** node writes to the conversation scope when an assignment target is prefixed `conversation.<name>` (`_run_assigner`), so state can be carried/updated across the run; non-prefixed targets stay at the top level (`{{<name>}}`).
- The editor manages both lists in the **全局变量** drawer (`editor.vue`); they are persisted on `graph.environment_variables` / `graph.conversation_variables` by `save()` and restored by `load()`. `globalVars` merges `sys` / `env` / `conversation` into every `VarInput` autocomplete, so the scopes are referenceable from any node regardless of graph wiring.

---

## 4. Recipe: add a new workflow node type

Example: add an **`http`** node that GETs a URL and exposes the response body as `{{<id>.text}}`.

**Backend** — `server/app/workflow/engine.py`:

1. Add a branch in `run()` next to the other `elif ntype == ...` cases:

   ```python
   elif ntype == "http":
       output = self._run_http(data)
   ```

2. Add the runner method (a node receives its `data` dict and returns an `output` dict that gets stored in `self.context[nid]`):

   ```python
   def _run_http(self, data: dict[str, Any]) -> dict[str, Any]:
       import requests
       url = _resolve(data.get("url", ""), self.context)
       resp = requests.get(url, timeout=30)
       return {"text": resp.text, "status": resp.status_code}
   ```

   For a node that streams text to the UI, follow `_run_llm`: make it an `async` generator yielding `(frame, text)` tuples where `frame` is `_event({"type": "text_delta", "node_id": nid, "delta": ...})`.

**Frontend** — `apps/web-ele/src/views/agentscope/workflow/`:

1. Register the type's visual metadata in `FlowNode.vue`'s `META` map (color, icon, label) so it renders on the canvas.
2. Add it to the left palette list and the right-hand config panel in `editor.vue` (a small form binding into `node.data`, e.g. a `url` input).

No schema migration is needed — node config is free-form JSON inside the graph.

---

## 5. Recipe: add a new API endpoint / backend feature

To add a feature area `foo`:

1. Create `server/app/foo/__init__.py`, `models.py`, `router.py`.
2. In `models.py`, define SQLModel tables (`class Foo(SQLModel, table=True)`).
3. In `router.py`:

   ```python
   from fastapi import APIRouter, Depends
   from sqlmodel import Session, select
   from ..ontology.db import get_session   # shared SQLite session dependency

   router = APIRouter(prefix="/admin/foos", tags=["foo"])

   @router.get("/")
   def list_foos(session: Session = Depends(get_session)) -> dict:
       rows = list(session.exec(select(Foo)))
       return {"items": rows, "total": len(rows)}
   ```

4. Wire it in `server/app/main.py`: `from .foo.router import router as foo_router` then `app.include_router(foo_router)`.
5. **Ensure the table is created**: `server/app/ontology/db.py:init_db()` must import `app.foo.models` (it imports all model modules so metadata is complete). Add the import there if missing.
6. Add a typed client at `apps/web-ele/src/api/agentscope/foo.ts` and re-export it from `index.ts`.

Identity: read the caller via the `X-User-ID` header (see `publish/router.py`'s `_owner` dependency for the pattern) and scope rows by `owner_user_id`.

---

## 6. Recipe: add a new admin page (frontend)

1. Create `apps/web-ele/src/views/agentscope/foo/index.vue`.
2. Add a route + menu entry in `apps/web-ele/src/router/routes/modules/agentscope.ts`.
3. Add i18n keys to both `locales/langs/zh-CN/agentscope.json` and `en-US/agentscope.json` (titles are referenced as `$t('agentscope.menu.foo')`).
4. Use the `foo.ts` API client for all data access. Reuse shared components: `SchemaForm.vue` (JSON-Schema-driven forms), `StatusTag.vue`, and Element Plus's `el-table` / `el-drawer` / `el-dialog` for the usual table + drawer CRUD pattern (see `views/agentscope/agents/index.vue` as the canonical example).

---

## 7. Recipe: knowledge pipeline & retrieval

A knowledge base is created by picking a **chunk strategy** × **index method**; the backend's `build_pipeline()` (`server/app/knowledge/pipeline.py`) derives the stage list from that choice. The frontend mirrors this in `buildPreview()` so the create dialog shows a live pipeline preview.

Stages: **extract → clean → split | split_parent_child → [embed | build_graph] → index**.

- chunk strategy `general` → `split`; `parent_child` → `split_parent_child` (large parent + small child chunks, child used for matching, parent returned as context).
- index method drives the indexer stage: `keyword` → TF-IDF only; `vector` → `embed` (hash-based 256-dim L2 vectors, no external deps); `knowledge_graph` → `build_graph` (LLM triple extraction via `graph.py`, needs `kg_credential_id` + `kg_type` + `kg_model`); `hybrid` → graph + keyword (0.7/0.3 blend).

Recall testing (`POST /admin/knowledge-bases/{id}/retrieve`) returns method-specific output: scores for vector, parent context for parent-child, matched triples for knowledge-graph. The retrieve panel can override the method per query.

**Visual pipeline editor** (`views/agentscope/knowledge/pipeline.vue`, route `/agentscope/knowledge/:id/pipeline`, opened from the "流水线编排" button on each KB row): a Vue Flow DAG editor covering the Dify **Knowledge Pipeline** node set — `datasource`, `extract` (document-extractor), `clean`, `split`, `split_parent_child`, `qa` (QA extraction), `embed`, `build_graph` (knowledge graph), `index`. Editing/reordering nodes and saving persists the stage list and triggers a reindex through the same `run_pipeline()` backend.

To add a pipeline stage (e.g. a `dedupe` step), extend `run_pipeline()` to handle the new `stage["type"]`, add it to `build_pipeline()` if it should be auto-derived, then add it to `PIPELINE_NODE_TYPES` + a config card in `pipeline.vue` (and mirror it in `buildPreview()` / `STAGE_ICON` in `views/agentscope/knowledge/index.vue`).

The same retrieval is exposed to agents as the `knowledge_search` tool (`server/app/knowledge/tools.py`), injected via the combined tool factory in `main.py`. Tools must return AgentScope `ToolChunk` objects (not `ToolResponse`) or results are silently dropped.

---

## 7b. Recipe: multi-agent orchestration

The orchestration feature (`server/app/orchestration/`, page `views/agentscope/orchestration/index.vue`, route `/agentscope/orchestration`) runs a team of LLM "members" using one of **6 industry-standard collaboration patterns**. An orchestration is a single SQLite row: `pattern` + a free-form `config` (`{ members: [...], coordinator: {...}, max_rounds: int }`). Each member carries `name`, `role`, `instruction`, and a model binding (`credential_id` / `type` / `model` / `parameters`).

| Pattern (`pattern`) | Behaviour (`engine.py`) | Coordinator? |
| --- | --- | --- | --- |
| `sequential` | Members run in order; each sees the previous output via `{{carry}}`. | no |
| `parallel` | All members handle the same task concurrently (`asyncio.gather`); outputs concatenated. | no |
| `aggregation` | Parallel fan-out, then an aggregator LLM synthesises one final answer. | yes |
| `router` | A router LLM picks the single best-fit member from the roster to answer. | yes |
| `supervisor` | A supervisor LLM delegates to workers over multiple rounds (`DELEGATE: <name> | <task>`/`FINAL: <answer>`), up to `max_rounds`. | yes |
| `handoff` | Swarm-style: members hand control to each other (`HANDOFF: <colleague>`) until one completes. | no |

Execution is **SSE** (`POST /admin/orchestrations/{id}/run`, body `{query}`). Frame `type`s: `member_started` (`member`, `role`), `member_finished` (`member`, `text`), `finished` (`output`), `error` (`message`). The frontend (`src/api/agentscope/orchestration.ts → runOrchestration()`) parses the stream and renders a live transcript + final output.

Free-text member selection from coordinator LLMs is resolved with `_match_member()` (fuzzy name match), so the LLM doesn't need to emit exact IDs.

**To add a new pattern:** implement an `async def _run_<pattern>(self, query)` generator method on `OrchestrationEngine` (yield the SSE frames above), add a dispatch branch in `OrchestrationEngine.run()`, add the pattern to `PATTERNS` in `router.py`'s `/patterns` endpoint, and add a matching entry (with a lucide icon — no emoji) to the `PATTERNS` const in `orchestration/index.vue`. Set `usesCoordinator()` to `true` for it if it needs the coordinator config block.

---

## 8. CLI

`agentscope-admin` (`server/app/cli.py`) is a thin argparse + `requests` client. Local commands (`serve`, `seed`) run processes; the rest drive the REST API of a _running_ backend.

```
agentscope-admin serve --reload
agentscope-admin seed
agentscope-admin agents   list | create <name> | delete <id>
agentscope-admin knowledge list | create <name> | add-doc <kb> --file f.txt |
                            retrieve <kb> "<q>" | reindex <kb> <doc> | delete <kb>
agentscope-admin workflow list | create <name> | run <id> --input k=v | delete <id>
agentscope-admin publish  list | create <agent_id> --name <n> | delete <id>
agentscope-admin keys     list <app> | create <app> --name <n> | revoke <app> <key>
```

Global flags: `--base-url` (env `AGENTSCOPE_ADMIN_BASE_URL`), `--user` (env `AGENTSCOPE_ADMIN_USER`), `--json` (raw JSON instead of tables). Run from a source checkout via `./server/agentscope-admin …`, or install the console script with `cd server && pip install -e .`.

To add a CLI subcommand: add a `cmd_<area>` handler and register a subparser in `build_parser()`, reusing the `ApiClient` helper (which carries `X-User-ID` and parses SSE via `ApiClient.stream`).

---

## 9. Local development loop

```bash
./start-dev.sh --seed     # backend:8000 + frontend:5777, seeded demo data
pnpm lint                 # eslint across the monorepo
pnpm typecheck            # vue-tsc
pnpm build:ele            # production build of the Element Plus app
```

Backend has no test suite yet; validate changes by exercising the REST API (`/docs`) or the CLI against a running server. Commit style is Conventional Commits (`feat:`, `fix:`, …) — commitlint runs on commit.
