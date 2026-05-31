#!/usr/bin/env python3
"""Seed a demo knowledge base + RAG workflow (Dify-style).

Creates:

* A **knowledge base** ("风控知识库") with one anti-money-laundering
  document, ingested through the default extract → clean → split → index
  pipeline (TF-IDF retrieval).
* A **workflow** ("风控问答工作流") wiring start → knowledge retrieval →
  LLM generation → answer, i.e. retrieval-augmented generation over the
  knowledge base.

The LLM node needs a model credential. The script looks one up at runtime
(preferring a DeepSeek credential) so no secret is hard-coded here.

Usage::

    python scripts/seed_knowledge_workflow.py [BASE_URL] [USER_ID]

Defaults: BASE_URL=http://localhost:8000, USER_ID=admin

Safe to re-run: existing demo objects with the same name are deleted first.
"""

from __future__ import annotations

import sys

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
USER = sys.argv[2] if len(sys.argv) > 2 else "admin"
H = {"X-User-ID": USER, "Content-Type": "application/json"}

KB_NAME = "风控知识库"
WF_NAME = "风控问答工作流"

DOC_CONTENT = (
    "电汇(wire)交易若单笔金额超过一万美元需上报。\n\n"
    "可疑交易识别：短时间内多笔小额拆分转账（structuring）属于高风险行为，"
    "应触发人工审查。\n\n"
    "对于标记为高风险的交易，风控系统应自动冻结账户并通知合规团队。\n\n"
    "KYC：开户时必须完成实名认证与受益所有人识别。"
)


def _req(method: str, path: str, **kw):
    resp = requests.request(method, f"{BASE}{path}", headers=H, timeout=60, **kw)
    if resp.status_code >= 400:
        raise SystemExit(f"{method} {path} -> {resp.status_code}: {resp.text}")
    return resp.json() if resp.text else {}


def resolve_credential() -> tuple[str | None, str | None]:
    """Return (credential_id, credential_type), preferring DeepSeek."""
    data = _req("GET", "/credential/")
    creds = data.get("credentials", [])
    if not creds:
        return None, None
    for cred in creds:
        ctype = (cred.get("data") or {}).get("type", "")
        if "deepseek" in ctype.lower():
            return cred["id"], ctype
    first = creds[0]
    return first["id"], (first.get("data") or {}).get("type", "")


def reset_kb() -> str:
    existing = _req("GET", "/admin/knowledge-bases/").get("items", [])
    for item in existing:
        kb = item.get("kb", item)
        if kb.get("name") == KB_NAME:
            _req("DELETE", f"/admin/knowledge-bases/{kb['id']}")
    kb = _req(
        "POST",
        "/admin/knowledge-bases/",
        json={
            "name": KB_NAME,
            "description": "反欺诈与合规知识",
            "icon": "lucide:shield",
            "top_k": 4,
        },
    )
    kb_id = kb["id"]
    doc = _req(
        "POST",
        f"/admin/knowledge-bases/{kb_id}/documents",
        json={"name": "反洗钱规则", "content": DOC_CONTENT},
    )
    print(f"[seed] knowledge base {kb_id} ({doc.get('chunk_count', '?')} chunks)")
    return kb_id


def reset_workflow(kb_id: str, credential_id: str | None, credential_type: str | None):
    existing = _req("GET", "/admin/workflows/").get("items", [])
    for wf in existing:
        if wf.get("name") == WF_NAME:
            _req("DELETE", f"/admin/workflows/{wf['id']}")

    llm_data = {
        "title": "LLM 生成",
        "model": "deepseek-chat",
        "parameters": {"temperature": 0.2, "max_tokens": 256},
        "system_prompt": "你是风控合规助手，依据给定资料回答，不要编造。",
        "prompt": "资料：\n{{kb.text}}\n\n问题：{{start.query}}\n\n请基于资料简洁回答。",
    }
    if credential_id:
        llm_data["type"] = credential_type
        llm_data["credential_id"] = credential_id
    else:
        print(
            "[seed] WARNING: no credential found — open the LLM node in the "
            "canvas and pick a credential before running the workflow.",
        )

    graph = {
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "position": {"x": 0, "y": 0},
                "data": {
                    "title": "开始",
                    "variables": [{"name": "query", "label": "问题", "type": "string"}],
                },
            },
            {
                "id": "kb",
                "type": "knowledge",
                "position": {"x": 250, "y": 0},
                "data": {
                    "title": "知识检索",
                    "kb_id": kb_id,
                    "query": "{{start.query}}",
                    "top_k": 3,
                },
            },
            {
                "id": "llm",
                "type": "llm",
                "position": {"x": 500, "y": 0},
                "data": llm_data,
            },
            {
                "id": "answer",
                "type": "answer",
                "position": {"x": 750, "y": 0},
                "data": {"title": "回复", "answer": "{{llm.text}}"},
            },
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "kb"},
            {"id": "e2", "source": "kb", "target": "llm"},
            {"id": "e3", "source": "llm", "target": "answer"},
        ],
    }
    wf = _req(
        "POST",
        "/admin/workflows/",
        json={
            "name": WF_NAME,
            "description": "知识检索增强问答",
            "icon": "lucide:workflow",
            "graph": graph,
        },
    )
    print(f"[seed] workflow {wf['id']} (4 nodes: start → kb → llm → answer)")


def main() -> None:
    kb_id = reset_kb()
    cred_id, cred_type = resolve_credential()
    reset_workflow(kb_id, cred_id, cred_type)
    print("[seed] done. Try: agentscope-admin workflow run <id> --input query=\"电汇要上报吗\"")


if __name__ == "__main__":
    main()
