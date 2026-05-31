"""Visual workflow orchestration (Dify-style).

A :class:`Workflow` stores a node/edge graph. The execution engine
(:mod:`.engine`) runs the graph as a DAG: it topologically orders nodes,
follows condition branches, resolves ``{{path}}`` template variables against a
shared run context, and streams node/text/finish events over SSE.

Supported node types: ``start``, ``llm``, ``agent``, ``knowledge``,
``condition``, ``template``, ``answer``/``end``.
"""
