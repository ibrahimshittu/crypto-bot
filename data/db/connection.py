"""Lazy, TLS-aware Postgres + Redis connections for cloud datastores."""

from __future__ import annotations

import ssl
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from core.config import Settings, get_settings

_pg_pool = None
_redis = None

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "scripts" / "db_init.sql"

# Hosts that should NOT use SSL (local dev); everything else gets SSL.
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "db", "redis", ""}


def _is_local(url: str) -> bool:
    return urlparse(url).hostname in _LOCAL_HOSTS


def _ssl_context_for(url: str):
    """Build an asyncpg SSL context that honors the URL's `sslmode`."""
    if _is_local(url):
        return None
    sslmode = (parse_qs(urlparse(url).query).get("sslmode", ["require"])[0]).lower()
    ctx = ssl.create_default_context()
    if sslmode not in ("verify-ca", "verify-full"):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def get_pg_pool(settings: Settings | None = None):
    """Return a shared asyncpg pool, enabling SSL automatically for cloud hosts."""
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool

    import asyncpg

    s = settings or get_settings()
    dsn = s.database_url
    clean_dsn = dsn.split("?")[0]
    ssl_ctx = _ssl_context_for(dsn)

    _pg_pool = await asyncpg.create_pool(clean_dsn, ssl=ssl_ctx, min_size=1, max_size=10)
    return _pg_pool


def get_redis(settings: Settings | None = None):
    """Return a shared async Redis client. `rediss://` enables TLS (Upstash/Redis Cloud)."""
    global _redis
    if _redis is not None:
        return _redis

    from redis import asyncio as aioredis

    s = settings or get_settings()
    kwargs: dict = {"decode_responses": True}
    if s.redis_url.startswith("rediss://"):
        import certifi

        kwargs["ssl_ca_certs"] = certifi.where()
    _redis = aioredis.from_url(s.redis_url, **kwargs)
    return _redis


async def init_schema(settings: Settings | None = None) -> None:
    """Apply scripts/db_init.sql (idempotent; TimescaleDB-optional)."""
    pool = await get_pg_pool(settings)
    sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    async with pool.acquire() as conn:
        await conn.execute(sql)


async def healthcheck(settings: Settings | None = None) -> dict:
    """Ping both datastores. Returns {'postgres': bool|str, 'redis': bool|str}."""
    result: dict[str, object] = {}
    try:
        pool = await get_pg_pool(settings)
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        result["postgres"] = True
    except Exception as e:
        result["postgres"] = f"error: {e}"
    try:
        r = get_redis(settings)
        await r.ping()
        result["redis"] = True
    except Exception as e:
        result["redis"] = f"error: {e}"
    return result


async def close_connections() -> None:
    global _pg_pool, _redis
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None
    if _redis is not None:
        await _redis.aclose()
        _redis = None
