"""Knowledge-base loader: parses YAML frontmatter + Markdown body of modules under `knowledge/`."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"


@dataclass(frozen=True)
class KnowledgeModule:
    """One parsed knowledge document."""

    path: Path
    category: str
    meta: dict[str, Any] = field(default_factory=dict)
    body: str = ""

    @property
    def id(self) -> str:
        return str(self.meta.get("id") or self.path.stem)


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body). Frontmatter is a leading '---' fenced YAML block."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            meta = yaml.safe_load(parts[1]) or {}
            if not isinstance(meta, dict):
                meta = {}
            return meta, parts[2].lstrip("\n")
    return {}, text


def load_module(path: Path) -> KnowledgeModule:
    text = path.read_text(encoding="utf-8")
    meta, body = _split_frontmatter(text)
    category = path.parent.name
    return KnowledgeModule(path=path, category=category, meta=meta, body=body)


@lru_cache
def load_all(knowledge_dir: str | None = None) -> tuple[KnowledgeModule, ...]:
    """Load every .md module under the knowledge dir (cached)."""
    base = Path(knowledge_dir) if knowledge_dir else KNOWLEDGE_DIR
    modules: list[KnowledgeModule] = []
    for path in sorted(base.rglob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        modules.append(load_module(path))
    return tuple(modules)


def by_category(category: str) -> list[KnowledgeModule]:
    return [m for m in load_all() if m.category == category]


def strategies() -> list[KnowledgeModule]:
    """All strategy modules, including ones flagged excluded/later (check meta['status'])."""
    return by_category("strategies")


def tradeable_strategies() -> list[KnowledgeModule]:
    """Strategy modules we actually run now (exclude documented-only families)."""
    excluded = {"documented_excluded_at_our_size", "phase_later"}
    return [m for m in strategies() if m.meta.get("status") not in excluded]


def get(module_id: str) -> KnowledgeModule | None:
    for m in load_all():
        if m.id == module_id:
            return m
    return None
