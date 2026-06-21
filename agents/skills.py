"""knowledge/*.md modules exposed as on-demand Pydantic AI capabilities (skills)."""

from __future__ import annotations

from functools import lru_cache

from core import knowledge as kb


def _describe(module: kb.KnowledgeModule) -> str:
    name = module.meta.get("name", module.id)
    family = module.meta.get("family")
    return f"{name} — {family}" if family else name


@lru_cache
def build_skill_capabilities() -> list:
    from pydantic_ai.capabilities import Capability

    return [
        Capability(
            id=m.id,
            description=_describe(m),
            instructions=m.body,
            defer_loading=True,
        )
        for m in kb.load_all()
    ]
