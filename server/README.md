# AgentScope Admin — Backend

FastAPI service built directly on top of AgentScope's app layer (`agentscope.create_app()`), extended with a Palantir-style ontology, a dashboard aggregator, per-agent model profiles and vben-compatible auth / preference endpoints.

## Run

```bash
./start.sh                 # venv + deps + Redis check + uvicorn --reload
./seed.sh                  # seed the enterprise-risk demo ontology
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
app/main.py            create_app() + router wiring
app/ontology           Palantir ontology: SQLModel tables, REST, agent tools
app/agent_profile      Per-agent model defaults + permission mode (SQLModel + REST)
app/dashboard          Aggregate stats endpoint
app/preferences        vben UI preference persistence (per user)
app/compat_auth        Minimal auth endpoints for the vben shell
app/settings.py        Pydantic settings (Redis, paths)
scripts/seed_risk_ontology.py   Enterprise-risk demo seed (idempotent)
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

The full AgentScope surface (agent, session, chat SSE, credential, model, schedule, workspace/mcp, workspace/skill, background-tasks, …) is mounted unchanged — see `/docs`.
