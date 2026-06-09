"""Unit tests for the pure workflow-engine helpers.

These cover the ``{{path}}`` template resolution, dotted/indexed traversal,
workflow-scoped variable coercion, the generic comparator used by list/loop
nodes, and the topological ordering — i.e. the deterministic core that decides
how data flows between nodes. They import cleanly without agentscope so they
run in CI without the heavy git dependency.
"""

from __future__ import annotations

from app.workflow.engine import (
    _coerce_var_list,
    _compare,
    _resolve,
    _topo_order,
    _traverse,
)


def test_resolve_simple_and_nested() -> None:
    ctx = {"start": {"query": "hi"}, "code": {"out": {"total": 30}}}
    assert _resolve("q={{start.query}}", ctx) == "q=hi"
    assert _resolve("t={{code.out.total}}", ctx) == "t=30"


def test_resolve_array_index() -> None:
    ctx = {"code": {"squares": [1, 4, 9, 16]}}
    assert _resolve("{{code.squares.2}}", ctx) == "9"


def test_resolve_missing_is_empty_string() -> None:
    assert _resolve("[{{nope.field}}]", {}) == "[]"


def test_resolve_non_string_is_json_encoded() -> None:
    ctx = {"n": {"obj": {"a": 1}}}
    # dicts/lists are JSON-encoded (non-ASCII preserved)
    assert _resolve("{{n.obj}}", ctx) == '{"a": 1}'
    assert _resolve("{{x.label}}", {"x": {"label": "中文"}}) == "中文"


def test_traverse_list_index_bounds() -> None:
    missing = object()
    assert _traverse([10, 20, 30], ["1"]) == 20
    assert _traverse([10, 20, 30], ["-1"]) == 30
    # out of range / non-int index returns the sentinel, not an exception
    assert _traverse([10], ["5"]).__class__.__name__ == "object"
    assert _traverse({"a": 1}, ["missing"]).__class__.__name__ == "object"


def test_coerce_var_list_shapes() -> None:
    raw = [
        {"name": "n", "value": "42", "type": "number"},
        {"name": "f", "value": "1.5", "type": "number"},
        {"name": "j", "value": '{"k": 1}', "type": "json"},
        {"name": "s", "value": "plain", "type": "string"},
        {"value": "no-name-skipped"},
    ]
    out = _coerce_var_list(raw)
    assert out == {"n": 42, "f": 1.5, "j": {"k": 1}, "s": "plain"}
    # a plain dict is passed through unchanged
    assert _coerce_var_list({"a": 1}) == {"a": 1}
    # None / empty is tolerated
    assert _coerce_var_list(None) == {}


def test_compare_operators() -> None:
    assert _compare("hello world", "contains", "world") is True
    assert _compare("hello", "not_contains", "zzz") is True
    assert _compare("5", "eq", 5) is True  # stringified comparison
    assert _compare(10, "gt", 2) is True
    assert _compare(1, "gte", 2) is False
    assert _compare("", "empty", None) is True
    assert _compare([1], "not_empty", None) is True
    assert _compare("a", "unknown_op", "b") is False


def test_topo_order_linear_and_cycle_fallback() -> None:
    nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    edges = [{"source": "a", "target": "b"}, {"source": "b", "target": "c"}]
    assert _topo_order(nodes, edges) == ["a", "b", "c"]

    # a 2-cycle must not drop nodes nor loop forever
    cyc_nodes = [{"id": "x"}, {"id": "y"}]
    cyc_edges = [
        {"source": "x", "target": "y"},
        {"source": "y", "target": "x"},
    ]
    assert sorted(_topo_order(cyc_nodes, cyc_edges)) == ["x", "y"]
