"""``agentscope-admin`` command-line interface.

A thin, dependency-light CLI for operating the AgentScope Admin platform.

It has two flavours of commands:

* **Local process commands** that run on this machine directly:
  ``serve`` (launch the API) and ``seed`` (load the demo ontology).
* **API commands** that talk to a *running* backend over HTTP, mirroring
  the same REST endpoints the web UI uses:
  ``agents``, ``knowledge``, ``workflow``, ``publish`` and ``keys``.

Usage examples::

    agentscope-admin serve --reload
    agentscope-admin seed
    agentscope-admin agents list
    agentscope-admin knowledge list
    agentscope-admin knowledge add-doc <kb_id> --file notes.txt --name Notes
    agentscope-admin knowledge retrieve <kb_id> "可疑交易上报阈值"
    agentscope-admin workflow list
    agentscope-admin workflow run <workflow_id> --input query="电汇要上报吗"
    agentscope-admin publish list
    agentscope-admin keys create <app_id> --name ci-key

Global options (or environment variables) configure the target server:

    --base-url   (env AGENTSCOPE_ADMIN_BASE_URL, default http://localhost:8000)
    --user       (env AGENTSCOPE_ADMIN_USER,     default "admin")
    --json       print raw JSON instead of human-friendly tables
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests

SERVER_DIR = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = os.environ.get("AGENTSCOPE_ADMIN_BASE_URL", "http://localhost:8000")
DEFAULT_USER = os.environ.get("AGENTSCOPE_ADMIN_USER", "admin")


# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #
def _err(msg: str) -> "None":
    print(f"\033[31m[error]\033[0m {msg}", file=sys.stderr)


def _ok(msg: str) -> None:
    print(f"\033[32m[ok]\033[0m {msg}")


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _print_table(rows: list[dict], columns: list[str]) -> None:
    """Render a minimal fixed-width table."""
    if not rows:
        print("(empty)")
        return
    widths = {c: len(c) for c in columns}
    for row in rows:
        for c in columns:
            widths[c] = max(widths[c], len(str(row.get(c, ""))))
    header = "  ".join(c.ljust(widths[c]) for c in columns)
    print(header)
    print("  ".join("-" * widths[c] for c in columns))
    for row in rows:
        print("  ".join(str(row.get(c, "")).ljust(widths[c]) for c in columns))


# --------------------------------------------------------------------------- #
# HTTP client
# --------------------------------------------------------------------------- #
class ApiClient:
    """Tiny REST client carrying the ``X-User-ID`` identity header."""

    def __init__(self, base_url: str, user: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-User-ID": user, "Content-Type": "application/json"}

    def request(self, method: str, path: str, **kw: Any) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = requests.request(
                method, url, headers=self.headers, timeout=60, **kw
            )
        except requests.exceptions.ConnectionError as exc:
            raise SystemExit(
                f"cannot reach backend at {self.base_url} "
                f"(is it running? try `agentscope-admin serve`)\n  {exc}"
            )
        if resp.status_code >= 400:
            raise SystemExit(f"{method} {path} -> {resp.status_code}: {resp.text}")
        return resp.json() if resp.text else {}

    def get(self, path: str, **kw: Any) -> Any:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw: Any) -> Any:
        return self.request("POST", path, **kw)

    def delete(self, path: str, **kw: Any) -> Any:
        return self.request("DELETE", path, **kw)

    def stream(self, path: str, payload: dict):
        """Yield decoded SSE ``data:`` frames from a streaming endpoint."""
        url = f"{self.base_url}{path}"
        with requests.post(
            url, headers=self.headers, json=payload, stream=True, timeout=300
        ) as resp:
            if resp.status_code >= 400:
                raise SystemExit(f"POST {path} -> {resp.status_code}: {resp.text}")
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw or not raw.startswith("data:"):
                    continue
                data = raw[len("data:") :].strip()
                if not data:
                    continue
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    continue


# --------------------------------------------------------------------------- #
# Local process commands: serve / seed
# --------------------------------------------------------------------------- #
def cmd_serve(args: argparse.Namespace) -> int:
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if args.reload:
        cmd.append("--reload")
    print(f"[serve] {' '.join(cmd)}  (cwd={SERVER_DIR})")
    return subprocess.call(cmd, cwd=str(SERVER_DIR))


def cmd_seed(args: argparse.Namespace) -> int:
    script = SERVER_DIR / "scripts" / "seed_risk_ontology.py"
    if not script.exists():
        _err(f"seed script not found: {script}")
        return 1
    cmd = [sys.executable, str(script), args.base_url, args.user]
    print(f"[seed] {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(SERVER_DIR))


# --------------------------------------------------------------------------- #
# agents
# --------------------------------------------------------------------------- #
def cmd_agents(args: argparse.Namespace) -> int:
    client = ApiClient(args.base_url, args.user)
    if args.action == "list":
        data = client.get("/agent/")
        agents = data.get("agents", data) if isinstance(data, dict) else data
        if args.json:
            _print_json(agents)
            return 0
        rows = [
            {
                "id": a.get("agent_id") or a.get("id", ""),
                "name": (a.get("data") or {}).get("name") or a.get("name", ""),
            }
            for a in agents
        ]
        _print_table(rows, ["id", "name"])
        return 0
    if args.action == "create":
        payload = {
            "name": args.name,
            "system_prompt": args.system_prompt,
            "context_config": {},
            "react_config": {},
        }
        out = client.post("/agent/", json=payload)
        _ok(f"created agent {out.get('agent_id', out)}")
        return 0
    if args.action == "delete":
        client.delete(f"/agent/{args.id}")
        _ok(f"deleted agent {args.id}")
        return 0
    return 1


# --------------------------------------------------------------------------- #
# knowledge
# --------------------------------------------------------------------------- #
def cmd_knowledge(args: argparse.Namespace) -> int:
    client = ApiClient(args.base_url, args.user)
    base = "/admin/knowledge-bases"
    if args.action == "list":
        data = client.get(f"{base}/")
        items = data.get("items", data) if isinstance(data, dict) else data
        if args.json:
            _print_json(items)
            return 0
        rows = []
        for item in items:
            kb = item.get("kb", item)
            rows.append(
                {
                    "id": kb.get("id", ""),
                    "name": kb.get("name", ""),
                    "docs": item.get("doc_count", ""),
                    "chunks": item.get("chunk_count", ""),
                    "top_k": kb.get("top_k", ""),
                }
            )
        _print_table(rows, ["id", "name", "docs", "chunks", "top_k"])
        return 0
    if args.action == "create":
        payload = {"name": args.name, "description": args.description or ""}
        out = client.post(f"{base}/", json=payload)
        _ok(f"created knowledge base {out.get('id', out)}")
        return 0
    if args.action == "add-doc":
        if args.file:
            content = Path(args.file).read_text(encoding="utf-8")
            name = args.name or Path(args.file).name
        else:
            content = args.text or sys.stdin.read()
            name = args.name or "document"
        out = client.post(
            f"{base}/{args.kb_id}/documents",
            json={"name": name, "content": content},
        )
        _ok(
            f"indexed document {out.get('id', '')} "
            f"({out.get('chunk_count', '?')} chunks)"
        )
        return 0
    if args.action == "reindex":
        client.post(f"{base}/{args.kb_id}/documents/{args.doc_id}/reindex")
        _ok(f"reindexed document {args.doc_id}")
        return 0
    if args.action == "retrieve":
        out = client.post(
            f"{base}/{args.kb_id}/retrieve",
            json={"query": args.query, "top_k": args.top_k},
        )
        items = out.get("items", [])
        if args.json:
            _print_json(out)
            return 0
        if not items:
            print("(no hits)")
            return 0
        for hit in items:
            print(f"\033[33mscore {hit.get('score')}\033[0m")
            print(hit.get("content", ""))
            print("-" * 40)
        return 0
    if args.action == "delete":
        client.delete(f"{base}/{args.kb_id}")
        _ok(f"deleted knowledge base {args.kb_id}")
        return 0
    return 1


# --------------------------------------------------------------------------- #
# workflow
# --------------------------------------------------------------------------- #
def cmd_workflow(args: argparse.Namespace) -> int:
    client = ApiClient(args.base_url, args.user)
    base = "/admin/workflows"
    if args.action == "list":
        data = client.get(f"{base}/")
        items = data.get("items", data) if isinstance(data, dict) else data
        if args.json:
            _print_json(items)
            return 0
        rows = [
            {
                "id": w.get("id", ""),
                "name": w.get("name", ""),
                "nodes": len((w.get("graph") or {}).get("nodes", [])),
                "enabled": w.get("enabled", ""),
            }
            for w in items
        ]
        _print_table(rows, ["id", "name", "nodes", "enabled"])
        return 0
    if args.action == "create":
        payload = {"name": args.name, "description": args.description or ""}
        out = client.post(f"{base}/", json=payload)
        _ok(f"created workflow {out.get('id', out)}")
        return 0
    if args.action == "run":
        inputs: dict[str, str] = {}
        for pair in args.input or []:
            if "=" not in pair:
                _err(f"--input expects key=value, got: {pair}")
                return 1
            key, value = pair.split("=", 1)
            inputs[key] = value
        final = ""
        for event in client.stream(f"{base}/{args.workflow_id}/run", {"inputs": inputs}):
            etype = event.get("type")
            if etype == "node_started":
                print(f"\033[36m▶ {event.get('title') or event.get('node_id')}\033[0m")
            elif etype == "node_finished":
                print(f"\033[32m✓ {event.get('node_id')}\033[0m")
            elif etype == "text_delta":
                sys.stdout.write(event.get("delta", ""))
                sys.stdout.flush()
            elif etype == "workflow_finished":
                final = event.get("output", final)
            elif etype == "error":
                _err(event.get("message", "workflow error"))
                return 1
        print("\n" + "=" * 40)
        print(final)
        return 0
    if args.action == "delete":
        client.delete(f"{base}/{args.workflow_id}")
        _ok(f"deleted workflow {args.workflow_id}")
        return 0
    return 1


# --------------------------------------------------------------------------- #
# publish & keys
# --------------------------------------------------------------------------- #
def cmd_publish(args: argparse.Namespace) -> int:
    client = ApiClient(args.base_url, args.user)
    base = "/admin/published-apps"
    if args.action == "list":
        data = client.get(f"{base}/")
        items = data.get("items", data) if isinstance(data, dict) else data
        if args.json:
            _print_json(items)
            return 0
        rows = []
        for item in items:
            app = item.get("app", item)
            rows.append(
                {
                    "id": app.get("id", ""),
                    "name": app.get("name", ""),
                    "token": app.get("token", ""),
                    "enabled": app.get("enabled", ""),
                    "keys": item.get("key_count", ""),
                }
            )
        _print_table(rows, ["id", "name", "token", "enabled", "keys"])
        return 0
    if args.action == "create":
        payload = {"agent_id": args.agent_id, "name": args.name}
        out = client.post(f"{base}/", json=payload)
        _ok(f"published app {out.get('id', '')} token={out.get('token', '')}")
        return 0
    if args.action == "delete":
        client.delete(f"{base}/{args.app_id}")
        _ok(f"deleted published app {args.app_id}")
        return 0
    return 1


def cmd_keys(args: argparse.Namespace) -> int:
    client = ApiClient(args.base_url, args.user)
    base = f"/admin/published-apps/{args.app_id}/keys"
    if args.action == "list":
        data = client.get(base)
        items = data.get("items", data) if isinstance(data, dict) else data
        if args.json:
            _print_json(items)
            return 0
        rows = [
            {
                "id": k.get("id", ""),
                "name": k.get("name", ""),
                "prefix": k.get("key_prefix", ""),
                "revoked": k.get("revoked", ""),
                "last_used": k.get("last_used_at", "") or "",
            }
            for k in items
        ]
        _print_table(rows, ["id", "name", "prefix", "revoked", "last_used"])
        return 0
    if args.action == "create":
        out = client.post(base, json={"name": args.name})
        _ok("created API key (shown once):")
        print(out.get("key") or json.dumps(out, ensure_ascii=False))
        return 0
    if args.action == "revoke":
        client.post(f"{base}/{args.key_id}/revoke")
        _ok(f"revoked key {args.key_id}")
        return 0
    return 1


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentscope-admin",
        description="Operate the AgentScope Admin platform from the terminal.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"backend base URL (default {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--user",
        default=DEFAULT_USER,
        help=f'acting user id, sent as X-User-ID (default "{DEFAULT_USER}")',
    )
    parser.add_argument(
        "--json", action="store_true", help="print raw JSON instead of tables"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # serve
    p_serve = sub.add_parser("serve", help="launch the FastAPI backend")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--reload", action="store_true", help="auto-reload")
    p_serve.set_defaults(func=cmd_serve)

    # seed
    p_seed = sub.add_parser("seed", help="seed the demo enterprise-risk ontology")
    p_seed.set_defaults(func=cmd_seed)

    # agents
    p_agents = sub.add_parser("agents", help="manage agents")
    s = p_agents.add_subparsers(dest="action", required=True)
    s.add_parser("list", help="list agents")
    c = s.add_parser("create", help="create an agent")
    c.add_argument("name")
    c.add_argument("--system-prompt", default="You are a helpful assistant.")
    d = s.add_parser("delete", help="delete an agent")
    d.add_argument("id")
    p_agents.set_defaults(func=cmd_agents)

    # knowledge
    p_kn = sub.add_parser("knowledge", help="manage knowledge bases")
    s = p_kn.add_subparsers(dest="action", required=True)
    s.add_parser("list", help="list knowledge bases")
    c = s.add_parser("create", help="create a knowledge base")
    c.add_argument("name")
    c.add_argument("--description", default="")
    a = s.add_parser("add-doc", help="add & index a document")
    a.add_argument("kb_id")
    a.add_argument("--file", help="path to a text file")
    a.add_argument("--text", help="inline text (else reads stdin)")
    a.add_argument("--name", help="document name")
    r = s.add_parser("reindex", help="reindex a document")
    r.add_argument("kb_id")
    r.add_argument("doc_id")
    rt = s.add_parser("retrieve", help="retrieval test")
    rt.add_argument("kb_id")
    rt.add_argument("query")
    rt.add_argument("--top-k", type=int, default=4)
    dd = s.add_parser("delete", help="delete a knowledge base")
    dd.add_argument("kb_id")
    p_kn.set_defaults(func=cmd_knowledge)

    # workflow
    p_wf = sub.add_parser("workflow", help="manage & run workflows")
    s = p_wf.add_subparsers(dest="action", required=True)
    s.add_parser("list", help="list workflows")
    c = s.add_parser("create", help="create a workflow")
    c.add_argument("name")
    c.add_argument("--description", default="")
    rn = s.add_parser("run", help="run a workflow (streams output)")
    rn.add_argument("workflow_id")
    rn.add_argument(
        "--input",
        action="append",
        metavar="KEY=VALUE",
        help="start variable, repeatable",
    )
    dd = s.add_parser("delete", help="delete a workflow")
    dd.add_argument("workflow_id")
    p_wf.set_defaults(func=cmd_workflow)

    # publish
    p_pub = sub.add_parser("publish", help="manage published apps")
    s = p_pub.add_subparsers(dest="action", required=True)
    s.add_parser("list", help="list published apps")
    c = s.add_parser("create", help="publish an agent as an app")
    c.add_argument("agent_id")
    c.add_argument("--name", required=True)
    dd = s.add_parser("delete", help="delete a published app")
    dd.add_argument("app_id")
    p_pub.set_defaults(func=cmd_publish)

    # keys
    p_keys = sub.add_parser("keys", help="manage published-app API keys")
    s = p_keys.add_subparsers(dest="action", required=True)
    ls = s.add_parser("list", help="list API keys")
    ls.add_argument("app_id")
    c = s.add_parser("create", help="create an API key")
    c.add_argument("app_id")
    c.add_argument("--name", required=True)
    rv = s.add_parser("revoke", help="revoke an API key")
    rv.add_argument("app_id")
    rv.add_argument("key_id")
    p_keys.set_defaults(func=cmd_keys)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
