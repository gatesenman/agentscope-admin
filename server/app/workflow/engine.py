"""Workflow execution engine.

Runs a node/edge graph as a DAG: nodes are ordered topologically, condition
branches gate which downstream nodes are reachable, and ``{{path}}`` template
references are resolved against a shared run context. Node execution streams
events (node started/finished, text deltas, workflow finished) which the
router relays over SSE.
"""

from __future__ import annotations

import json
import re
from collections import deque
from typing import Any, AsyncGenerator

import httpx
from sqlmodel import Session

from ..knowledge import service as knowledge_service
from ..settings import get_settings

_settings = get_settings()
_TEMPLATE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


def _event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _resp_text(content: Any) -> str:
    """Extract concatenated text from a ChatResponse ``content`` list."""
    out: list[str] = []
    for block in content or []:
        if isinstance(block, dict):
            if block.get("type") == "text":
                out.append(block.get("text", ""))
        elif getattr(block, "type", None) == "text":
            out.append(getattr(block, "text", ""))
    return "".join(out)


def _resolve(template: str, context: dict[str, Any]) -> str:
    """Resolve ``{{a.b.c}}`` references against the run context."""

    def repl(match: re.Match[str]) -> str:
        path = match.group(1).split(".")
        cur: Any = context
        for part in path:
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return ""
        return cur if isinstance(cur, str) else json.dumps(cur, ensure_ascii=False)

    return _TEMPLATE.sub(repl, template or "")


