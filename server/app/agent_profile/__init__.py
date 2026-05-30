"""Per-agent model defaults and capability profile.

This module augments AgentScope's fixed agent schema (identity / context /
react) with admin-level configuration that a professional agent platform
needs but AgentScope does not persist itself: a default model + credential,
generation parameters, an optional fallback model, and business metadata.

It mirrors the ``AgentBinding`` pattern and reuses the ontology SQLite engine
so no AgentScope core change is required.
"""
