"""REST API for execution-trace observability.

Goes beyond raw token usage: stores a per-run execution chain (model calls,
tool calls, ontology operations, human confirmations, replies) so the UI can
show — per agent — which sessions ran, and for each session a step-by-step
timeline with inputs/outputs/durations. Also serves aggregate analytics
(success rate, latency percentiles, token trend, top tools).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from ..ontology.db import get_session
from .models import TraceSpan
from .router import _cost

router = APIRouter(prefix="/admin/trace", tags=["observability"])


def _owner(x_user_id: str = Header(default="admin")) -> str:
    return x_user_id


def _percentile(values: list[int], pct: float) -> int:
    """Nearest-rank percentile of a list of durations (ms)."""
    if not values:
        return 0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round(pct / 100 * len(ordered)) - 1))
    return ordered[k]


class SpanIn(BaseModel):
    seq: int = 0
    kind: str = "model"
    name: str = ""
    status: str = "ok"
    model_name: str = ""
    input_text: str = ""
    output_text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0


class RunIn(BaseModel):
    """A complete run (one user turn) with its ordered spans."""

    agent_id: str = ""
    session_id: str = ""
    run_id: str = ""
    source: str = "playground"
    spans: list[SpanIn] = []


def _truncate(text: str, limit: int = 8000) -> str:
    return text if len(text) <= limit else text[:limit] + "…(truncated)"


@router.post("/runs", summary="Ingest a run's execution-chain spans")
def ingest_run(
    body: RunIn,
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> dict:
    if not body.spans:
        return {"recorded": 0}
    for s in body.spans:
        session.add(
            TraceSpan(
                owner_user_id=owner,
                agent_id=body.agent_id,
                session_id=body.session_id,
                run_id=body.run_id,
                source=body.source,
                seq=s.seq,
                kind=s.kind,
                name=s.name,
                status=s.status,
                model_name=s.model_name,
                input_text=_truncate(s.input_text),
                output_text=_truncate(s.output_text),
                input_tokens=s.input_tokens,
                output_tokens=s.output_tokens,
                duration_ms=s.duration_ms,
            ),
        )
    session.commit()
    return {"recorded": len(body.spans)}


def _rows_since(session: Session, owner: str, days: int) -> list[TraceSpan]:
    since = datetime.utcnow() - timedelta(days=days)
    return list(
        session.exec(
            select(TraceSpan)
            .where(TraceSpan.owner_user_id == owner)
            .where(TraceSpan.created_at >= since),
        ).all(),
    )


@router.get("/agents", summary="Per-agent session/run/token aggregation")
def agents_overview(
    days: int = Query(default=30, ge=1, le=365),
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> dict:
    rows = _rows_since(session, owner, days)
    by_agent: dict[str, dict] = defaultdict(
        lambda: {
            "sessions": set(),
            "runs": set(),
            "model_calls": 0,
            "tool_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "errors": 0,
            "run_durations": defaultdict(int),
            "last_active": None,
        },
    )
    for r in rows:
        a = by_agent[r.agent_id or "unknown"]
        a["sessions"].add(r.session_id)
        a["runs"].add(r.run_id)
        if r.kind == "model":
            a["model_calls"] += 1
            a["input_tokens"] += r.input_tokens
            a["output_tokens"] += r.output_tokens
            a["cost"] += _cost(r.model_name, r.input_tokens, r.output_tokens)
        if r.kind in {"tool", "ontology", "knowledge"}:
            a["tool_calls"] += 1
        if r.status == "error":
            a["errors"] += 1
        a["run_durations"][r.run_id] += r.duration_ms
        if a["last_active"] is None or r.created_at > a["last_active"]:
            a["last_active"] = r.created_at

    items = []
    for agent_id, a in by_agent.items():
        durations = list(a["run_durations"].values())
        run_count = len(a["runs"])
        error_runs = a["errors"]
        items.append(
            {
                "agent_id": agent_id,
                "sessions": len(a["sessions"]),
                "runs": run_count,
                "model_calls": a["model_calls"],
                "tool_calls": a["tool_calls"],
                "input_tokens": a["input_tokens"],
                "output_tokens": a["output_tokens"],
                "total_tokens": a["input_tokens"] + a["output_tokens"],
                "cost": round(a["cost"], 4),
                "success_rate": round(
                    100 * (1 - error_runs / run_count) if run_count else 100, 1,
                ),
                "avg_latency_ms": round(sum(durations) / len(durations))
                if durations
                else 0,
                "p95_latency_ms": _percentile(durations, 95),
                "last_active": a["last_active"].isoformat()
                if a["last_active"]
                else None,
            },
        )
    items.sort(key=lambda x: x["last_active"] or "", reverse=True)
    return {"days": days, "items": items}


@router.get("/sessions", summary="Sessions for an agent with run aggregates")
def agent_sessions(
    agent_id: str = Query(default=""),
    days: int = Query(default=30, ge=1, le=365),
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> dict:
    rows = _rows_since(session, owner, days)
    rows = [r for r in rows if not agent_id or r.agent_id == agent_id]
    by_session: dict[str, dict] = defaultdict(
        lambda: {
            "agent_id": "",
            "runs": set(),
            "model_calls": 0,
            "tool_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "errors": 0,
            "duration_ms": 0,
            "source": "playground",
            "started_at": None,
            "last_active": None,
        },
    )
    for r in rows:
        s = by_session[r.session_id]
        s["agent_id"] = r.agent_id
        s["source"] = r.source
        s["runs"].add(r.run_id)
        s["duration_ms"] += r.duration_ms
        if r.kind == "model":
            s["model_calls"] += 1
            s["input_tokens"] += r.input_tokens
            s["output_tokens"] += r.output_tokens
            s["cost"] += _cost(r.model_name, r.input_tokens, r.output_tokens)
        if r.kind in {"tool", "ontology", "knowledge"}:
            s["tool_calls"] += 1
        if r.status == "error":
            s["errors"] += 1
        if s["started_at"] is None or r.created_at < s["started_at"]:
            s["started_at"] = r.created_at
        if s["last_active"] is None or r.created_at > s["last_active"]:
            s["last_active"] = r.created_at

    items = [
        {
            "session_id": sid,
            "agent_id": s["agent_id"],
            "source": s["source"],
            "runs": len(s["runs"]),
            "model_calls": s["model_calls"],
            "tool_calls": s["tool_calls"],
            "input_tokens": s["input_tokens"],
            "output_tokens": s["output_tokens"],
            "total_tokens": s["input_tokens"] + s["output_tokens"],
            "cost": round(s["cost"], 4),
            "errors": s["errors"],
            "duration_ms": s["duration_ms"],
            "started_at": s["started_at"].isoformat() if s["started_at"] else None,
            "last_active": s["last_active"].isoformat()
            if s["last_active"]
            else None,
        }
        for sid, s in by_session.items()
    ]
    items.sort(key=lambda x: x["last_active"] or "", reverse=True)
    return {"agent_id": agent_id, "items": items}


@router.get("/sessions/{session_id}", summary="Full execution chain for a session")
def session_trace(
    session_id: str,
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> dict:
    rows = list(
        session.exec(
            select(TraceSpan)
            .where(TraceSpan.owner_user_id == owner)
            .where(TraceSpan.session_id == session_id)
            .order_by(TraceSpan.created_at, TraceSpan.seq),
        ).all(),
    )
    runs: dict[str, dict] = {}
    order: list[str] = []
    for r in rows:
        if r.run_id not in runs:
            runs[r.run_id] = {
                "run_id": r.run_id,
                "started_at": r.created_at,
                "spans": [],
            }
            order.append(r.run_id)
        runs[r.run_id]["spans"].append(
            {
                "id": r.id,
                "seq": r.seq,
                "kind": r.kind,
                "name": r.name,
                "status": r.status,
                "model_name": r.model_name,
                "input_text": r.input_text,
                "output_text": r.output_text,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "duration_ms": r.duration_ms,
                "created_at": r.created_at.isoformat(),
            },
        )

    run_list = []
    for rid in order:
        run = runs[rid]
        spans = run["spans"]
        duration = sum(s["duration_ms"] for s in spans)
        tokens = sum(s["input_tokens"] + s["output_tokens"] for s in spans)
        cost = sum(
            _cost(s["model_name"], s["input_tokens"], s["output_tokens"])
            for s in spans
        )
        status = "error" if any(s["status"] == "error" for s in spans) else "ok"
        run_list.append(
            {
                "run_id": rid,
                "started_at": run["started_at"].isoformat(),
                "duration_ms": duration,
                "total_tokens": tokens,
                "cost": round(cost, 4),
                "status": status,
                "spans": spans,
            },
        )
    return {"session_id": session_id, "runs": run_list}


@router.get("/analytics", summary="Aggregate analytics for the dashboard")
def analytics(
    days: int = Query(default=30, ge=1, le=365),
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> dict:
    rows = _rows_since(session, owner, days)

    run_status: dict[str, str] = {}
    run_duration: dict[str, int] = defaultdict(int)
    tool_calls: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "errors": 0, "duration_ms": 0},
    )
    by_day: dict[str, dict] = defaultdict(
        lambda: {"input": 0, "output": 0, "runs": set()},
    )
    model_calls = 0
    for r in rows:
        run_duration[r.run_id] += r.duration_ms
        if r.status == "error":
            run_status[r.run_id] = "error"
        else:
            run_status.setdefault(r.run_id, "ok")
        if r.kind in {"tool", "ontology", "knowledge"}:
            t = tool_calls[r.name or r.kind]
            t["calls"] += 1
            t["duration_ms"] += r.duration_ms
            if r.status == "error":
                t["errors"] += 1
        if r.kind == "model":
            model_calls += 1
        day = r.created_at.strftime("%Y-%m-%d")
        d = by_day[day]
        d["input"] += r.input_tokens
        d["output"] += r.output_tokens
        d["runs"].add(r.run_id)

    total_runs = len(run_status)
    error_runs = sum(1 for v in run_status.values() if v == "error")
    durations = list(run_duration.values())

    top_tools = sorted(
        (
            {
                "name": name,
                "calls": t["calls"],
                "errors": t["errors"],
                "avg_latency_ms": round(t["duration_ms"] / t["calls"])
                if t["calls"]
                else 0,
            }
            for name, t in tool_calls.items()
        ),
        key=lambda x: x["calls"],
        reverse=True,
    )[:10]

    return {
        "days": days,
        "total_runs": total_runs,
        "model_calls": model_calls,
        "tool_calls": sum(t["calls"] for t in tool_calls.values()),
        "success_rate": round(
            100 * (1 - error_runs / total_runs) if total_runs else 100, 1,
        ),
        "error_runs": error_runs,
        "avg_latency_ms": round(sum(durations) / len(durations)) if durations else 0,
        "p50_latency_ms": _percentile(durations, 50),
        "p95_latency_ms": _percentile(durations, 95),
        "p99_latency_ms": _percentile(durations, 99),
        "top_tools": top_tools,
        "by_day": [
            {
                "date": k,
                "input": by_day[k]["input"],
                "output": by_day[k]["output"],
                "runs": len(by_day[k]["runs"]),
            }
            for k in sorted(by_day.keys())
        ],
    }
