"""Observability: token-usage / cost capture and aggregation.

AgentScope streams ``MODEL_CALL_END`` events carrying ``input_tokens`` /
``output_tokens`` per model call. The chat endpoint lives in AgentScope core
(which we do not modify), so usage is captured at the edges we control:

* the debug console reports each ``MODEL_CALL_END`` to ``POST /admin/usage``;
* the published-app proxy records usage server-side while relaying SSE frames.

Rows land in a single ``usage_log`` table that the dashboard aggregates into
token totals, per-model / per-day breakdowns, and an estimated cost.
"""
