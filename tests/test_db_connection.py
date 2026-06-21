"""Tests for cloud datastore connection logic (SSL auto-detection).

We don't open real sockets here — just verify that cloud hosts are flagged for SSL and
local hosts are not, which is the bit most likely to break a deploy.
"""

from data.db.connection import _is_local


def test_local_hosts_skip_ssl():
    assert _is_local("postgresql://crypto:crypto@localhost:5432/crypto_bot")
    assert _is_local("postgresql://u:p@127.0.0.1:5432/db")
    assert _is_local("redis://redis:6379/0")  # docker-compose service name


def test_cloud_hosts_require_ssl():
    assert not _is_local(
        "postgresql://u:p@ep-cool-pooler.us-east-2.aws.neon.tech/crypto_bot?sslmode=require"
    )
    assert not _is_local("rediss://default:pw@apn1-xxx.upstash.io:6379")


def test_config_uses_openrouter_single_key():
    from core.config import Settings

    s = Settings()
    # The Anthropic/OpenAI fields are gone; one OpenRouter key drives the LLM layer.
    assert hasattr(s, "openrouter_api_key")
    assert not hasattr(s, "anthropic_api_key")
    # OpenRouter slug form is "provider/model" (has a slash, not the old "provider:model").
    assert "/" in s.llm_model and ":" not in s.llm_model
