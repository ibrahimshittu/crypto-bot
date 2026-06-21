"""Jinja-templated agent prompts."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).resolve().parent


@lru_cache
def _env():
    from jinja2 import Environment, FileSystemLoader

    return Environment(
        loader=FileSystemLoader(str(_DIR)),
        autoescape=False,           # these are text prompts, not HTML
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def render(template: str, **ctx) -> str:
    """Render `<template>.jinja` with the given context."""
    name = template if template.endswith(".jinja") else f"{template}.jinja"
    return _env().get_template(name).render(**ctx)