def _topo_order(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Kahn topological sort over node ids; tolerates cycles by appending
    any leftover nodes in declaration order."""
    ids = [n["id"] for n in nodes]
    indeg = {i: 0 for i in ids}
    adj: dict[str, list[str]] = {i: [] for i in ids}
    for e in edges:
        if e["source"] in adj and e["target"] in indeg:
            adj[e["source"]].append(e["target"])
            indeg[e["target"]] += 1
    queue = deque([i for i in ids if indeg[i] == 0])
    order: list[str] = []
    while queue:
        cur = queue.popleft()
        order.append(cur)
        for nxt in adj[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    for i in ids:  # fallback for any node left out by a cycle
        if i not in order:
            order.append(i)
    return order


class WorkflowEngine:
    """Executes one workflow graph against a set of start inputs."""

    def __init__(self, graph: dict[str, Any], session: Session, user_id: str = "admin"):
        self.nodes: dict[str, dict] = {n["id"]: n for n in graph.get("nodes", [])}
        self.edges: list[dict] = graph.get("edges", [])
        self.session = session
        self.user_id = user_id
        self.context: dict[str, Any] = {}
        # Outgoing edges grouped by source node.
        self.out_edges: dict[str, list[dict]] = {}
        for e in self.edges:
            self.out_edges.setdefault(e["source"], []).append(e)

    async def run(self, inputs: dict[str, Any]) -> AsyncGenerator[str, None]:
        yield _event({"type": "workflow_started"})
        try:
            async for frame in self._run(inputs):
                yield frame
        except Exception as exc:  # noqa: BLE001 - report failures to the client
            yield _event({"type": "error", "message": str(exc)})

    async def _run(self, inputs: dict[str, Any]) -> AsyncGenerator[str, None]:
        order = _topo_order(list(self.nodes.values()), self.edges)
        reachable: set[str] = set()
        # Branch chosen by each condition node: maps node_id -> "true"/"false".
        branch: dict[str, str] = {}

        # Seed reachability from nodes with no incoming edges (start nodes).
        targets = {e["target"] for e in self.edges}
        for nid in order:
            if nid not in targets:
                reachable.add(nid)

        final_answer = ""
        for nid in order:
            node = self.nodes[nid]
            if nid not in reachable:
                continue
            ntype = node.get("type", "")
            data = node.get("data", {})
            title = data.get("title") or ntype
            yield _event(
                {"type": "node_started", "node_id": nid, "node_type": ntype, "title": title},
            )

            output: dict[str, Any] = {}
            if ntype == "start":
                output = dict(inputs)
                self.context["start"] = dict(inputs)
                for k, v in inputs.items():
                    self.context.setdefault(k, v)
            elif ntype == "llm":
                async for frame, text in self._run_llm(nid, data):
                    if frame:
                        yield frame
                    output["text"] = text
            elif ntype == "agent":
                async for frame, text in self._run_agent(nid, data):
                    if frame:
                        yield frame
                    output["text"] = text
            elif ntype == "knowledge":
                output = self._run_knowledge(data)
            elif ntype == "template":
                output = {"text": _resolve(data.get("template", ""), self.context)}
            elif ntype == "condition":
                chosen = self._eval_condition(data)
                branch[nid] = chosen
                output = {"branch": chosen}
            elif ntype in {"answer", "end"}:
                output = {"text": _resolve(data.get("answer", ""), self.context)}
                final_answer = output["text"]

            self.context[nid] = output
            yield _event({"type": "node_finished", "node_id": nid, "output": output})

            # Activate downstream nodes via taken edges.
            for e in self.out_edges.get(nid, []):
                if ntype == "condition":
                    handle = e.get("sourceHandle") or "true"
                    if handle != branch.get(nid):
                        continue
                reachable.add(e["target"])

        yield _event({"type": "workflow_finished", "output": final_answer})

    # ----- node runners --------------------------------------------------- #
    async def _run_llm(
        self,
        nid: str,
        data: dict[str, Any],
    ) -> AsyncGenerator[tuple[str | None, str], None]:
        from agentscope.app.storage import ChatModelConfig, RedisStorage
        from agentscope.app._service._model import get_model
        from agentscope.message import Msg

        system = _resolve(data.get("system_prompt", ""), self.context)
        prompt = _resolve(data.get("prompt", ""), self.context)
        messages = []
        if system:
            messages.append(
                Msg(name="system", role="system", content=[{"type": "text", "text": system}]),
            )
        messages.append(
            Msg(name="user", role="user", content=[{"type": "text", "text": prompt}]),
        )
        cfg = ChatModelConfig(
            type=data.get("type", ""),
            credential_id=data.get("credential_id", ""),
            model=data.get("model", ""),
            parameters=data.get("parameters", {}) or {},
        )
        async with RedisStorage(
            host=_settings.redis_host,
            port=_settings.redis_port,
            db=_settings.redis_db,
            password=_settings.redis_password,
        ) as storage:
            model = await get_model(self.user_id, cfg, storage)
            model.stream = True
            gen = await model(messages=messages)
            full = ""
            async for resp in gen:
                text = _resp_text(resp.content)
                # The stream emits deltas then a final cumulative frame; merge
                # both by detecting the cumulative case.
                if len(text) >= len(full) and text.startswith(full):
                    delta = text[len(full) :]
                    full = text
                else:
                    delta = text
                    full += text
                if delta:
                    yield (
                        _event({"type": "text_delta", "node_id": nid, "delta": delta}),
                        full,
                    )
            yield (None, full)

    async def _run_agent(
        self,
        nid: str,
        data: dict[str, Any],
    ) -> AsyncGenerator[tuple[str | None, str], None]:
        agent_id = data.get("agent_id", "")
        query = _resolve(data.get("prompt", "") or "{{start.query}}", self.context)
        base = _settings.internal_base_url
        headers = {"X-User-ID": self.user_id}
        blocks: dict[str, str] = {}
        order: list[str] = []
        async with httpx.AsyncClient(base_url=base, timeout=None) as client:
            resp = await client.post(
                "/sessions/",
                json={"agent_id": agent_id, "name": f"workflow-{nid}"},
                headers=headers,
            )
            resp.raise_for_status()
            session_id = resp.json()["session_id"]
            chat_body = {
                "agent_id": agent_id,
                "session_id": session_id,
                "input": {
                    "name": "user",
                    "role": "user",
                    "content": [{"type": "text", "text": query}],
                },
            }
            async with client.stream("POST", "/chat/", json=chat_body, headers=headers) as s:
                async for line in s.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    try:
                        event = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "TEXT_BLOCK_DELTA":
                        bid = event.get("block_id", "")
                        if bid not in blocks:
                            blocks[bid] = ""
                            order.append(bid)
                        blocks[bid] += event.get("delta", "")
                        yield (
                            _event(
                                {
                                    "type": "text_delta",
                                    "node_id": nid,
                                    "delta": event.get("delta", ""),
                                },
                            ),
                            "".join(blocks[b] for b in order),
                        )
        yield (None, "".join(blocks[b] for b in order))

    def _run_knowledge(self, data: dict[str, Any]) -> dict[str, Any]:
        kb_id = data.get("kb_id", "")
        query = _resolve(data.get("query", "") or "{{start.query}}", self.context)
        hits = knowledge_service.retrieve(
            self.session,
            kb_id,
            query,
            top_k=data.get("top_k"),
        )
        text = "\n\n".join(h["content"] for h in hits)
        return {
            "text": text,
            "chunks": [
                {"content": h["content"], "score": h["score"], "document_id": h["document_id"]}
                for h in hits
            ],
        }

    def _eval_condition(self, data: dict[str, Any]) -> str:
        left = _resolve(data.get("variable", ""), self.context)
        op = data.get("operator", "contains")
        right = _resolve(data.get("value", ""), self.context) or data.get("value", "")
        result = False
        if op == "contains":
            result = right in left
        elif op == "not_contains":
            result = right not in left
        elif op in {"equals", "eq"}:
            result = left == right
        elif op in {"not_equals", "ne"}:
            result = left != right
        elif op == "empty":
            result = not left
        elif op == "not_empty":
            result = bool(left)
        elif op in {"gt", "lt", "gte", "lte"}:
            try:
                lf, rf = float(left), float(right)
                result = {
                    "gt": lf > rf,
                    "lt": lf < rf,
                    "gte": lf >= rf,
                    "lte": lf <= rf,
                }[op]
            except ValueError:
                result = False
        return "true" if result else "false"
