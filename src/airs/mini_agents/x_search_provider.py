"""X/Twitter search provider — searches X via XAgent MCP or twikit.

Primary: XAgent MCP (HTTP or stdio) — requires API key in .config.yaml.
Fallback: twikit library — requires browser-cookie-based authentication.

For the AIRS collector, this provider searches X for jewellery/luxury retail
discussions and returns SearchCandidate objects.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from airs.mini_agents.base_collector import SearchCandidate


class XSearchProvider:
    """Searches X/Twitter via XAgent MCP (primary) or twikit (fallback).

    Configuration is read from ``.config.yaml`` under the ``x_agent`` key.
    If an ``api_key`` is present, the XAgent MCP provider is used.
    Otherwise, falls back to twikit (cookie-based auth).
    """

    def __init__(
        self,
        max_results: int = 10,
        cookies_path: str | None = None,
        mcp_provider: Any | None = None,
    ) -> None:
        self.max_results = max_results
        self.cookies_path = cookies_path
        self._mcp_provider = mcp_provider
        self._twikit_provider: Any | None = None

    @classmethod
    def from_config(cls, config_path: str | Path = ".config.yaml") -> XSearchProvider:
        from airs.providers.x_mcp import XMCPProvider

        try:
            mcp_provider = XMCPProvider.from_config(config_path)
        except Exception:
            mcp_provider = None

        return cls(mcp_provider=mcp_provider)

    def search(self, query: str, source_type: str, time_window: str) -> list[SearchCandidate]:
        # Try XAgent MCP first
        if self._mcp_provider is not None:
            try:
                results = self._mcp_provider.search(query, source_type, time_window)
                if results:
                    return results
            except Exception as exc:
                print(f"[XSearchProvider] MCP search failed, trying fallback: {exc}")

        # Fallback to twikit
        try:
            provider = self._get_twikit_provider()
            return provider.search(query, source_type, time_window)
        except (ImportError, RuntimeError) as exc:
            print(f"[XSearchProvider] twikit fallback also failed: {exc}")
            return []

    def _get_twikit_provider(self) -> _TwikitProvider:
        if self._twikit_provider is None:
            self._twikit_provider = _TwikitProvider(
                max_results=self.max_results,
                cookies_path=self.cookies_path,
            )
        return self._twikit_provider


class _TwikitProvider:
    """Internal twikit-based X search provider (fallback)."""

    def __init__(self, max_results: int = 10, cookies_path: str | None = None) -> None:
        self.max_results = max_results
        self.cookies_path = cookies_path
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from twikit import Client
        except ImportError:
            raise ImportError(
                "twikit is required for XSearchProvider fallback. "
                "Install it with: pip install twikit"
            )

        self._client = Client()

        if self.cookies_path:
            self._client.set_cookies(self.cookies_path)
        else:
            import os

            default_path = os.path.expanduser("~/.twikit_cookies.json")
            if os.path.exists(default_path):
                self._client.set_cookies(default_path)
            else:
                raise RuntimeError(
                    "No twikit cookies found. Please log in first:\n"
                    "  from twikit import Client\n"
                    "  client = Client()\n"
                    "  client.login(auth_info_1='username', auth_info_2='email', auth_info_3='password')\n"
                    "  client.save_cookies('~/.twikit_cookies.json')\n"
                )

        return self._client

    def search(self, query: str, source_type: str, time_window: str) -> list[SearchCandidate]:
        try:
            client = self._get_client()
        except (ImportError, RuntimeError) as exc:
            print(f"[XSearchProvider] twikit client init failed: {exc}")
            return []

        days = self._parse_days(time_window)
        search_query = self._build_search_query(query, days)

        try:
            results = client.search_tweet(search_query, product="Top")
        except Exception as exc:
            print(f"[XSearchProvider] twikit search failed for query={query!r}: {exc}")
            return []

        candidates: list[SearchCandidate] = []
        for tweet in results:
            if len(candidates) >= self.max_results:
                break
            text = getattr(tweet, "text", "") or getattr(tweet, "full_text", "")
            tweet_id = getattr(tweet, "id", "") or getattr(tweet, "id_str", "")
            username = getattr(tweet, "user", None)
            if username and hasattr(username, "screen_name"):
                author = f"@{username.screen_name}"
            else:
                author = "X user"

            url = f"https://x.com/{author}/status/{tweet_id}" if tweet_id else ""
            created_at = getattr(tweet, "created_at", None)
            published_at = str(created_at) if created_at else None

            candidates.append(
                SearchCandidate(
                    title=text[:200] if text else "",
                    url=url,
                    snippet=text[:500] if text else "",
                    source_name=f"X/{author}",
                    published_at=published_at,
                )
            )
        return candidates

    def _build_search_query(self, query: str, days: int) -> str:
        if days <= 1:
            time_filter = "since:today"
        else:
            time_filter = f"since:{self._days_ago_date(days)}"
        return f"{query} {time_filter}"

    @staticmethod
    def _days_ago_date(days: int) -> str:
        from datetime import date, timedelta

        return (date.today() - timedelta(days=days)).isoformat()

    @staticmethod
    def _parse_days(time_window: str) -> int:
        match = re.match(r"(\d+)d", time_window)
        if match:
            return int(match.group(1))
        return 7