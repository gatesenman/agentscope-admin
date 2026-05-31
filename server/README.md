# AgentScope Admin — Backend

FastAPI service built directly on top of AgentScope's app layer (`agentscope.create_app()`), extended with a Palantir-style ontology, a dashboard aggregator, per-agent model profiles and vben-compatible auth / preference endpoints.

## Run

```bash
./start.sh                 # venv + deps + Redis check + uvicorn --reload
./seed.sh                  # seed demo data (ontology + KB + RAG workflow)
./agentscope-admin --help  # CLI (or: pip install -e . for a global command)
```

Manual equivalent:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- API root: `http://localhost:8000`
- Health: `GET /health`
- OpenAPI docs: `GET /docs`

## Configuration (env vars)

| Variable | Default | Purpose |
| --- | --- | --- |
| `AGENTSCOPE_ADMIN_REDIS_HOST` | `localhost` | Redis host (AgentScope storage) |
| `AGENTSCOPE_ADMIN_REDIS_PORT` | `6379` | Redis port |
| `AGENTSCOPE_ADMIN_REDIS_PASSWORD` | — | Redis password (optional) |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | uvicorn bind (start.sh) |
| `RELOAD` | `1` | uvicorn auto-reload (start.sh) |

See `app/settings.py` for the full settings model.

## Layout

```
app/main.py            create_app() + router wiring + combined agent-tool factory
app/cli.py             `agentscope-admin` CLI (argparse + requests)
app/ontology           Palantir ontology: SQLModel tables, REST, agent tools
app/knowledge          Knowledge bases, ingestion pipeline, TF-IDF retrieval + tool
app/workflow           Dify-style DAG workflow model + topological SSE engine
app/publish            Published apps + API keys (Web App / REST / embed)
app/agent_profile      Per-agent model defaults + permission mode (SQLModel + REST)
app/dashboard          Aggregate stats endpoint
app/preferences        vben UI preference persistence (per user)
app/compat_auth        Minimal auth endpoints for the vben shell
app/settings.py        Pydantic settings (Redis, paths)
scripts/seed_risk_ontology.py        Enterprise-risk demo ontology (idempotent)
scripts/seed_knowledge_workflow.py   Demo knowledge base + RAG workflow (idempotent)
```

## Persistence

- **AgentScope state** (agents, sessions, credentials, schedules) → `RedisStorage`.
- **Ontology + agent profiles + preferences** → SQLite at `data/ontology.db`.
- **Workspaces** (per-session files / tools) → `data/workspaces` via `LocalWorkspaceManager`.

## Admin endpoints (added on top of AgentScope)

| Method | Path | Purpose |
| --- | --- | --- |
| GET/PUT/DELETE | `/admin/agent-profiles/{agent_id}` | Per-agent model defaults, params, fallback, permission mode |
| `/ontology/...` | full CRUD | Object types / properties / link types / action types / instances |
| GET | `/dashboard/stats` | Aggregate counts |
| GET/PUT | `/preferences` | vben UI preferences per user |
| `/admin/knowledge-bases/...` | full CRUD | Knowledge bases, documents, retrieve test |
| `/admin/workflows/...` | full CRUD + `/{id}/run` | Workflow graphs + SSE execution |
| `/admin/published-apps/...` | full CRUD + `/keys` | Published apps + API keys |
| POST | `/v1/apps/{token}/chat-messages` | Public REST chat (Bearer key, Dify-style) |

The full AgentScope surface (agent, session, chat SSE, credential, model, schedule, workspace/mcp, workspace/skill, background-tasks, …) is mounted unchanged — see `/docs`.
