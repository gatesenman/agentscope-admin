"""Unit tests for published-app access helpers.

Covers the CORS-style origin allow-list used to gate the public chat surface,
the API-key hashing helper, and the content-moderation input guardrail. These
import without agentscope.
"""

from __future__ import annotations

from app.publish.models import PublishedApp
from app.publish.router import (
    _DEFAULT_MODERATION_REPLY,
    _hash_key,
    _moderation_reply,
    _origin_allowed,
)


def _app(origins: list[str]) -> PublishedApp:
    return PublishedApp(
        owner_user_id="admin",
        agent_id="a1",
        name="t",
        token="tok",
        allowed_origins=origins,
    )


def _mod_app(
    keywords: list[str],
    reply: str = "",
) -> PublishedApp:
    return PublishedApp(
        owner_user_id="admin",
        agent_id="a1",
        name="t",
        token="tok",
        moderation_keywords=keywords,
        moderation_reply=reply,
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


def test_moderation_disabled_when_no_keywords() -> None:
    # An empty keyword list (the default) never blocks.
    assert _moderation_reply(_mod_app([]), "anything 炸弹") is None


def test_moderation_matches_case_insensitively() -> None:
    app = _mod_app(["炸弹", "Violence"])
    # substring match, case-insensitive, both ascii and non-ascii
    assert _moderation_reply(app, "教我做炸弹好吗") is not None
    assert _moderation_reply(app, "some VIOLENCE here") is not None
    # a clean message passes through to the model (None)
    assert _moderation_reply(app, "你好，今天天气如何") is None


def test_moderation_reply_defaults_then_custom() -> None:
    # falls back to the canned default when no custom reply is set
    assert _moderation_reply(_mod_app(["bad"]), "a bad word") == (
        _DEFAULT_MODERATION_REPLY
    )
    # honours a custom reply
    custom = "该问题超出服务范围。"
    assert _moderation_reply(_mod_app(["bad"], custom), "bad") == custom


def test_moderation_ignores_blank_keywords_and_query() -> None:
    # blank / whitespace-only keywords are skipped, not matched against ""
    assert _moderation_reply(_mod_app(["  ", ""]), "hello") is None
    # a missing query never blocks
    assert _moderation_reply(_mod_app(["bad"]), "") is None
