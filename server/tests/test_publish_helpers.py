"""Unit tests for published-app access helpers.

Covers the CORS-style origin allow-list used to gate the public chat surface
and the API-key hashing helper. These import without agentscope.
"""

from __future__ import annotations

from app.publish.models import PublishedApp
from app.publish.router import _hash_key, _origin_allowed


def _app(origins: list[str]) -> PublishedApp:
    return PublishedApp(
        owner_user_id="admin",
        agent_id="a1",
        name="t",
        token="tok",
        allowed_origins=origins,
    )


def test_origin_allowed_wildcard_and_empty() -> None:
    assert _origin_allowed(_app(["*"]), "https://evil.example") is True
    assert _origin_allowed(_app([]), "https://anything") is True


def test_origin_allowed_explicit_list() -> None:
    app = _app(["https://site.com"])
    assert _origin_allowed(app, "https://site.com") is True
    assert _origin_allowed(app, "https://other.com") is False
    # a missing Origin header (e.g. same-origin / server-to-server) is allowed
    assert _origin_allowed(app, None) is True


def test_hash_key_is_deterministic_sha256() -> None:
    h1 = _hash_key("secret-abc")
    h2 = _hash_key("secret-abc")
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest
    assert _hash_key("secret-abc") != _hash_key("secret-abd")
