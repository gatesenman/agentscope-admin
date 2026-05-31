"""Multi-tenant / RBAC skeleton.

Identity is carried by the ``X-User-ID`` header and every domain table is
already scoped by ``owner_user_id``. This module adds the missing pieces for a
team product: a ``user`` table, a fixed role catalog (admin / editor / viewer)
with permission codes, and a ``/admin/rbac`` API so members and their roles can
be managed from the console. A default ``admin`` user is seeded on startup.
"""
