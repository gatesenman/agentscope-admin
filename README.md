# AgentScope Admin（智能体管理后台）

A B2B admin platform for managing the full lifecycle of [AgentScope](https://github.com/agentscope-ai/agentscope) agents, with a Palantir-style **ontology / semantic layer** that agents bind to for precise semantic queries and action execution.

The frontend is built on [vue-vben-admin](https://github.com/vbenjs/vue-vben-admin) (Element Plus edition, `apps/web-ele`). The backend is a real FastAPI service built directly on top of AgentScope's app layer (`agentscope.app`) — not a mock.

## Features

- **Agent lifecycle** — create / edit / delete agents with schema-driven configuration (identity, context, ReAct), rendered dynamically from the backend's `GET /agent/schema`.
- **Palantir-style ontology** — object types, properties, link types (relations), action types and object instances. Agents bind to an ontology and receive ontology tools (semantic query / traverse / execute action).
- **Credentials & models** — manage LLM provider credentials (OpenAI / DashScope / Anthropic / …) and pick models per session.
- **Playground** — chat with an agent over an SSE stream, with live tool-call and thinking traces.
- **Multi-agent orchestration** — sequential pipelines chaining agents' outputs.
- **Integration center** — ready-to-copy cURL / Python snippets for embedding the API.
- **Dashboard** — aggregate stats across agents, credentials, sessions and the ontology.

## Architecture

```
apps/web-ele          Vue 3 + Element Plus admin UI (vue-vben-admin)
  src/api/agentscope    Typed API client for the backend
  src/views/agentscope  Dashboard / Agents / Ontology / Credentials / Sessions / Orchestration / Integration
server                FastAPI backend
  app/main.py           Wires agentscope.create_app() + ontology + dashboard + auth-compat routers
  app/ontology          Palantir-style ontology (SQLModel + SQLite) and agent tools
  app/dashboard         Aggregate stats
  app/compat_auth       Minimal auth endpoints for the vben demo shell (placeholder identity)
```

AgentScope state (agents, sessions, credentials) is persisted via its built-in `RedisStorage` + `LocalWorkspaceManager`. The ontology is persisted separately in SQLite.

## Prerequisites

- Node.js `v22.22.0`, pnpm `11.2.2`
- Python `3.12`
- Redis running locally on `:6379`

## Backend

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API is then available at `http://localhost:8000` (`/health`, `/docs`).

## Frontend

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

---

Based on [vue-vben-admin](https://github.com/vbenjs/vue-vben-admin) (MIT). Refer to the upstream repository for base framework documentation.
