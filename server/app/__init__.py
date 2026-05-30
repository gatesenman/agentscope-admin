"""AgentScope Admin backend.

A FastAPI service built directly on top of AgentScope. It reuses
AgentScope's own app layer (agents, models, credentials, sessions, chat,
schedules, workspace) and augments it with:

- a Palantir-style **Ontology** module (object types, properties, links,
  action types, object instances) exposed over REST, and
- ontology **tools** injected into every agent so the agent can run precise
  semantic queries and execute actions against the ontology.
"""

__version__ = "0.1.0"
