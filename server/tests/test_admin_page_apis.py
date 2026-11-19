"""HTTP smoke tests for the admin pages that were blank before the AgentScope pin.

These mount only the SQLModel-backed admin routers, so they run without
installing the pinned AgentScope git dependency or Redis.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.agent_profile import models as _agent_profile_models  # noqa: F401
from app.agent_profile.router import router as agent_profile_router
from app.observability import models as _observability_models  # noqa: F401
from app.observability.router import router as observability_router
from app.ontology.db import get_session
from app.orchestration import models as _orchestration_models  # noqa: F401
from app.orchestration.router import router as orchestration_router

PINNED_SHA = "68f643db4d814d7a639b920c8a82ecb6b27bd39c"
SERVER_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _session():
        with Session(engine) as session:
            yield session

    app = FastAPI()
    app.include_router(agent_profile_router)
    app.include_router(observability_router)
    app.include_router(orchestration_router)
    app.dependency_overrides[get_session] = _session
    return TestClient(app)


def test_agent_profiles_round_trip(client: TestClient) -> None:
    empty = client.get("/admin/agent-profiles/")
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "total": 0}

    upsert = client.put(
        "/admin/agent-profiles/agent-demo",
        json={"default_model": "gpt-4o-mini", "description": "smoke"},
    )
    assert upsert.status_code == 200
    body = upsert.json()
    assert body["agent_id"] == "agent-demo"
    assert body["default_model"] == "gpt-4o-mini"

    listed = client.get("/admin/agent-profiles/")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["agent_id"] == "agent-demo"

    deleted = client.delete("/admin/agent-profiles/agent-demo")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}
    assert client.get("/admin/agent-profiles/").json()["total"] == 0


def test_usage_summary_and_recent(client: TestClient) -> None:
    skipped = client.post("/admin/usage/", json={"model_name": "gpt-4o-mini"})
    assert skipped.status_code == 200
    assert skipped.json() == {"recorded": False}

    recorded = client.post(
        "/admin/usage/",
        json={
            "agent_id": "agent-demo",
            "model_name": "gpt-4o-mini",
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
        },
        headers={"x-user-id": "admin"},
    )
    assert recorded.status_code == 200
    assert recorded.json() == {"recorded": True}

    summary = client.get("/admin/usage/summary", headers={"x-user-id": "admin"})
    assert summary.status_code == 200
    data = summary.json()
    assert data["total_input_tokens"] == 1_000_000
    assert data["total_output_tokens"] == 1_000_000
    # 0.15 + 0.60 USD per 1M tokens
    assert data["estimated_cost_usd"] == pytest.approx(0.75)

    recent = client.get("/admin/usage/recent", headers={"x-user-id": "admin"})
    assert recent.status_code == 200
    items = recent.json()["items"]
    assert len(items) == 1
    assert items[0]["agent_id"] == "agent-demo"


def test_orchestration_patterns_and_crud(client: TestClient) -> None:
    patterns = client.get("/admin/orchestrations/patterns")
    assert patterns.status_code == 200
    values = {row["value"] for row in patterns.json()["items"]}
    assert {"sequential", "parallel", "aggregation", "router", "supervisor", "handoff"} <= values

    created = client.post(
        "/admin/orchestrations/",
        json={"name": "smoke-pipeline", "pattern": "sequential"},
    )
    assert created.status_code == 200
    orch_id = created.json()["id"]
    assert created.json()["name"] == "smoke-pipeline"

    listed = client.get("/admin/orchestrations/")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == orch_id

    fetched = client.get(f"/admin/orchestrations/{orch_id}")
    assert fetched.status_code == 200
    assert fetched.json()["pattern"] == "sequential"


def test_agentscope_pin_is_consistent() -> None:
    pyproject = (SERVER_ROOT / "pyproject.toml").read_text()
    requirements = (SERVER_ROOT / "requirements.txt").read_text()
    pattern = re.compile(r"agentscope\.git@([0-9a-f]{40})")
    py_pins = pattern.findall(pyproject)
    req_pins = pattern.findall(requirements)
    assert py_pins == [PINNED_SHA]
    assert req_pins == [PINNED_SHA]


def test_admin_chrome_declares_focus_visible() -> None:
    root = Path(__file__).resolve().parents[2]
    css = (root / "apps/web-ele/src/views/agentscope/a11y.css").read_text()
    bootstrap = (root / "apps/web-ele/src/bootstrap.ts").read_text()
    assert ":focus-visible" in css
    assert "views/agentscope/a11y.css" in bootstrap
