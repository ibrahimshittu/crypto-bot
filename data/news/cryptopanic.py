"""CryptoPanic news adapter."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from core.config import get_settings

_BASE = "https://cryptopanic.com/api/developer/v2/posts/"


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    published_at: str
    currencies: list[str] = field(default_factory=list)
    positive_votes: int = 0
    negative_votes: int = 0

    @property
    def net_sentiment(self) -> int:
        return self.positive_votes - self.negative_votes


class CryptoPanicClient:
    def __init__(self, api_key: str | None = None, timeout: float = 10.0):
        self.api_key = api_key if api_key is not None else get_settings().cryptopanic_api_key
        self.timeout = timeout

    async def recent(self, *, currencies: list[str] | None = None, limit: int = 50) -> list[NewsItem]:
        """Fetch recent posts. Degrades to [] on any error."""
        if not self.api_key:
            return []
        params: dict[str, str] = {"auth_token": self.api_key, "public": "true"}
        if currencies:
            params["currencies"] = ",".join(currencies)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(_BASE, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return []

        items: list[NewsItem] = []
        seen: set[str] = set()
        for post in data.get("results", [])[:limit]:
            url = post.get("url") or post.get("original_url", "")
            if url in seen:
                continue
            seen.add(url)
            votes = post.get("votes", {}) or {}
            items.append(
                NewsItem(
                    title=post.get("title", ""),
                    url=url,
                    published_at=post.get("published_at", ""),
                    currencies=[c.get("code", "") for c in post.get("instruments", []) or post.get("currencies", []) or []],
                    positive_votes=int(votes.get("positive", 0) or 0),
                    negative_votes=int(votes.get("negative", 0) or 0),
                )
            )
        return items
