"""Workflow execution engine.

Runs a node/edge graph as a DAG: nodes are ordered topologically, condition
branches gate which downstream nodes are reachable, and ``{{path}}`` template
references are resolved against a shared run context. Node execution streams
events (node started/finished, text deltas, workflow finished) which the
router relays over SSE.
"""

from __future__ import annotations

import ast
import asyncio
import json
import operator as _op
import re
from collections import deque
from typing import Any, AsyncGenerator

import httpx
from sqlmodel import Session

from ..knowledge import service as knowledge_service
from ..settings import get_settings

_settings = get_settings()
_TEMPLATE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")

_SAFE_OPS = {
    ast.Add: _op.add,
    ast.Sub: _op.sub,
    ast.Mult: _op.mul,
    ast.Div: _op.truediv,
    ast.FloorDiv: _op.floordiv,
    ast.Mod: _op.mod,
    ast.Pow: _op.pow,
    ast.USub: _op.neg,
    ast.UAdd: _op.pos,
}


def _safe_eval(expr: str) -> float:
    """Evaluate a pure-arithmetic expression (no names, calls or attributes)."""

    def ev(node: ast.AST) -> Any:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
            return _SAFE_OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
            return _SAFE_OPS[type(node.op)](ev(node.operand))
        raise ValueError("unsupported expression")

    return ev(ast.parse(str(expr), mode="eval").body)


def _parse_json_object(text: str) -> dict[str, Any]:
    """Best-effort parse of a JSON object out of an LLM reply."""
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"\{.*\}", text or "", re.S)
    if match:
        try:
            obj = json.loads(match.group(0))
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


# Modules pre-injected into the sandboxed `code` node namespace.
_CODE_SAFE_BUILTINS = {
    name: getattr(__builtins__, name, None) if not isinstance(__builtins__, dict) else __builtins__.get(name)
    for name in (
        "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
        "int", "len", "list", "map", "max", "min", "range", "round", "set",
        "sorted", "str", "sum", "tuple", "zip",
    )
}


_MISSING = object()


class _NodeFailure(Exception):
    """Raised internally when a node runner reports a failure.

    Node runners signal failure by returning an output dict with a truthy
    ``error`` key. The engine converts that into this exception so the same
    retry / error-strategy path handles both raised exceptions and
    error-dict outputs uniformly."""


def _parse_json_lenient(text: str) -> Any:
    """Best-effort parse of an LLM text response into JSON.

    Strips ``` fences and, if direct parsing fails, extracts the first
    balanced ``{...}`` / ``[...]`` span. Returns ``None`` on failure."""
    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s).strip()
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        match = re.search(r"(\{.*\}|\[.*\])", s, re.S)
        if match:
            try:
                return json.loads(match.group(1))
            except (ValueError, TypeError):
                return None
        return None


def _node_default_output(err_cfg: dict[str, Any]) -> dict[str, Any]:
    """Build a node's fallback output when its error strategy is ``default``.

    Accepts either a ``default_output`` object/JSON string or a plain
    ``default_text``; always exposes a ``text`` field so downstream templates
    referencing ``{{node.text}}`` keep working after a handled failure."""
    raw = err_cfg.get("default_output")
    out: dict[str, Any] = {}
    if isinstance(raw, dict):
        out = dict(raw)
    elif isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            out = parsed if isinstance(parsed, dict) else {"text": raw}
        except (ValueError, TypeError):
            out = {"text": raw}
    if "text" not in out:
        out["text"] = err_cfg.get("default_text", "") or ""
    return out


def _traverse(cur: Any, parts: list[str]) -> Any:
    """Walk a dotted path over nested dicts/lists. Supports integer list
    indices (e.g. ``items.0.id``). Returns ``_MISSING`` if any step fails."""
    for part in parts:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, (list, tuple)):
            try:
                idx = int(part)
            except (TypeError, ValueError):
                return _MISSING
            if -len(cur) <= idx < len(cur):
                cur = cur[idx]
            else:
                return _MISSING
        else:
            return _MISSING
    return cur


