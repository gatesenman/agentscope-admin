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


def prop(api, name, dtype="string", col="", **extra):
    p = {
        "api_name": api,
        "display_name": name,
        "data_type": dtype,
        **extra,
    }
    if col:
        p["column_mapping"] = col
    return p


def reset_ontology() -> str:
    existing = _req("GET", "/ontology/").get("items", [])
    old_ids = [o["id"] for o in existing if o["api_name"] == API_NAME]
    for oid in old_ids:
        _req("DELETE", f"/ontology/{oid}")
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
    new_id = ont["id"]
    # Re-point any agent bindings that pointed at a now-deleted ontology so
    # agents keep following the freshly seeded data instead of querying a
    # stale (deleted) ontology id.
    if old_ids:
        bindings = _req("GET", "/ontology/bindings/all").get("items", [])
        for b in bindings:
            if b.get("ontology_id") in old_ids:
                _req(
                    "PUT",
                    f"/ontology/bindings/{b['agent_id']}",
                    json={
                        "ontology_id": new_id,
                        "enabled": b.get("enabled", True),
                        "allowed_object_types": b.get("allowed_object_types", []),
                        "allowed_actions": b.get("allowed_actions", []),
                    },
                )
                print(f"  rebound agent {b['agent_id']} -> {new_id}")
    return new_id


