from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from airs.mini_agents.base_collector import SearchCandidate, parse_simple_yaml
from airs.mcp.base_mcp import BaseMCPClient, MCPServerConfig


DEFAULT_SUBREDDITS = [
    "jewelry",
    "jewellery",
    "watches",
    "luxury",
    "diamond",
    "gold",
]

# Local proxy used by the hackathon dev environment. Set reddit_mcp.proxy_url:
# none in .config.yaml if you want the MCP child process to connect directly.
DEFAULT_PROXY_URL = "http://127.0.0.1:7890"


class RedditMCPProvider:
    """SearchProvider adapter backed by a Reddit MCP server."""

    def __init__(
        self,
        mcp_client: Any | None = None,
        server_config: MCPServerConfig | None = None,
        subreddits: list[str] | None = None,
        max_results: int = 10,
        search_all: bool = True,
        server_flavor: str = "buddy",
        proxy_url: str | None = None,
        timeout_seconds: float = 30.0,
        search_all_tool: str = "search_reddit",
        subreddit_search_tool: str = "search_reddit",
    ) -> None:
        self.mcp_client = mcp_client
        self.server_config = server_config
        self.subreddits = subreddits or DEFAULT_SUBREDDITS
        self.max_results = max_results
        self.search_all = search_all
        self.server_flavor = server_flavor
        self.proxy_url = proxy_url
        self.timeout_seconds = timeout_seconds
        self.search_all_tool = search_all_tool
        self.subreddit_search_tool = subreddit_search_tool

    @classmethod
    def from_config(cls, config_path: str | Path = ".config.yaml") -> RedditMCPProvider:
        config = parse_simple_yaml(config_path)
        section = config.get("reddit_mcp") or config.get("reddit") or {}
        if not isinstance(section, dict):
            section = {}

        server_flavor = str(section.get("server_flavor") or "buddy")
        default_command = "npx.cmd" if os.name == "nt" else "npx"
        command = str(section.get("command") or section.get("mcp_command") or default_command)
        if server_flavor == "buddy" and command == "reddit-mcp-server":
            command = default_command
        args_text = str(section.get("args") or section.get("mcp_args") or "-y reddit-mcp-buddy")
        args = args_text.split() if args_text else []

        env = {
            "REDDIT_CLIENT_ID": cls._clean_optional_secret(section.get("client_id")),
            "REDDIT_CLIENT_SECRET": cls._clean_optional_secret(section.get("client_secret")),
            "REDDIT_USER_AGENT": str(section.get("user_agent") or "AIRS/0.1"),
        }
        proxy_url = str(section.get("proxy_url") or DEFAULT_PROXY_URL).strip()
        if proxy_url and proxy_url.lower() not in {"", "none", "false", "off", "direct"}:
            env["HTTP_PROXY"] = proxy_url
            env["HTTPS_PROXY"] = proxy_url
        env = {key: value for key, value in env.items() if value}

        subreddits_text = section.get("subreddits")
        subreddits = (
            [item.strip() for item in str(subreddits_text).split(",") if item.strip()]
            if subreddits_text
            else None
        )

        max_results = int(section.get("max_results") or 10)
        search_all = str(section.get("search_all") or "true").lower() != "false"
        proxy_url = str(section.get("proxy_url") or DEFAULT_PROXY_URL).strip()
        if proxy_url.lower() in {"", "none", "false", "off", "direct"}:
            proxy_url = ""
        server_config = MCPServerConfig(command=command, args=args, env=env)
        return cls(
            server_config=server_config,
            subreddits=subreddits,
            max_results=max_results,
            search_all=search_all,
            server_flavor=server_flavor,
            proxy_url=proxy_url or None,
            timeout_seconds=float(section.get("timeout_seconds") or 30),
            search_all_tool=str(section.get("search_all_tool") or "search_reddit"),
            subreddit_search_tool=str(section.get("subreddit_search_tool") or "search_reddit"),
        )

    @staticmethod
    def _clean_optional_secret(value: Any) -> str:
        text = str(value or "").strip()
        lowered = text.lower()
        if not text:
            return ""
        placeholder_markers = [
            "your ",
            "reddit client",
            "client id",
            "client secret",
            "xxx",
            "todo",
            "placeholder",
        ]
        if any(marker in lowered for marker in placeholder_markers):
            return ""
        return text

    def search(self, query: str, source_type: str, time_window: str) -> list[SearchCandidate]:
        client = self.mcp_client or self._build_client()
        close_after = self.mcp_client is None
        try:
            if close_after and hasattr(client, "start"):
                client.start()
            candidates = self._search_with_client(client, query, time_window)
            return self._deduplicate(candidates)[: self.max_results]
        except Exception as exc:
            print(f"[RedditMCPProvider] search failed: {exc}")
            return []
        finally:
            if close_after and hasattr(client, "close"):
                client.close()

    def _build_client(self) -> BaseMCPClient:
        if self.server_config is None:
            raise RuntimeError("Missing Reddit MCP server config.")
        return BaseMCPClient(
            self.server_config,
            timeout_seconds=self.timeout_seconds,
            proxy_url=self.proxy_url,
        )

    def _search_with_client(
        self,
        client: Any,
        query: str,
        time_window: str,
    ) -> list[SearchCandidate]:
        time_filter = self._time_filter(self._parse_days(time_window))
        if self.search_all:
            result = client.call_tool(
                self.search_all_tool,
                self._tool_arguments(query=query, time_filter=time_filter),
            )
            candidates = self._result_to_candidates(result)
            if candidates:
                return candidates

        candidates: list[SearchCandidate] = []
        for subreddit in self.subreddits:
            if len(candidates) >= self.max_results:
                break
            result = client.call_tool(
                self.subreddit_search_tool,
                self._tool_arguments(
                    query=query,
                    time_filter=time_filter,
                    subreddit=subreddit,
                ),
            )
            candidates.extend(self._result_to_candidates(result, default_subreddit=subreddit))
        return candidates

    def _tool_arguments(
        self,
        query: str,
        time_filter: str,
        subreddit: str | None = None,
    ) -> dict[str, Any]:
        if self.server_flavor == "reddit_mcp_server":
            arguments: dict[str, Any] = {
                "query": query,
                "limit": self.max_results,
                "time_filter": time_filter,
            }
            if subreddit:
                arguments["subreddit"] = subreddit
            return arguments

        arguments = {
            "query": query,
            "limit": self.max_results,
            "sort": "relevance",
            "time": time_filter,
        }
        if subreddit:
            arguments["subreddits"] = [subreddit]
        return arguments

    def _result_to_candidates(
        self,
        result: Any,
        default_subreddit: str | None = None,
    ) -> list[SearchCandidate]:
        if isinstance(result, dict) and result.get("isError"):
            message = self._content_text(result) or str(result.get("error") or "unknown MCP error")
            print(f"[RedditMCPProvider] MCP tool returned error: {message[:300]}")
            return []
        posts = self._extract_posts(result)
        return [
            candidate
            for post in posts
            if (candidate := self._post_to_candidate(post, default_subreddit)) is not None
        ]

    def _extract_posts(self, result: Any) -> list[dict[str, Any]]:
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        if not isinstance(result, dict):
            return []

        for key in ("posts", "results", "items", "data"):
            value = result.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = self._extract_posts(value)
                if nested:
                    return nested

        content = result.get("content")
        if isinstance(content, list):
            posts: list[dict[str, Any]] = []
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "text":
                    continue
                text = str(item.get("text") or "")
                posts.extend(self._text_to_posts(text))
            return posts

        return []

    def _content_text(self, result: dict[str, Any]) -> str:
        content = result.get("content")
        if not isinstance(content, list):
            return ""
        texts = [
            str(item.get("text") or "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return "\n".join(text for text in texts if text)

    def _text_to_posts(self, text: str) -> list[dict[str, Any]]:
        stripped = text.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            return self._extract_posts(parsed)
        except json.JSONDecodeError:
            pass

        blocks = re.split(r"\n\s*\n", stripped)
        posts = []
        for block in blocks:
            title = self._extract_text_field(block, "Title")
            url = self._extract_text_field(block, "URL")
            if not title and not url:
                continue
            posts.append(
                {
                    "title": title,
                    "url": url,
                    "subreddit": self._extract_text_field(block, "Subreddit"),
                    "selftext": self._extract_text_field(block, "Body") or block,
                    "score": self._extract_int_field(block, "Score"),
                    "num_comments": self._extract_int_field(block, "Comments"),
                }
            )
        return posts

    def _post_to_candidate(
        self,
        post: dict[str, Any],
        default_subreddit: str | None = None,
    ) -> SearchCandidate | None:
        title = str(post.get("title") or post.get("name") or "").strip()
        if not title:
            return None

        subreddit = (
            str(
                post.get("subreddit")
                or post.get("community")
                or post.get("subreddit_name_prefixed")
                or default_subreddit
                or "reddit"
            )
            .removeprefix("r/")
            .strip()
        )
        url = self._normalize_url(str(post.get("permalink") or post.get("url") or ""))
        body = (
            post.get("selftext")
            or post.get("body")
            or post.get("text")
            or post.get("description")
            or title
        )
        snippet_parts = [self._engagement_summary(post), str(body).strip()]
        snippet = "\n\n".join(part for part in snippet_parts if part)
        return SearchCandidate(
            title=title,
            url=url,
            snippet=snippet[:1000],
            source_name=f"reddit/r/{subreddit}",
            published_at=self._published_at(post),
        )

    def _engagement_summary(self, post: dict[str, Any]) -> str:
        parts = []
        if post.get("score") is not None:
            parts.append(f"Score: {post['score']}")
        if post.get("num_comments") is not None:
            parts.append(f"Comments: {post['num_comments']}")
        if post.get("upvote_ratio") is not None:
            parts.append(f"Upvote ratio: {post['upvote_ratio']}")
        return " | ".join(parts)

    def _published_at(self, post: dict[str, Any]) -> str | None:
        raw = post.get("created_utc") or post.get("created")
        if raw is None:
            return str(post.get("published_at") or post.get("created_at") or "") or None
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            return str(raw)

    def _normalize_url(self, url: str) -> str:
        if not url:
            return ""
        if url.startswith("/"):
            return f"https://www.reddit.com{url}"
        return url

    def _deduplicate(self, candidates: list[SearchCandidate]) -> list[SearchCandidate]:
        unique: list[SearchCandidate] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = candidate.url or candidate.title
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique

    @staticmethod
    def _extract_text_field(text: str, label: str) -> str:
        match = re.search(rf"^{re.escape(label)}:\s*(.+)$", text, flags=re.MULTILINE)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_int_field(text: str, label: str) -> int | None:
        raw = RedditMCPProvider._extract_text_field(text, label)
        if not raw:
            return None
        match = re.search(r"-?\d+", raw)
        return int(match.group(0)) if match else None

    @staticmethod
    def _parse_days(time_window: str) -> int:
        match = re.match(r"(\d+)d", time_window)
        if match:
            return int(match.group(1))
        return 7

    @staticmethod
    def _time_filter(days: int) -> str:
        if days <= 1:
            return "day"
        if days <= 7:
            return "week"
        if days <= 30:
            return "month"
        if days <= 365:
            return "year"
        return "all"
