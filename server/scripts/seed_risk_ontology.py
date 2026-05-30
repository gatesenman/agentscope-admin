#!/usr/bin/env python3
"""Seed a rich, realistic ontology for demos.

Domain: **enterprise risk & supply chain** (Palantir-style). It models
organizations, people, bank accounts, transactions, products, orders,
suppliers, sanctions and risk events, together with the relations and
actions an analyst agent would use to perform semantic queries and act on
the graph.

Usage::

    python scripts/seed_risk_ontology.py [BASE_URL] [USER_ID]

Defaults: BASE_URL=http://localhost:8000, USER_ID=admin

The script is safe to re-run: if an ontology with the same ``api_name``
already exists it is deleted and rebuilt.
"""

from __future__ import annotations

import sys

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
USER = sys.argv[2] if len(sys.argv) > 2 else "admin"
H = {"X-User-ID": USER, "Content-Type": "application/json"}

API_NAME = "enterprise_risk"


def _req(method: str, path: str, **kw):
    resp = requests.request(method, f"{BASE}{path}", headers=H, timeout=30, **kw)
    if resp.status_code >= 400:
        raise SystemExit(f"{method} {path} -> {resp.status_code}: {resp.text}")
    return resp.json() if resp.text else {}


def prop(api, name, dtype="string", **extra):
    return {
        "api_name": api,
        "display_name": name,
        "data_type": dtype,
        **extra,
    }


def reset_ontology() -> str:
    existing = _req("GET", "/ontology/").get("items", [])
    for o in existing:
        if o["api_name"] == API_NAME:
            _req("DELETE", f"/ontology/{o['id']}")
    ont = _req(
        "POST",
        "/ontology/",
        json={
            "api_name": API_NAME,
            "display_name": "企业风控本体",
            "description": "企业风控与供应链语义模型：组织 / 人员 / 账户 / 交易 / "
            "订单 / 产品 / 供应商 / 制裁名单 / 风险事件，及其关系与动作。",
        },
    )
    return ont["id"]


