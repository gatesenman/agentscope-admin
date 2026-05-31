"""REST API for token-usage / cost observability."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from ..ontology.db import get_session
from .models import UsageLog

router = APIRouter(prefix="/admin/usage", tags=["observability"])


# Estimated price in USD per 1M tokens. Unknown models fall back to zero so the
# dashboard never shows a misleading number. Values are editable here.
_PRICING: dict[str, dict[str, float]] = {
    "deepseek-chat": {"input": 0.27, "output": 1.10},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


def _owner(x_user_id: str = Header(default="admin")) -> str:
    return x_user_id


def _cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    price = _PRICING.get(model_name)
    if not price:
        return 0.0
    return (
        input_tokens * price["input"] + output_tokens * price["output"]
    ) / 1_000_000


class UsageCreate(BaseModel):
    agent_id: str = ""
    session_id: str = ""
    source: str = "playground"
    model_name: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


@router.post("/", summary="Record a model-call usage event")
def record_usage(
    body: UsageCreate,
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> dict:
    # Ignore empty events (some providers omit token counts).
    if body.input_tokens == 0 and body.output_tokens == 0:
        return {"recorded": False}
    row = UsageLog(owner_user_id=owner, **body.model_dump())
    session.add(row)
    session.commit()
    return {"recorded": True}


@router.get("/summary", summary="Aggregated token usage and estimated cost")
def usage_summary(
    days: int = Query(default=30, ge=1, le=365),
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> dict:
    since = datetime.utcnow() - timedelta(days=days)
    rows = session.exec(
        select(UsageLog)
        .where(UsageLog.owner_user_id == owner)
        .where(UsageLog.created_at >= since),
    ).all()

    total_input = sum(r.input_tokens for r in rows)
    total_output = sum(r.output_tokens for r in rows)
    total_cost = sum(
        _cost(r.model_name, r.input_tokens, r.output_tokens) for r in rows
    )

    by_model: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "input": 0, "output": 0, "cost": 0.0},
    )
    by_day: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "input": 0, "output": 0},
    )
    for r in rows:
        m = by_model[r.model_name or "unknown"]
        m["calls"] += 1
        m["input"] += r.input_tokens
        m["output"] += r.output_tokens
        m["cost"] += _cost(r.model_name, r.input_tokens, r.output_tokens)

        day = r.created_at.strftime("%Y-%m-%d")
        d = by_day[day]
        d["calls"] += 1
        d["input"] += r.input_tokens
        d["output"] += r.output_tokens

    return {
        "days": days,
        "total_calls": len(rows),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "estimated_cost_usd": round(total_cost, 4),
        "by_model": [
            {"model_name": k, **v, "cost": round(v["cost"], 4)}
            for k, v in sorted(
                by_model.items(),
                key=lambda kv: kv[1]["input"] + kv[1]["output"],
                reverse=True,
            )
        ],
        "by_day": [
            {"date": k, **by_day[k]} for k in sorted(by_day.keys())
        ],
    }


@router.get("/recent", summary="Recent model-call usage rows")
def usage_recent(
    limit: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> dict:
    rows = session.exec(
        select(UsageLog)
        .where(UsageLog.owner_user_id == owner)
        .order_by(UsageLog.created_at.desc())
        .limit(limit),
    ).all()
    return {
        "items": [
            {
                "id": r.id,
                "agent_id": r.agent_id,
                "session_id": r.session_id,
                "source": r.source,
                "model_name": r.model_name,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost": round(
                    _cost(r.model_name, r.input_tokens, r.output_tokens), 4,
                ),
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }
