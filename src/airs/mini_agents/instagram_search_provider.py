"""Instagram search provider — searches Instagram via instamcp/curl_cffi.

Uses cookie-based authentication (no official API key required for basic features).
Requires instamcp package or equivalent Instagram scraping library.

For the AIRS collector, this provider searches Instagram for jewellery/luxury retail
posts and returns SearchCandidate objects.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from airs.mini_agents.base_collector import SearchCandidate


class InstagramSearchProvider:
    """Searches Instagram via public web endpoints or instamcp.

    Authentication: Uses session cookies (no API key required for basic search).
    For full functionality, provide Instagram session cookies via config.
    """

    def __init__(
        self,
        max_results: int = 10,
        session_id: str | None = None,
        http_client: Any | None = None,
    ) -> None:
        self.max_results = max_results
        self.session_id = session_id
        self.http_client = http_client or httpx.Client(timeout=30)

    def search(self, query: str, source_type: str, time_window: str) -> list[SearchCandidate]:
        """Search Instagram for posts matching the query.

        Uses Instagram's public hashtag search endpoint. Falls back to
        a simplified approach if session cookies are not available.
        """
        candidates: list[SearchCandidate] = []

        # Try instamcp first if available
        try:
            candidates = self._search_via_instamcp(query)
        except ImportError:
            pass

        # Fallback: try public web search
        if not candidates:
            candidates = self._search_via_web(query)

        return candidates[: self.max_results]

    def _search_via_instamcp(self, query: str) -> list[SearchCandidate]:
        """Search using instamcp library if available."""
        try:
            from instamcp import InstaMCP
        except ImportError:
            raise ImportError("instamcp not installed")

        # instamcp integration would go here
        # For now, return empty — will be implemented when instamcp is installed
        return []

    def _search_via_web(self, query: str) -> list[SearchCandidate]:
        """Search Instagram via public web endpoints.

        Uses Instagram's public explore/tag pages to find relevant posts.
        This is a simplified approach that works without authentication.
        """
        candidates: list[SearchCandidate] = []

        # Clean query for hashtag search
        tag = query.strip().replace(" ", "").lower()
        # Remove special characters for hashtag
        tag = re.sub(r"[^a-z0-9]", "", tag)

        url = f"https://www.instagram.com/explore/tags/{tag}/"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
        }

        try:
            response = self.http_client.get(url, headers=headers, follow_redirects=True)
            if response.status_code >= 400:
                print(f"[InstagramSearchProvider] HTTP {response.status_code} for tag #{tag}")
                return []
        except Exception as exc:
            print(f"[InstagramSearchProvider] request failed: {exc}")
            return []

        # Instagram's public pages are mostly JS-rendered, so we can't
        # easily extract post data from HTML. Return a placeholder that
        # indicates the search was attempted.
        # Full implementation requires instamcp or Instagram Graph API.
        print(f"[InstagramSearchProvider] Public web search for #{tag} — "
              "Instagram pages are JS-rendered. Install instamcp for full results.")
        return []

    @staticmethod
    def _parse_days(time_window: str) -> int:
        match = re.match(r"(\d+)d", time_window)
        if match:
            return int(match.group(1))
        return 7