def main() -> None:
    oid = reset_ontology()
    print(f"ontology {oid}")

    # ---- Object types -------------------------------------------------- #
    object_types: dict[str, dict] = {}

    def add_ot(api, name, icon, color, title, props):
        ot = _req(
            "POST",
            f"/ontology/{oid}/object-types",
            json={
                "api_name": api,
                "display_name": name,
                "icon": icon,
                "color": color,
                "primary_key_property": "id",
                "title_property": title,
                "properties": props,
            },
        )
        object_types[api] = ot
        print(f"  object-type {api} -> {ot['id']}")
        return ot

    add_ot(
        "organization", "组织", "Building2", "#3b82f6", "name",
        [
            prop("id", "ID", required=True, is_primary_key=True),
            prop("name", "名称", required=True, is_title=True),
            prop("industry", "行业"),
            prop("country", "国家/地区"),
            prop("registered_capital", "注册资本", "double"),
            prop("risk_level", "风险等级"),
            prop("established_date", "成立日期", "date"),
        ],
    )
    add_ot(
        "person", "人员", "User", "#06b6d4", "name",
        [
            prop("id", "ID", required=True, is_primary_key=True),
            prop("name", "姓名", required=True, is_title=True),
            prop("role", "角色"),
            prop("nationality", "国籍"),
            prop("pep_flag", "政治公众人物", "boolean"),
            prop("email", "邮箱"),
        ],
    )
    add_ot(
        "account", "银行账户", "CreditCard", "#10b981", "account_no",
        [
            prop("id", "ID", required=True, is_primary_key=True),
            prop("account_no", "账号", required=True, is_title=True),
            prop("currency", "币种"),
            prop("balance", "余额", "double"),
            prop("status", "状态"),
            prop("opened_date", "开户日期", "date"),
        ],
    )
    add_ot(
        "transaction", "交易", "ArrowLeftRight", "#f59e0b", "id",
        [
            prop("id", "ID", required=True, is_primary_key=True, is_title=True),
            prop("amount", "金额", "double"),
            prop("currency", "币种"),
            prop("channel", "渠道"),
            prop("status", "状态"),
            prop("risk_score", "风险评分", "double"),
            prop("occurred_at", "发生时间", "timestamp"),
        ],
    )
    add_ot(
        "product", "产品", "Package", "#8b5cf6", "name",
        [
            prop("id", "ID", required=True, is_primary_key=True),
            prop("name", "名称", required=True, is_title=True),
            prop("category", "类别"),
            prop("unit_price", "单价", "double"),
        ],
    )
    add_ot(
        "order", "订单", "ShoppingCart", "#ec4899", "order_no",
        [
            prop("id", "ID", required=True, is_primary_key=True),
            prop("order_no", "订单号", required=True, is_title=True),
            prop("total_amount", "总金额", "double"),
            prop("status", "状态"),
            prop("order_date", "下单日期", "date"),
        ],
    )
    add_ot(
        "supplier", "供应商", "Truck", "#14b8a6", "name",
        [
            prop("id", "ID", required=True, is_primary_key=True),
            prop("name", "名称", required=True, is_title=True),
            prop("country", "国家/地区"),
            prop("tier", "层级", "integer"),
            prop("reliability_score", "可靠度", "double"),
        ],
    )
    add_ot(
        "sanction", "制裁名单", "ShieldAlert", "#ef4444", "list_name",
        [
            prop("id", "ID", required=True, is_primary_key=True),
            prop("list_name", "名单", required=True, is_title=True),
            prop("reason", "原因"),
            prop("added_date", "加入日期", "date"),
        ],
    )
    add_ot(
        "risk_event", "风险事件", "AlertTriangle", "#dc2626", "title",
        [
            prop("id", "ID", required=True, is_primary_key=True),
            prop("title", "标题", required=True, is_title=True),
            prop("event_type", "类型"),
            prop("severity", "严重度"),
            prop("status", "状态"),
            prop("detected_at", "检测时间", "timestamp"),
            prop("description", "描述"),
        ],
    )

    # ---- Link types ---------------------------------------------------- #
    def add_link(api, name, src, tgt, card):
        lt = _req(
            "POST",
            f"/ontology/{oid}/link-types",
            json={
                "api_name": api,
                "display_name": name,
                "source_object_type_id": object_types[src]["id"],
                "target_object_type_id": object_types[tgt]["id"],
                "cardinality": card,
            },
        )
        print(f"  link-type {api}")
        return lt

    add_link("owns_account", "拥有账户", "organization", "account", "one_to_many")
    add_link("employs", "雇佣", "organization", "person", "one_to_many")
    add_link("controls", "实际控制", "person", "organization", "many_to_many")
    add_link("debits", "付款账户", "transaction", "account", "one_to_many")
    add_link("credits", "收款账户", "transaction", "account", "one_to_many")
    add_link("places_order", "下单", "organization", "order", "one_to_many")
    add_link("order_item", "订单含产品", "order", "product", "many_to_many")
    add_link("supplies", "供应产品", "supplier", "product", "many_to_many")
    add_link("sourced_from", "采购自", "organization", "supplier", "many_to_many")
    add_link("on_sanction", "命中制裁", "person", "sanction", "many_to_many")
    add_link("flags_txn", "标记交易", "risk_event", "transaction", "one_to_many")
    add_link("involves_org", "涉及组织", "risk_event", "organization", "many_to_many")

    # ---- Action types -------------------------------------------------- #
    def add_action(api, name, ot, effect, params):
        at = _req(
            "POST",
            f"/ontology/{oid}/action-types",
            json={
                "api_name": api,
                "display_name": name,
                "object_type_id": object_types[ot]["id"] if ot else None,
                "effect": effect,
                "parameters": params,
            },
        )
        print(f"  action-type {api}")
        return at

    add_action(
        "freeze_account", "冻结账户", "account", "modify",
        {"reason": {"type": "string", "description": "冻结原因"}},
    )
    add_action(
        "flag_transaction", "标记可疑交易", "transaction", "modify",
        {
            "risk_score": {"type": "number", "description": "风险评分"},
            "reason": {"type": "string", "description": "原因"},
        },
    )
    add_action(
        "open_investigation", "立案调查", "risk_event", "create",
        {
            "title": {"type": "string"},
            "severity": {"type": "string"},
            "description": {"type": "string"},
        },
    )
    add_action(
        "escalate_risk_event", "升级风险事件", "risk_event", "modify",
        {"severity": {"type": "string", "description": "新的严重度"}},
    )
    add_action(
        "block_supplier", "封禁供应商", "supplier", "modify",
        {"reason": {"type": "string"}},
    )

    # ---- Object instances ---------------------------------------------- #
    ids: dict[str, str] = {}

    def add_obj(key, ot, props):
        inst = _req(
            "POST",
            f"/ontology/{oid}/object-types/{object_types[ot]['id']}/objects",
            json={"properties": props},
        )
        ids[key] = inst["id"]
        return inst

    add_obj("org_acme", "organization", {"id": "ORG-001", "name": "Acme 控股集团", "industry": "制造业", "country": "CN", "registered_capital": 5_000_000, "risk_level": "中", "established_date": "2009-03-12"})
    add_obj("org_globex", "organization", {"id": "ORG-002", "name": "Globex 贸易有限公司", "industry": "进出口", "country": "SG", "registered_capital": 1_200_000, "risk_level": "高", "established_date": "2018-07-01"})
    add_obj("org_initech", "organization", {"id": "ORG-003", "name": "Initech 科技", "industry": "软件", "country": "US", "registered_capital": 800_000, "risk_level": "低", "established_date": "2015-11-20"})

    add_obj("p_alice", "person", {"id": "P-001", "name": "Alice Chen", "role": "法定代表人", "nationality": "CN", "pep_flag": False, "email": "alice@acme.example"})
    add_obj("p_bob", "person", {"id": "P-002", "name": "Bob Ivanov", "role": "实际控制人", "nationality": "RU", "pep_flag": True, "email": "bob@globex.example"})
    add_obj("p_carol", "person", {"id": "P-003", "name": "Carol Diaz", "role": "财务总监", "nationality": "US", "pep_flag": False, "email": "carol@initech.example"})

    add_obj("acc_acme", "account", {"id": "ACC-001", "account_no": "6225-8800-1001", "currency": "CNY", "balance": 2_300_000, "status": "active", "opened_date": "2010-01-05"})
    add_obj("acc_globex", "account", {"id": "ACC-002", "account_no": "SG-0099-2002", "currency": "USD", "balance": 540_000, "status": "active", "opened_date": "2018-08-10"})
    add_obj("acc_initech", "account", {"id": "ACC-003", "account_no": "US-7700-3003", "currency": "USD", "balance": 980_000, "status": "active", "opened_date": "2016-02-18"})

    add_obj("txn_1", "transaction", {"id": "TXN-1001", "amount": 480_000, "currency": "USD", "channel": "wire", "status": "completed", "risk_score": 0.82, "occurred_at": "2026-04-02T09:31:00"})
    add_obj("txn_2", "transaction", {"id": "TXN-1002", "amount": 12_000, "currency": "CNY", "channel": "card", "status": "completed", "risk_score": 0.12, "occurred_at": "2026-04-03T14:05:00"})
    add_obj("txn_3", "transaction", {"id": "TXN-1003", "amount": 250_000, "currency": "USD", "channel": "wire", "status": "pending", "risk_score": 0.66, "occurred_at": "2026-04-05T22:47:00"})

    add_obj("prod_a", "product", {"id": "PRD-001", "name": "工业传感器 X1", "category": "硬件", "unit_price": 320})
    add_obj("prod_b", "product", {"id": "PRD-002", "name": "控制器固件许可", "category": "软件", "unit_price": 1500})

    add_obj("ord_1", "order", {"id": "ORD-001", "order_no": "PO-2026-0001", "total_amount": 96_000, "status": "fulfilled", "order_date": "2026-03-20"})
    add_obj("ord_2", "order", {"id": "ORD-002", "order_no": "PO-2026-0002", "total_amount": 45_000, "status": "processing", "order_date": "2026-04-01"})

    add_obj("sup_1", "supplier", {"id": "SUP-001", "name": "东方元器件厂", "country": "CN", "tier": 1, "reliability_score": 0.91})
    add_obj("sup_2", "supplier", {"id": "SUP-002", "name": "Offshore Components Ltd", "country": "KP", "tier": 3, "reliability_score": 0.34})

    add_obj("san_1", "sanction", {"id": "SAN-001", "list_name": "OFAC SDN", "reason": "资金转移高风险", "added_date": "2024-09-01"})

    add_obj("risk_1", "risk_event", {"id": "RSK-001", "title": "Globex 大额跨境可疑交易", "event_type": "AML", "severity": "high", "status": "open", "detected_at": "2026-04-02T10:00:00", "description": "TXN-1001 触发跨境大额+高风险评分规则。"})

    # ---- Links --------------------------------------------------------- #
    def add_link_inst(link_type, src, tgt):
        _req(
            "POST",
            f"/ontology/{oid}/links",
            json={
                "link_type_id": _link_id(link_type),
                "source_object_id": ids[src],
                "target_object_id": ids[tgt],
            },
        )

    link_types = {lt["api_name"]: lt["id"] for lt in _req("GET", f"/ontology/{oid}/link-types")["items"]}

    def _link_id(api):
        return link_types[api]

    add_link_inst("owns_account", "org_acme", "acc_acme")
    add_link_inst("owns_account", "org_globex", "acc_globex")
    add_link_inst("owns_account", "org_initech", "acc_initech")
    add_link_inst("employs", "org_acme", "p_alice")
    add_link_inst("employs", "org_globex", "p_bob")
    add_link_inst("employs", "org_initech", "p_carol")
    add_link_inst("controls", "p_bob", "org_globex")
    add_link_inst("debits", "txn_1", "acc_globex")
    add_link_inst("credits", "txn_1", "acc_acme")
    add_link_inst("debits", "txn_3", "acc_globex")
    add_link_inst("credits", "txn_3", "acc_initech")
    add_link_inst("places_order", "org_acme", "ord_1")
    add_link_inst("places_order", "org_initech", "ord_2")
    add_link_inst("order_item", "ord_1", "prod_a")
    add_link_inst("order_item", "ord_2", "prod_b")
    add_link_inst("supplies", "sup_1", "prod_a")
    add_link_inst("supplies", "sup_2", "prod_b")
    add_link_inst("sourced_from", "org_acme", "sup_1")
    add_link_inst("sourced_from", "org_globex", "sup_2")
    add_link_inst("on_sanction", "p_bob", "san_1")
    add_link_inst("flags_txn", "risk_1", "txn_1")
    add_link_inst("involves_org", "risk_1", "org_globex")

    graph = _req("GET", f"/ontology/{oid}/graph")
    print(
        f"done: {len(graph.get('nodes', []))} nodes, "
        f"{len(graph.get('edges', []))} edges",
    )


if __name__ == "__main__":
    main()
