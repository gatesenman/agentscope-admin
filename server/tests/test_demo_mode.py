from fastapi.testclient import TestClient

from app.demo import build_demo_app, demo_payloads


def test_demo_mode_returns_page_payloads_without_redis():
    client = TestClient(build_demo_app())
    status = client.get("/admin/status")
    assert status.status_code == 200
    body = status.json()
    assert body["mode"] == "demo"
    assert body["redis"] is False
    assert "banner" in body
    agents = client.get("/admin/agent-profiles/")
    assert agents.status_code == 200
    assert agents.json()["total"] == 1
    assert agents.json()["items"][0]["agent_id"] == "demo-researcher"
    usage = client.get("/admin/usage/summary")
    assert usage.status_code == 200
    flows = client.get("/admin/orchestration/workflows")
    assert flows.status_code == 200
    assert flows.json()["total"] == 1
    # payloads helper stays in sync
    assert demo_payloads()["connection"]["mode"] == "demo"