def _dig(item: Any, field: str | None) -> Any:
    """Read ``field`` (dot path) out of a dict/list item; identity if no field."""
    if not field:
        return item
    value = _traverse(item, str(field).split("."))
    return None if value is _MISSING else value


def _compare(left: Any, op: str, right: Any) -> bool:
    """Generic comparison used by list-operator filters and loop break tests."""
    if op in {"empty"}:
        return left in (None, "", [], {})
    if op in {"not_empty"}:
        return left not in (None, "", [], {})
    ls = "" if left is None else str(left)
    rs = "" if right is None else str(right)
    if op in {"contains"}:
        return rs in ls
    if op in {"not_contains"}:
        return rs not in ls
    if op in {"eq", "equals"}:
        return ls == rs
    if op in {"ne", "not_equals"}:
        return ls != rs
    if op in {"gt", "lt", "gte", "lte"}:
        try:
            lf, rf = float(left), float(right)
        except (TypeError, ValueError):
            return False
        return {
            "gt": lf > rf,
            "lt": lf < rf,
            "gte": lf >= rf,
            "lte": lf <= rf,
        }[op]
    return False


def _event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


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
        cur = _traverse(context, match.group(1).split("."))
        if cur is _MISSING:
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

            # Per-node error handling + retry (Dify-style): nodes may declare
            # ``error_handling`` with a retry policy and a strategy of
            # ``fail`` (abort run, default), ``default`` (substitute a fallback
            # output and continue) or ``branch`` (route to the ``fail`` handle).
            err_cfg = data.get("error_handling") or {}
            try:
                max_retries = max(0, int(err_cfg.get("max_retries") or 0))
            except (TypeError, ValueError):
                max_retries = 0
            try:
                retry_interval = max(0.0, float(err_cfg.get("retry_interval_ms") or 0) / 1000.0)
            except (TypeError, ValueError):
                retry_interval = 0.0
            strategy = err_cfg.get("strategy") or "fail"

            output: dict[str, Any] = {}
            node_failed = False
            attempt = 0
            while True:
                try:
                    output = {}
                    if ntype in {"start", "trigger-webhook", "trigger-schedule", "trigger-plugin"}:
                        output = dict(inputs)
                        self.context["start"] = dict(inputs)
                        for k, v in inputs.items():
                            self.context.setdefault(k, v)
                    elif ntype == "llm":
                        async for frame, text in self._run_llm(nid, data):
                            if frame:
                                yield frame
                            output["text"] = text
                        if data.get("output_format") == "json":
                            parsed = _parse_json_lenient(output.get("text", ""))
                            output["json"] = parsed
                            if isinstance(parsed, dict):
                                for k, v in parsed.items():
                                    output.setdefault(k, v)
                            elif parsed is None:
                                output["error"] = "LLM 未返回合法 JSON"
                    elif ntype == "agent":
                        async for frame, text in self._run_agent(nid, data):
                            if frame:
                                yield frame
                            output["text"] = text
                    elif ntype == "knowledge":
                        output = self._run_knowledge(data)
                    elif ntype == "ontology":
                        output = self._run_ontology(data)
                    elif ntype == "template":
                        output = {"text": _resolve(data.get("template", ""), self.context)}
                    elif ntype == "condition":
                        chosen = self._eval_condition(data)
                        branch[nid] = chosen
                        output = {"branch": chosen}
                    elif ntype == "question-classifier":
                        chosen, output = await self._run_classifier(data)
                        branch[nid] = chosen
                    elif ntype == "parameter-extractor":
                        output = await self._run_parameter_extractor(data)
                    elif ntype == "code":
                        output = self._run_code(data)
                    elif ntype == "http-request":
                        output = await self._run_http(data)
                    elif ntype == "tool":
                        output = await self._run_tool(data)
                    elif ntype == "list-operator":
                        output = self._run_list_operator(data)
                    elif ntype == "iteration":
                        output = self._run_iteration(data)
                    elif ntype == "loop":
                        output = self._run_loop(data)
                    elif ntype == "variable-aggregator":
                        output = self._run_variable_aggregator(data)
                    elif ntype == "assigner":
                        output = self._run_assigner(data)
                    elif ntype == "document-extractor":
                        output = self._run_document_extractor(data)
                    elif ntype == "datasource":
                        output = self._run_datasource(data)
                    elif ntype == "knowledge-index":
                        output = self._run_knowledge_index(data)
                    elif ntype == "human-input":
                        output = self._run_human_input(data)
                    elif ntype in {"answer", "end"}:
                        output = {"text": _resolve(data.get("answer", ""), self.context)}
                        final_answer = output["text"]
                    if isinstance(output, dict) and output.get("error"):
                        # A runner reported a failure via its output dict; route
                        # it through the same retry / error-strategy handling.
                        raise _NodeFailure(str(output["error"]))
                    break
                except Exception as exc:  # noqa: BLE001 - per-node error policy
                    if attempt < max_retries:
                        attempt += 1
                        yield _event(
                            {
                                "type": "node_retry",
                                "node_id": nid,
                                "attempt": attempt,
                                "max_retries": max_retries,
                                "error": str(exc),
                            },
                        )
                        if retry_interval:
                            await asyncio.sleep(retry_interval)
                        continue
                    if strategy == "default":
                        output = _node_default_output(err_cfg)
                        yield _event(
                            {
                                "type": "node_error",
                                "node_id": nid,
                                "error": str(exc),
                                "handled": "default",
                                "output": output,
                            },
                        )
                        break
                    if strategy == "branch":
                        node_failed = True
                        output = {"error": str(exc)}
                        branch[nid] = "fail"
                        yield _event(
                            {
                                "type": "node_error",
                                "node_id": nid,
                                "error": str(exc),
                                "handled": "fail-branch",
                            },
                        )
                        break
                    yield _event({"type": "error", "node_id": nid, "message": str(exc)})
                    return

            self.context[nid] = output
            yield _event({"type": "node_finished", "node_id": nid, "output": output})

            # Activate downstream nodes via taken edges.
            for e in self.out_edges.get(nid, []):
                handle = e.get("sourceHandle")
                if ntype in {"condition", "question-classifier"}:
                    default_handle = "true" if ntype == "condition" else ""
                    if (handle or default_handle) != branch.get(nid):
                        continue
                elif strategy == "branch":
                    # With a fail branch configured the ``fail`` handle is taken
                    # only on failure; normal handles only on success.
                    if node_failed:
                        if handle != "fail":
                            continue
                    elif handle == "fail":
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
        if data.get("output_format") == "json":
            schema = _resolve(data.get("json_schema", ""), self.context).strip()
            instr = "你必须只输出一个合法的 JSON 对象，不要包含任何解释文字或 markdown 代码块标记。"
            if schema:
                instr += f"\n输出需符合以下 JSON 结构/示例：\n{schema}"
            messages.append(
                Msg(name="system", role="system", content=[{"type": "text", "text": instr}]),
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
        raw_k = data.get("top_k")
        try:
            top_k = int(raw_k) if raw_k not in (None, "", 0, "0") else None
        except (TypeError, ValueError):
            top_k = None
        raw_thr = data.get("score_threshold")
        try:
            score_threshold = float(raw_thr) if raw_thr not in (None, "") else None
        except (TypeError, ValueError):
            score_threshold = None
        method = data.get("retrieval_method") or None
        hits = knowledge_service.retrieve(
            self.session,
            kb_id,
            query,
            top_k=top_k,
            score_threshold=score_threshold,
            method=method,
        )
        text = "\n\n".join(h["content"] for h in hits)
        return {
            "text": text,
            "chunks": [
                {"content": h["content"], "score": h["score"], "document_id": h["document_id"]}
                for h in hits
            ],
        }

    def _run_ontology(self, data: dict[str, Any]) -> dict[str, Any]:
        """Run a Palantir-style ontology operation: semantic object query,
        relationship traversal or action execution against a bound ontology."""
        from ..ontology import service as ontology_service

        ontology_id = data.get("ontology_id", "")
        op = data.get("operation", "query")
        try:
            if op == "query":
                filters = data.get("filters") or {}
                resolved = {k: _resolve(str(v), self.context) for k, v in filters.items()}
                result = ontology_service.query_objects(
                    self.session,
                    ontology_id,
                    data.get("object_type", ""),
                    {k: v for k, v in resolved.items() if v != ""} or None,
                    _resolve(data.get("search", ""), self.context) or None,
                    int(data.get("limit", 25)),
                )
            elif op == "traverse":
                result = ontology_service.traverse_link(
                    self.session,
                    ontology_id,
                    data.get("link_type", ""),
                    _resolve(data.get("source_object_id", ""), self.context),
                )
            elif op == "execute_action":
                params = data.get("parameters") or {}
                resolved = {k: _resolve(str(v), self.context) for k, v in params.items()}
                result = ontology_service.execute_action(
                    self.session,
                    ontology_id,
                    data.get("action", ""),
                    resolved or None,
                    _resolve(data.get("object_id", ""), self.context) or None,
                )
            else:
                result = {"error": f"Unknown ontology operation: {op!r}"}
        except ontology_service.OntologyError as exc:
            result = {"error": str(exc)}
        out: dict[str, Any] = {
            "result": result,
            "text": json.dumps(result, ensure_ascii=False, default=str),
        }
        if isinstance(result, dict) and isinstance(result.get("items"), list):
            out["objects"] = result["items"]
        if isinstance(result, dict) and result.get("error"):
            # Surface failures at the top level so the engine's per-node error
            # handling (retry / default / fail-branch) can act on them.
            out["error"] = result["error"]
        return out

    # ----- shared helpers ------------------------------------------------- #
    def _lookup(self, path: str) -> Any:
        """Resolve a ``a.b.c`` (or ``{{a.b.c}}``) reference to its raw value."""
        if not path:
            return None
        clean = path.replace("{{", "").replace("}}", "").strip()
        value = _traverse(self.context, clean.split("."))
        return None if value is _MISSING else value

    def _resolve_json(self, value: Any) -> dict[str, Any]:
        """Coerce a dict or JSON-string config value into a resolved dict."""
        if isinstance(value, dict):
            return {
                k: (_resolve(v, self.context) if isinstance(v, str) else v)
                for k, v in value.items()
            }
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(_resolve(value, self.context))
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    async def _model_complete(
        self,
        data: dict[str, Any],
        system: str,
        prompt: str,
    ) -> str:
        """Non-streaming single-shot model call used by classifier / extractor."""
        from agentscope.app.storage import ChatModelConfig, RedisStorage
        from agentscope.app._service._model import get_model
        from agentscope.message import Msg

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
            model.stream = False
            result = await model(messages=messages)
            if hasattr(result, "content"):
                return _resp_text(result.content)
            full = ""
            async for resp in result:  # pragma: no cover - defensive
                full = _resp_text(resp.content)
            return full

    # ----- AI nodes ------------------------------------------------------- #
    async def _run_classifier(self, data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Classify the input into one of ``classes``; the chosen class id is
        used as the branch handle (Dify question-classifier)."""
        classes: list[dict] = data.get("classes") or []
        query = _resolve(data.get("query", "") or "{{start.query}}", self.context)
        names = [c.get("name", "") for c in classes if c.get("name")]
        chosen_id, chosen_name = "", ""
        if data.get("credential_id") and names:
            try:
                system = (
                    "You are a precise text classifier. Reply with exactly one "
                    "category name from the provided list and nothing else."
                )
                prompt = f"Categories: {names}\n\nText:\n{query}\n\nCategory:"
                reply = (await self._model_complete(data, system, prompt)).strip()
                for c in classes:
                    if c.get("name") and c["name"] in reply:
                        chosen_id, chosen_name = c.get("id", ""), c["name"]
                        break
            except Exception:  # noqa: BLE001 - fall back to keyword scoring
                chosen_id = ""
        if not chosen_id and classes:  # keyword-overlap fallback
            best, score = classes[0], -1
            low = query.lower()
            for c in classes:
                s = sum(1 for w in str(c.get("name", "")).lower().split() if w in low)
                if s > score:
                    best, score = c, s
            chosen_id, chosen_name = best.get("id", ""), best.get("name", "")
        return chosen_id, {
            "class_id": chosen_id,
            "class_name": chosen_name,
            "text": chosen_name,
        }

    async def _run_parameter_extractor(self, data: dict[str, Any]) -> dict[str, Any]:
        """Extract structured parameters from text as JSON (Dify parameter-extractor)."""
        params: list[dict] = data.get("parameters_schema") or data.get("parameters") or []
        query = _resolve(data.get("query", "") or "{{start.query}}", self.context)
        schema = [
            {
                "name": p.get("name", ""),
                "type": p.get("type", "string"),
                "description": p.get("description", ""),
                "required": bool(p.get("required", False)),
            }
            for p in params
            if p.get("name")
        ]
        extracted: dict[str, Any] = {}
        if data.get("credential_id") and schema:
            try:
                system = "Extract the parameters and reply ONLY with a compact JSON object."
                prompt = (
                    f"Parameter schema:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
                    f"Text:\n{query}\n\nJSON:"
                )
                extracted = _parse_json_object(await self._model_complete(data, system, prompt))
            except Exception:  # noqa: BLE001
                extracted = {}
        out: dict[str, Any] = {
            "extracted": extracted,
            "text": json.dumps(extracted, ensure_ascii=False),
        }
        out.update(extracted)
        return out

    # ----- logic nodes ---------------------------------------------------- #
    def _run_code(self, data: dict[str, Any]) -> dict[str, Any]:
        """Execute a restricted Python snippet. Inputs are bound as locals and
        the snippet must assign an ``outputs`` dict (or define ``main``)."""
        lang = (data.get("language") or "python").lower()
        if lang not in {"python", "python3"}:
            return {"error": f"unsupported language: {lang}", "text": ""}
        inputs: dict[str, Any] = {}
        for v in data.get("variables") or []:
            name = v.get("name") or v.get("variable")
            if not name:
                continue
            raw = v.get("value", "")
            if isinstance(raw, str) and raw.strip().startswith("{{"):
                inputs[name] = self._lookup(raw)
            elif isinstance(raw, str):
                inputs[name] = _resolve(raw, self.context)
            else:
                inputs[name] = raw
        import datetime as _dt
        import math as _math

        glb: dict[str, Any] = {
            "__builtins__": _CODE_SAFE_BUILTINS,
            "json": json,
            "re": re,
            "math": _math,
            "datetime": _dt,
        }
        loc: dict[str, Any] = dict(inputs)
        try:
            exec(data.get("code", ""), glb, loc)  # noqa: S102 - sandboxed builtins
            result = loc.get("outputs")
            if result is None and callable(loc.get("main")):
                result = loc["main"](**inputs) if inputs else loc["main"]()
            if not isinstance(result, dict):
                result = {"result": result}
        except Exception as exc:  # noqa: BLE001 - report to the run log
            return {"error": str(exc), "text": ""}
        result.setdefault("text", json.dumps(result, ensure_ascii=False, default=str))
        return result

    async def _run_http(self, data: dict[str, Any]) -> dict[str, Any]:
        method = (data.get("method") or "GET").upper()
        url = _resolve(data.get("url", ""), self.context)
        headers = self._resolve_json(data.get("headers"))
        params = self._resolve_json(data.get("params"))
        timeout = float(data.get("timeout", 30) or 30)
        kwargs: dict[str, Any] = {"headers": headers or None, "params": params or None}
        body = data.get("body", "")
        if isinstance(body, str) and body.strip():
            resolved = _resolve(body, self.context)
            try:
                kwargs["json"] = json.loads(resolved)
            except json.JSONDecodeError:
                kwargs["content"] = resolved
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(method, url, **kwargs)
            return {"status": resp.status_code, "body": resp.text, "text": resp.text}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc), "status": 0, "body": "", "text": ""}

    async def _run_tool(self, data: dict[str, Any]) -> dict[str, Any]:
        """Invoke a built-in workflow tool (Dify tool node)."""
        tool = data.get("tool", "")
        args = {
            k: (_resolve(v, self.context) if isinstance(v, str) else v)
            for k, v in (data.get("parameters") or {}).items()
        }
        if tool == "current_time":
            import datetime as _dt

            text = _dt.datetime.now(_dt.timezone.utc).isoformat()
            return {"result": text, "text": text}
        if tool == "calculator":
            expr = str(args.get("expression") or _resolve(data.get("query", ""), self.context))
            try:
                val = _safe_eval(expr)
                return {"result": val, "text": str(val)}
            except (ValueError, SyntaxError, KeyError, TypeError) as exc:
                return {"error": str(exc), "text": ""}
        if tool == "knowledge_search":
            hits = knowledge_service.retrieve(
                self.session,
                str(args.get("kb_id", "")),
                str(args.get("query", "") or _resolve("{{start.query}}", self.context)),
            )
            text = "\n\n".join(h["content"] for h in hits)
            return {"result": hits, "text": text}
        if tool == "http_get":
            return await self._run_http({"method": "GET", "url": args.get("url", "")})
        return {"error": f"unknown tool: {tool}", "text": ""}

    def _run_list_operator(self, data: dict[str, Any]) -> dict[str, Any]:
        src = self._lookup(data.get("variable", ""))
        items = list(src) if isinstance(src, (list, tuple)) else []
        field = data.get("filter_field")
        if field and data.get("filter_value") not in (None, ""):
            op = data.get("filter_operator", "eq")
            target = data.get("filter_value")
            items = [it for it in items if _compare(_dig(it, field), op, target)]
        order = data.get("order")
        if order in {"asc", "desc"}:
            key = data.get("order_field")
            items = sorted(
                items,
                key=lambda it: _dig(it, key) if key else it,
                reverse=order == "desc",
            )
        limit = data.get("limit")
        if isinstance(limit, int) and limit > 0:
            items = items[:limit]
        extract = data.get("extract_field")
        if extract:
            items = [_dig(it, extract) for it in items]
        return {
            "result": items,
            "length": len(items),
            "first": items[0] if items else None,
            "text": json.dumps(items, ensure_ascii=False, default=str),
        }

    # ----- flow nodes ----------------------------------------------------- #
    def _run_iteration(self, data: dict[str, Any]) -> dict[str, Any]:
        src = self._lookup(data.get("input", ""))
        items = list(src) if isinstance(src, (list, tuple)) else []
        items = items[: int(data.get("max_items", 50) or 50)]
        template = data.get("item_template", "{{item}}")
        results = [
            _resolve(template, {**self.context, "item": item, "index": idx})
            for idx, item in enumerate(items)
        ]
        return {
            "result": results,
            "results": results,
            "length": len(results),
            "text": "\n".join(str(r) for r in results),
        }

    def _run_loop(self, data: dict[str, Any]) -> dict[str, Any]:
        max_loops = int(data.get("max_loops", 5) or 5)
        template = data.get("template", "")
        cond = data.get("break_when") or {}
        results: list[str] = []
        for i in range(max(0, min(max_loops, 1000))):
            merged = {**self.context, "loop_index": i, "loop_results": list(results)}
            results.append(_resolve(template, merged))
            if cond.get("variable"):
                left = _resolve(str(cond["variable"]), merged)
                if _compare(left, cond.get("operator", "eq"), cond.get("value", "")):
                    break
        return {
            "result": results,
            "iterations": len(results),
            "text": "\n".join(str(r) for r in results),
        }

    def _run_human_input(self, data: dict[str, Any]) -> dict[str, Any]:
        """Single-pass engine: surface the configured default reply as the
        human response so the graph can complete during a test run."""
        text = _resolve(data.get("default", "") or data.get("prompt", ""), self.context)
        return {"text": text, "approved": True}

    # ----- variable nodes ------------------------------------------------- #
    def _run_variable_aggregator(self, data: dict[str, Any]) -> dict[str, Any]:
        selectors = data.get("variables") or []
        values = [self._lookup(s) for s in selectors]
        if data.get("mode") == "array":
            out: Any = values
        else:  # first non-empty
            out = next((v for v in values if v not in (None, "", [], {})), "")
        return {
            "output": out,
            "text": out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, default=str),
        }

    def _run_assigner(self, data: dict[str, Any]) -> dict[str, Any]:
        assigned: dict[str, Any] = {}
        for a in data.get("assignments") or []:
            name = a.get("variable", "")
            if not name:
                continue
            raw = a.get("value", "")
            if isinstance(raw, str) and raw.strip().startswith("{{"):
                value = self._lookup(raw)
            elif isinstance(raw, str):
                value = _resolve(raw, self.context)
            else:
                value = raw
            self.context[name] = value
            assigned[name] = value
        out: dict[str, Any] = {
            "assigned": assigned,
            "text": json.dumps(assigned, ensure_ascii=False, default=str),
        }
        out.update(assigned)
        return out

    # ----- data nodes ----------------------------------------------------- #
    def _run_document_extractor(self, data: dict[str, Any]) -> dict[str, Any]:
        raw = _resolve(data.get("input", "") or "{{start.query}}", self.context)
        text = re.sub(r"[ \t]+\n", "\n", raw).strip()
        return {"text": text, "length": len(text)}

    def _run_datasource(self, data: dict[str, Any]) -> dict[str, Any]:
        """Datasource node: surface inline text or fetch a URL as the source."""
        source_type = data.get("source_type", "text")
        value = _resolve(data.get("value", ""), self.context)
        if source_type == "url" and value:
            import httpx

            try:
                resp = httpx.get(value, timeout=30, follow_redirects=True)
                return {"text": resp.text, "status": resp.status_code, "url": value}
            except Exception as exc:  # noqa: BLE001
                return {"text": "", "error": str(exc), "url": value}
        return {"text": value, "source_type": source_type}

    def _run_knowledge_index(self, data: dict[str, Any]) -> dict[str, Any]:
        """Knowledge-index node: write the resolved content into a KB and index
        it through the KB's configured ingestion pipeline."""
        from ..knowledge.models import Document, KnowledgeBase

        kb_id = data.get("kb_id", "")
        content = _resolve(data.get("input", "") or "{{start.query}}", self.context)
        if not (self.session and kb_id and content):
            return {"text": content, "indexed": False}
        kb = self.session.get(KnowledgeBase, kb_id)
        if kb is None:
            return {"text": content, "indexed": False, "error": "kb not found"}
        doc = Document(kb_id=kb_id, name=data.get("name") or "workflow", content=content)
        self.session.add(doc)
        self.session.commit()
        self.session.refresh(doc)
        knowledge_service.ingest_document(self.session, doc, kb)
        return {"text": content, "indexed": True, "document_id": doc.id}

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
