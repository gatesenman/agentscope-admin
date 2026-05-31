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
| Ontology | SQLite | `ontology` | object types, properties, link types, action types, object instances |
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

Output is **Server-Sent Events**. Frame types (field `type`): `workflow_started`, `node_started`, `text_delta`, `node_finished`, `workflow_finished` (carries the final `output`), `error`. The frontend client (`src/api/agentscope/workflow.ts`) and the CLI (`workflow run`) both parse these.

Built-in node types: `start`, `llm`, `agent`, `knowledge`, `ontology`, `condition`, `template`, `answer` (alias `end`).

The **`ontology`** node (Palantir-style) runs one of three operations against a bound ontology and is handled by `_run_ontology()` in `engine.py`:

- `query` — semantic search over object instances (`object_type`, `search`, `filters`, `limit`)
- `traverse` — follow a link from a source object (`link_type`, `source_object_id`)
- `execute_action` — invoke an action type, mutating instance state (`action`, `object_id`, `parameters`)

Its result is exposed as both `{{<id>.result}}` (structured) and `{{<id>.text}}` (JSON string). The editor config panel (`views/agentscope/workflow/editor.vue`) shows operation-dependent fields, driven by `selectedNode.data.operation`.

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

To add a pipeline stage (e.g. a `dedupe` step), extend `run_pipeline()` to handle the new `stage["type"]`, add it to `build_pipeline()` if it should be auto-derived, then mirror it in `buildPreview()` and add a `STAGE_ICON` entry + config card in `views/agentscope/knowledge/index.vue`.

The same retrieval is exposed to agents as the `knowledge_search` tool (`server/app/knowledge/tools.py`), injected via the combined tool factory in `main.py`. Tools must return AgentScope `ToolChunk` objects (not `ToolResponse`) or results are silently dropped.

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