def main() -> None:
    oid = reset_ontology()
    print(f"ontology {oid}")

    # ---- Datasources (backing data sources for object types) ----------- #
    datasources: dict[str, dict] = {}

    def add_ds(api, name, kind, connection, columns):
        ds = _req(
            "POST",
            f"/ontology/{oid}/datasources",
            json={
                "api_name": api,
                "display_name": name,
                "kind": kind,
                "connection": connection,
                "columns": [{"name": c[0], "data_type": c[1]} for c in columns],
            },
        )
        datasources[api] = ds
        print(f"  datasource {api} -> {ds['id']}")
        return ds

    add_ds(
        "crm", "CRM 客户主数据", "sql",
        {"dsn": "postgres://crm.internal/crm", "schema": "public"},
        [
            ("ORG_ID", "string"), ("ORG_NAME", "string"), ("INDUSTRY", "string"),
            ("COUNTRY", "string"), ("REG_CAPITAL", "double"), ("RISK_LEVEL", "string"),
            ("EST_DATE", "date"), ("PERSON_ID", "string"), ("FULL_NAME", "string"),
            ("ROLE", "string"), ("NATIONALITY", "string"), ("PEP_FLAG", "boolean"),
            ("EMAIL", "string"),
        ],
    )
    add_ds(
        "core_banking", "核心银行系统", "sql",
        {"dsn": "oracle://corebank.internal/CBS", "schema": "CBS"},
        [
            ("ACCT_ID", "string"), ("ACCT_NO", "string"), ("CCY", "string"),
            ("BAL_AMT", "double"), ("ACCT_STATUS", "string"), ("OPEN_DT", "date"),
            ("TXN_ID", "string"), ("AMT", "double"), ("CHANNEL", "string"),
            ("TXN_STATUS", "string"), ("RISK_SCORE", "double"), ("TXN_TS", "timestamp"),
        ],
    )
    add_ds(
        "erp", "ERP 供应链", "dataset",
        {"path": "/datasets/erp/supply_chain", "format": "parquet"},
        [
            ("PRD_ID", "string"), ("PRD_NAME", "string"), ("CATEGORY", "string"),
            ("UNIT_PRICE", "double"), ("ORD_ID", "string"), ("ORDER_NO", "string"),
            ("TOTAL_AMT", "double"), ("ORD_STATUS", "string"), ("ORDER_DT", "date"),
            ("SUP_ID", "string"), ("SUP_NAME", "string"), ("TIER", "integer"),
            ("RELIABILITY", "double"),
        ],
    )
    add_ds(
        "compliance_feed", "合规风险数据源", "rest_api",
        {"base_url": "https://compliance.internal/api", "path": "/feed"},
        [
            ("SAN_ID", "string"), ("LIST_NAME", "string"), ("REASON", "string"),
            ("ADDED_DT", "date"), ("RSK_ID", "string"), ("TITLE", "string"),
            ("EVENT_TYPE", "string"), ("SEVERITY", "string"), ("STATUS", "string"),
            ("DETECTED_TS", "timestamp"), ("DESCRIPTION", "string"),
        ],
    )

    # ---- Object types (each backed by a datasource) -------------------- #
    object_types: dict[str, dict] = {}

    def add_ot(api, name, icon, color, title, ds, table, props):
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
                "datasource_id": datasources[ds]["id"],
                "backing_table": table,
                "properties": props,
            },
        )
        object_types[api] = ot
        print(f"  object-type {api} -> {ot['id']}")
        return ot

    add_ot(
        "organization", "组织", "Building2", "#3b82f6", "name", "crm", "ORGANIZATIONS",
        [
            prop("id", "ID", required=True, is_primary_key=True, col="ORG_ID"),
            prop("name", "名称", required=True, is_title=True, col="ORG_NAME"),
            prop("industry", "行业", col="INDUSTRY"),
            prop("country", "国家/地区", col="COUNTRY"),
            prop("registered_capital", "注册资本", "double", col="REG_CAPITAL"),
            prop("risk_level", "风险等级", col="RISK_LEVEL"),
            prop("established_date", "成立日期", "date", col="EST_DATE"),
        ],
    )
    add_ot(
        "person", "人员", "User", "#06b6d4", "name", "crm", "PERSONS",
        [
            prop("id", "ID", required=True, is_primary_key=True, col="PERSON_ID"),
            prop("name", "姓名", required=True, is_title=True, col="FULL_NAME"),
            prop("role", "角色", col="ROLE"),
            prop("nationality", "国籍", col="NATIONALITY"),
            prop("pep_flag", "政治公众人物", "boolean", col="PEP_FLAG"),
            prop("email", "邮箱", col="EMAIL"),
        ],
    )
    add_ot(
        "account", "银行账户", "CreditCard", "#10b981", "account_no", "core_banking", "ACCOUNTS",
        [
            prop("id", "ID", required=True, is_primary_key=True, col="ACCT_ID"),
            prop("account_no", "账号", required=True, is_title=True, col="ACCT_NO"),
            prop("currency", "币种", col="CCY"),
            prop("balance", "余额", "double", col="BAL_AMT"),
            prop("status", "状态", col="ACCT_STATUS"),
            prop("opened_date", "开户日期", "date", col="OPEN_DT"),
        ],
    )
    add_ot(
        "transaction", "交易", "ArrowLeftRight", "#f59e0b", "id", "core_banking", "TRANSACTIONS",
        [
            prop("id", "ID", required=True, is_primary_key=True, is_title=True, col="TXN_ID"),
            prop("amount", "金额", "double", col="AMT"),
            prop("currency", "币种", col="CCY"),
            prop("channel", "渠道", col="CHANNEL"),
            prop("status", "状态", col="TXN_STATUS"),
            prop("risk_score", "风险评分", "double", col="RISK_SCORE"),
            prop("occurred_at", "发生时间", "timestamp", col="TXN_TS"),
        ],
    )
    add_ot(
        "product", "产品", "Package", "#8b5cf6", "name", "erp", "PRODUCTS",
        [
            prop("id", "ID", required=True, is_primary_key=True, col="PRD_ID"),
            prop("name", "名称", required=True, is_title=True, col="PRD_NAME"),
            prop("category", "类别", col="CATEGORY"),
            prop("unit_price", "单价", "double", col="UNIT_PRICE"),
        ],
    )
    add_ot(
        "order", "订单", "ShoppingCart", "#ec4899", "order_no", "erp", "ORDERS",
        [
            prop("id", "ID", required=True, is_primary_key=True, col="ORD_ID"),
            prop("order_no", "订单号", required=True, is_title=True, col="ORDER_NO"),
            prop("total_amount", "总金额", "double", col="TOTAL_AMT"),
            prop("status", "状态", col="ORD_STATUS"),
            prop("order_date", "下单日期", "date", col="ORDER_DT"),
        ],
    )
    add_ot(
        "supplier", "供应商", "Truck", "#14b8a6", "name", "erp", "SUPPLIERS",
        [
            prop("id", "ID", required=True, is_primary_key=True, col="SUP_ID"),
            prop("name", "名称", required=True, is_title=True, col="SUP_NAME"),
            prop("country", "国家/地区", col="COUNTRY"),
            prop("tier", "层级", "integer", col="TIER"),
            prop("reliability_score", "可靠度", "double", col="RELIABILITY"),
        ],
    )
    add_ot(
        "sanction", "制裁名单", "ShieldAlert", "#ef4444", "list_name", "compliance_feed", "SANCTIONS",
        [
            prop("id", "ID", required=True, is_primary_key=True, col="SAN_ID"),
            prop("list_name", "名单", required=True, is_title=True, col="LIST_NAME"),
            prop("reason", "原因", col="REASON"),
            prop("added_date", "加入日期", "date", col="ADDED_DT"),
        ],
    )
    add_ot(
        "risk_event", "风险事件", "AlertTriangle", "#dc2626", "title", "compliance_feed", "RISK_EVENTS",
        [
            prop("id", "ID", required=True, is_primary_key=True, col="RSK_ID"),
            prop("title", "标题", required=True, is_title=True, col="TITLE"),
            prop("event_type", "类型", col="EVENT_TYPE"),
            prop("severity", "严重度", col="SEVERITY"),
            prop("status", "状态", col="STATUS"),
            prop("detected_at", "检测时间", "timestamp", col="DETECTED_TS"),
            prop("description", "描述", col="DESCRIPTION"),
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

    # ---- Connectors (external systems actions write back to) ----------- #
    connectors: dict[str, dict] = {}

    def add_connector(api, name, kind, config, operations):
        c = _req(
            "POST",
            f"/ontology/{oid}/connectors",
            json={
                "api_name": api,
                "display_name": name,
                "kind": kind,
                "config": config,
                "operations": operations,
            },
        )
        connectors[api] = c
        print(f"  connector {api} -> {c['id']}")
        return c

    add_connector(
        "payments_core", "支付核心系统", "rest",
        {"base_url": "https://corebank.internal/api", "headers": {}, "simulate": True},
        [
            {
                "api_name": "freeze",
                "display_name": "冻结账户",
                "method": "POST",
                "path": "/accounts/{object_id}/freeze",
                "description": "冻结指定账户并记录原因",
                "params": ["freeze_reason"],
            },
        ],
    )
    add_connector(
        "case_management", "工单/立案系统", "rest",
        {"base_url": "https://casemgmt.internal/api", "headers": {}, "simulate": True},
        [
            {
                "api_name": "create_case",
                "display_name": "创建调查工单",
                "method": "POST",
                "path": "/cases",
                "description": "在工单系统中创建一条调查记录",
                "params": ["case_title", "case_severity", "case_detail"],
            },
        ],
    )
    add_connector(
        "aml_engine", "反洗钱规则引擎", "rest",
        {"base_url": "https://aml.internal/api", "headers": {}, "simulate": True},
        [
            {
                "api_name": "flag",
                "display_name": "标记可疑交易",
                "method": "POST",
                "path": "/transactions/{object_id}/flag",
                "description": "向反洗钱引擎上报可疑交易",
                "params": ["score", "note"],
            },
        ],
    )
    add_connector(
        "notification", "通知中心", "webhook",
        {"base_url": "https://notify.internal/hooks", "headers": {}, "simulate": True},
        [
            {
                "api_name": "notify",
                "display_name": "发送告警通知",
                "method": "POST",
                "path": "/alerts",
                "description": "推送供应商封禁等合规告警",
                "params": ["message"],
            },
        ],
    )

    # ---- Action types (bound to connector operations for write-back) --- #
    def add_action(api, name, ot, effect, params, connector=None, operation="", bindings=None):
        at = _req(
            "POST",
            f"/ontology/{oid}/action-types",
            json={
                "api_name": api,
                "display_name": name,
                "object_type_id": object_types[ot]["id"] if ot else None,
                "effect": effect,
                "parameters": params,
                "connector_id": connectors[connector]["id"] if connector else None,
                "connector_operation": operation,
                "parameter_bindings": bindings or {},
            },
        )
        print(f"  action-type {api}")
        return at

    add_action(
        "freeze_account", "冻结账户", "account", "modify",
        {"reason": {"type": "string", "description": "冻结原因"}},
        connector="payments_core", operation="freeze",
        bindings={"reason": "freeze_reason"},
    )
    add_action(
        "flag_transaction", "标记可疑交易", "transaction", "modify",
        {
            "risk_score": {"type": "number", "description": "风险评分"},
            "reason": {"type": "string", "description": "原因"},
        },
        connector="aml_engine", operation="flag",
        bindings={"risk_score": "score", "reason": "note"},
    )
    add_action(
        "open_investigation", "立案调查", "risk_event", "create",
        {
            "title": {"type": "string"},
            "severity": {"type": "string"},
            "description": {"type": "string"},
        },
        connector="case_management", operation="create_case",
        bindings={"title": "case_title", "severity": "case_severity", "description": "case_detail"},
    )
    add_action(
        "escalate_risk_event", "升级风险事件", "risk_event", "modify",
        {"severity": {"type": "string", "description": "新的严重度"}},
    )
    add_action(
        "block_supplier", "封禁供应商", "supplier", "modify",
        {"reason": {"type": "string"}},
        connector="notification", operation="notify",
        bindings={"reason": "message"},
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
