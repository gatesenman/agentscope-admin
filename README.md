# AgentScope Admin（智能体管理后台）

A B2B admin platform for managing the full lifecycle of [AgentScope](https://github.com/agentscope-ai/agentscope) agents, with a Palantir-style **ontology / semantic layer** that agents bind to for precise semantic queries and action execution.

The frontend is built on [vue-vben-admin](https://github.com/vbenjs/vue-vben-admin) (Element Plus edition, `apps/web-ele`). The backend is a real FastAPI service built directly on top of AgentScope's app layer (`agentscope.app`) — not a mock.

## Features

- **Agent lifecycle** — create / edit / delete agents with schema-driven configuration (identity, context, ReAct), rendered dynamically from the backend's `GET /agent/schema`.
- **Palantir-style ontology** — object types, properties, link types (relations), action types and object instances. Agents bind to an ontology and receive ontology tools (semantic query / traverse / execute action).
- **Model configuration (per agent)** — persistent default credential / model, generation parameters (temperature / top_p / max_tokens), a fallback model and a tool-execution **permission mode** (aligned with the Claude Agent SDK's `permission_mode`). See [docs/CONFIG-ALIGNMENT.md](docs/CONFIG-ALIGNMENT.md).
- **Credentials & models** — manage LLM provider credentials (OpenAI / DashScope / DeepSeek / Anthropic / …) and pick models per session.
- **Playground** — chat with an agent over an SSE stream, with live tool-call and thinking traces; auto-prefills the agent's saved model defaults and permission mode.
- **Multi-agent orchestration** — a team of LLM members run under one of **6 industry-standard patterns**: sequential, parallel, aggregation, router, supervisor (multi-round delegation) and handoff (swarm). SSE-streamed live transcript + final output. Backend in `server/app/orchestration/`.
- **Workflow orchestration (Dify-style)** — a visual DAG canvas (Vue Flow) covering the **full Dify node catalogue** (triggers, LLM, agent, question-classifier, parameter-extractor, knowledge / knowledge-index / document-extractor / datasource, condition, iteration, loop, variable-aggregator, assigner, code, template, http-request, tool, list-operator, human-input, answer) **plus a Palantir-style `ontology` node** (query / traverse / execute action). Template variables (`{{node.field}}`), multi-branch routing and SSE-streamed execution. Backend engine in `server/app/workflow/`.
- **Knowledge base + visual pipeline editor** — knowledge bases built by choosing a **chunk strategy** (general / parent-child) × **index method** (keyword / vector / knowledge-graph / hybrid), with a Vue Flow **Knowledge Pipeline** editor covering Dify's node set (datasource → extract → clean → split / parent-child → qa → embed / build-graph → index) and a recall-test panel. The same retrieval is reused as a workflow node and as the agent-callable `knowledge_search` tool. Backend in `server/app/knowledge/`.
- **CLI** — `agentscope-admin` for serving, seeding and managing agents / knowledge / workflows / published apps / API keys. See [CLI](#cli).
- **Publishing (Dify-style)** — freeze an agent into a public **App** exposing three integration surfaces, with multi-key management. See [Publishing](#publishing).
- **Integration center** — ready-to-copy cURL / Python snippets for embedding the API.
- **Dashboard** — aggregate stats across agents, credentials, sessions and the ontology.

## Architecture

```
apps/web-ele          Vue 3 + Element Plus admin UI (vue-vben-admin)
  src/api/agentscope    Typed API client for the backend
  src/views/agentscope  Dashboard / Agents / Ontology / Credentials / Sessions /
                        Orchestration / Workflow / Knowledge / Publish / Integration
server                FastAPI backend
  app/main.py           Wires agentscope.create_app() + our routers + agent-tool factory
  app/cli.py            `agentscope-admin` command-line interface
  app/ontology          Palantir-style ontology (SQLModel + SQLite) and agent tools
  app/knowledge         Knowledge bases, ingestion pipeline, TF-IDF retrieval + tool
  app/workflow          Dify-style DAG workflow model + topological SSE engine
  app/orchestration     Multi-agent orchestration (6 patterns) + SSE engine
  app/publish           Published apps + API keys (Web App / REST / embed)
  app/dashboard         Aggregate stats
  app/compat_auth       Minimal auth endpoints for the vben demo shell (placeholder identity)
```

AgentScope state (agents, sessions, credentials) is persisted via its built-in `RedisStorage` + `LocalWorkspaceManager`. The ontology, knowledge bases, workflows and published apps are persisted separately in SQLite. See [DEVELOPER.md](DEVELOPER.md) for the full module map and extension recipes.

## Prerequisites

- Node.js `v22.22.0`, pnpm `11.2.2`
- Python `3.12`
- Redis running locally on `:6379`

## Quick start (one command)

```bash
./start-dev.sh           # backend (:8000) + frontend (:5777)
./start-dev.sh --seed    # also seed demo data (ontology + KB + RAG workflow) first
```

The script creates the Python venv, installs backend + frontend deps on first run, checks Redis, then launches both servers and tears them down on Ctrl-C.

## Backend (manual)

```bash
cd server
./start.sh               # venv + deps + Redis check + uvicorn (reload)
# or, fully manual:
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API is then available at `http://localhost:8000` (`/health`, `/docs`). Seed the demo ontology with `cd server && ./seed.sh`.

## Frontend (manual)

```bash
pnpm install
pnpm dev:ele      # dev server on http://localhost:5777
```

The dev server proxies `/api` → `http://localhost:8000` (see `apps/web-ele/vite.config.ts`).

## Build / lint / typecheck

```bash
pnpm build:ele
pnpm typecheck
pnpm lint
```

## CLI

`agentscope-admin` operates the platform from the terminal. Run it from a source checkout via `./server/agentscope-admin …`, or install the console script with `cd server && pip install -e .`.

```bash
agentscope-admin serve --reload                      # launch the backend
agentscope-admin seed                                # demo ontology + KB + workflow
agentscope-admin agents list
agentscope-admin knowledge retrieve <kb_id> "可疑交易上报阈值"
agentscope-admin workflow run <workflow_id> --input query="电汇要上报吗"
agentscope-admin publish list
agentscope-admin keys create <app_id> --name ci-key
```

Global flags: `--base-url` (env `AGENTSCOPE_ADMIN_BASE_URL`, default `http://localhost:8000`), `--user` (env `AGENTSCOPE_ADMIN_USER`, default `admin`), `--json`. Commands that manage resources talk to a _running_ backend.

## Developer guide

For extending the platform (adding a workflow node, an API endpoint, a page, or a pipeline stage), see [DEVELOPER.md](DEVELOPER.md) — written to be AI-agent friendly for second-stage development.

## Publishing

Publishing freezes an agent into a public **App** (snapshotting its model, parameters, ontology binding and permission mode). Manage apps under **智能体平台 → 发布管理** (`/agentscope/publish`): publish/unpublish, toggle status, edit the public profile (name / icon / opening statement / suggested questions / allowed origins / rate limit), and manage API keys.

Each app is reachable by an opaque `token` through three surfaces:

| Surface | Entry point | Auth |
| --- | --- | --- |
| **Web App** (hosted UI) | `GET /app/{token}` (frontend) | none (login-free) |
| **REST API** | `POST /v1/apps/{token}/chat-messages` | `Authorization: Bearer app-sk-…` |
| **Embed** | `<iframe>` of the Web App, or floating bubble via `/static/embed.js` | none |

The REST endpoint mirrors Dify's chat-messages contract and supports both `response_mode: "streaming"` (SSE) and `"blocking"` (single JSON answer):

```bash
curl -N http://localhost:8000/v1/apps/<token>/chat-messages \
  -H "Authorization: Bearer <app-sk-...>" \
  -H "Content-Type: application/json" \
  -d '{"query":"查询 wire 渠道交易","response_mode":"streaming"}'
```

API keys are shown **once** on creation, stored only as SHA-256 hashes (`key_prefix` is kept for display), and can be revoked; last-used time is tracked. Public chat is proxied to the server's own AgentScope endpoints under the app owner's identity, so published apps reuse the same ontology tools and permission mode as the playground. Backend lives in `server/app/publish/` (`models.py` tables + `router.py` admin/public endpoints).

## MCP servers

A persistent registry of Model Context Protocol servers, managed under **智能体平台 → MCP 服务器** (`/agentscope/mcp`). Supports both `stdio` and `http` transports, stateful/stateless mode, tool allow/deny filters, and a one-click **test** that builds a real `MCPClient`, connects, and lists discovered tools (recording health + last error). Enabled servers are auto-attached to debug sessions on creation. Backend: `server/app/mcp_registry/`.

## Human-in-the-loop tool confirmation

When an agent runs under a permission mode that requires approval, AgentScope streams a `REQUIRE_USER_CONFIRM` event. The debug console (`/agentscope/sessions`) renders the pending tool calls with **Approve / Reject** controls and resumes the reply by posting back a `USER_CONFIRM_RESULT` on the same `reply_id` — no more bypassing permissions to get work done.

## Observability (token usage & cost)

AgentScope emits `MODEL_CALL_END` events carrying input/output token counts. Usage is captured at both edges we control — the debug console reports each call (`source=playground`) and the published-app proxy records usage server-side while relaying SSE frames (`source=app`) — and written to the `usage_log` table. The **可观测性** page (`/agentscope/observability`) aggregates totals, a per-model breakdown with estimated USD cost, and a recent-calls trace. Backend: `server/app/observability/` (`POST /admin/usage`, `GET /admin/usage/summary`, `GET /admin/usage/recent`).

## Users & roles (multi-tenant / RBAC skeleton)

Every domain table is scoped by `owner_user_id` (identity via the `X-User-ID` header). The **用户与角色** page (`/agentscope/users`) manages console members against a fixed role catalog (`admin` / `editor` / `viewer`) with permission codes. A default `admin` user is seeded on startup and protected from deletion. Backend: `server/app/rbac/` (`/admin/rbac/users`, `/admin/rbac/roles`, `/admin/rbac/me`).

---

Based on [vue-vben-admin](https://github.com/vbenjs/vue-vben-admin) (MIT). Refer to the upstream repository for base framework documentation.
