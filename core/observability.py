"""Logfire observability wiring."""

from __future__ import annotations

from contextlib import nullcontext

from core.config import Settings, get_settings

_configured = False


def configure_observability(app=None, settings: Settings | None = None) -> bool:
    """Configure Logfire + instrument frameworks. Returns True if Logfire is active."""
    global _configured
    s = settings or get_settings()

    try:
        import logfire
    except Exception:
        return False

    if not _configured:
        kwargs = {"environment": s.logfire_environment, "service_name": "crypto-bot"}
        if s.logfire_token:
            kwargs["token"] = s.logfire_token
        try:
            logfire.configure(**kwargs)
            _configured = True
        except Exception:
            return False

        for fn in ("instrument_pydantic_ai", "instrument_httpx"):
            try:
                getattr(logfire, fn)()
            except Exception:
                pass

    if app is not None:
        try:
            logfire.instrument_fastapi(app)
        except Exception:
            pass

    return _configured


def span(name: str, **attrs):
    """A Logfire span if configured, else a no-op context manager."""
    if not _configured:
        return nullcontext()
    try:
        import logfire

        return logfire.span(name, **attrs)
    except Exception:
        return nullcontext()
