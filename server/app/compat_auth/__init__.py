"""Compatibility auth endpoints for the vue-vben-admin frontend.

The vben Element-Plus app ships with a demo authentication flow that expects a
`{ "code": 0, "data": ... }` response envelope and the endpoints
`/auth/login`, `/auth/codes`, `/auth/logout`, `/user/info` and `/menu/all`.

Since the real identity layer (JWT) is not built yet, this module provides a
minimal single-tenant implementation so the admin shell is usable end to end.
The issued token is a static placeholder; the AgentScope routers continue to
identify the user via the ``X-User-ID`` header.
"""
