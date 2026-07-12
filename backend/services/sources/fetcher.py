"""F9: the daily sweep's source of source content — a fetcher abstraction
so the sweep service (services/sources/sweep.py) never depends on how a
document's current text was obtained. Mirrors the fixture-provider
pattern used for AI-touching services (services/composition,
services/extraction, ...): every environment except a hypothetical
future live-HTTP one uses FixtureSourceFetcher, so sweeps are
deterministic in tests, CI, and demos.
"""
from __future__ import annotations

from typing import Protocol


class SourceFetcher(Protocol):
    def fetch(self, url: str) -> str:
        """Return the current raw text content published at `url`."""
        ...


class FixtureSourceFetcher:
    """Returns canned content keyed by URL. register()/update() let a
    test simulate a source changing between two sweep runs."""

    def __init__(self, content_by_url: dict[str, str] | None = None) -> None:
        self._content_by_url = dict(content_by_url or {})

    def register(self, url: str, content: str) -> None:
        self._content_by_url[url] = content

    def fetch(self, url: str) -> str:
        if url not in self._content_by_url:
            raise KeyError(f"No fixture content registered for {url}")
        return self._content_by_url[url]
