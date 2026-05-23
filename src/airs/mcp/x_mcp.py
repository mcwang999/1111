"""X/Twitter search provider via XAgent MCP server.

Supports two transport modes:
- http: connects to mcp.getxagent.com (remote, API key only) — default
- stdio: runs x-mcp binary locally (requires x-mcp installed)

Config (.config.yaml)::

    x_agent:
      api_key: "sk_..."
      mode: http              # "http" or "stdio"
      mcp_url: "https://mcp.getxagent.com/mcp"  # http mode endpoint
      search_tool: search_tweets
      max_results: 10
      proxy_url: "http://127.0.0.1:7890"   # optional, set "none" to disable
      # stdio-mode overrides (only used when mode=stdio)
      command: x-mcp
      args: ""
"""

from __future__ import annotations

import json
import os
import queue
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from airs.mini_agents.base_collector import SearchCandidate, parse_simple_yaml
from airs.mcp.base_mcp import BaseMCPClient, MCPServerConfig

DEFAULT_X_MCP_URL = "https://api.getxagent.com/sse"
DEFAULT_PROXY_URL = "http://127.0.0.1:7890"


class XMCPProvider:
    """SearchProvider adapter backed by an XAgent MCP server.

    Uses the MCP protocol (stdio or HTTP) to call XAgent tools such as
    ``search_tweets`` and converts the results into ``SearchCandidate``
    objects compatible with the AIRS collector pipeline.
    """

    def __init__(
        self,
        mcp_client: Any | None = None,
        server_config: MCPServerConfig | None = None,
        api_key: str | None = None,
        mcp_url: str | None = None,
        mode: str = "http",
        max_results: int = 10,
        search_tool: str = "search_tweets",
        proxy_url: str | None = None,
    ) -> None:
        self.mcp_client = mcp_client
        self.server_config = server_config
        self.api_key = api_key
        self.mcp_url = mcp_url or DEFAULT_X_MCP_URL
        self.mode = mode
        self.max_results = max_results
        self.search_tool = search_tool
        self.proxy_url = proxy_url

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config_path: str | Path = ".config.yaml") -> XMCPProvider:
        config = parse_simple_yaml(config_path)
        section = config.get("x_agent") or config.get("x_mcp") or {}
        if not isinstance(section, dict):
            section = {}

        api_key = str(section.get("api_key") or "")
        mcp_url = str(section.get("mcp_url") or DEFAULT_X_MCP_URL)
        mode = str(section.get("mode") or "http").lower()
        max_results = int(section.get("max_results") or 10)
        search_tool = str(section.get("search_tool") or "search_tweets")

        proxy_url = str(section.get("proxy_url") or DEFAULT_PROXY_URL).strip()
        if proxy_url.lower() in {"", "none", "false", "off", "direct"}:
            proxy_url = ""

        # stdio-mode config
        command = str(section.get("command") or "x-mcp")
        args_text = str(section.get("args") or "")
        args = args_text.split() if args_text else []
        env: dict[str, str] = {}
        if api_key:
            env["TWITTER_API_KEY"] = api_key

        server_config = MCPServerConfig(command=command, args=args, env=env)

        return cls(
            server_config=server_config,
            api_key=api_key or None,
            mcp_url=mcp_url,
            mode=mode,
            max_results=max_results,
            search_tool=search_tool,
            proxy_url=proxy_url or None,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(self, query: str, source_type: str, time_window: str) -> list[SearchCandidate]:
        """Search X/Twitter via the configured MCP transport."""
        if self.mode == "http":
            return self._search_http(query, time_window)
        return self._search_stdio(query, time_window)

    # ------------------------------------------------------------------
    # stdio transport
    # ------------------------------------------------------------------

    def _search_stdio(self, query: str, time_window: str) -> list[SearchCandidate]:
        client = self.mcp_client or self._build_stdio_client()
        close_after = self.mcp_client is None
        try:
            if close_after and hasattr(client, "start"):
                client.start()
            result = client.call_tool(
                self.search_tool,
                self._tool_arguments(query, time_window),
            )
            return self._result_to_candidates(result)[: self.max_results]
        except Exception as exc:
            print(f"[XMCPProvider] stdio search failed: {exc}")
            return []
        finally:
            if close_after and hasattr(client, "close"):
                client.close()

    def _build_stdio_client(self) -> BaseMCPClient:
        if self.server_config is None:
            raise RuntimeError("Missing X MCP server config for stdio mode.")
        return BaseMCPClient(self.server_config, proxy_url=self.proxy_url)

    # ------------------------------------------------------------------
    # HTTP transport (MCP over SSE)
    # ------------------------------------------------------------------

    def _search_http(self, query: str, time_window: str) -> list[SearchCandidate]:
        """Search X via XAgent MCP over SSE transport.

        The XAgent SSE endpoint follows the MCP SSE transport spec:
        1. Connect to the SSE endpoint to receive an event stream
        2. The server sends an ``endpoint`` event with the POST URL
        3. Client sends JSON-RPC requests to that POST URL
        4. Responses arrive as SSE events on the original stream
        """
        import httpx
        import threading

        sse_url = self._build_url()
        headers = self._build_headers()
        proxies = self.proxy_url if self.proxy_url else None

        try:
            with httpx.Client(timeout=90, proxy=proxies) as http:
                # We use a background thread to read SSE events while
                # we send requests on the main thread.
                sse_events: queue.Queue[dict[str, Any]] = queue.Queue()
                post_url_holder: list[str] = [""]
                session_id_holder: list[str] = [""]
                sse_connected = threading.Event()
                sse_done = threading.Event()

                def _read_sse():
                    """Background thread: read SSE events from the stream."""
                    event_type = ""
                    try:
                        with http.stream("GET", sse_url, headers=headers) as sse_stream:
                            sse_stream.raise_for_status()

                            # Signal that the SSE connection is established
                            sse_connected.set()

                            for raw_line in sse_stream.iter_lines():
                                if sse_done.is_set():
                                    break
                                line = raw_line if isinstance(raw_line, str) else raw_line.decode("utf-8", errors="replace")
                                line = line.strip()
                                if not line:
                                    continue

                                if line.startswith("event:"):
                                    event_type = line[len("event:"):].strip()
                                    continue

                                if line.startswith("data:"):
                                    data_str = line[len("data:"):].strip()

                                    if event_type == "endpoint":
                                        post_url_holder[0] = data_str
                                        event_type = ""
                                        continue

                                    # Try to parse as JSON-RPC response
                                    try:
                                        msg = json.loads(data_str)
                                        if isinstance(msg, dict):
                                            sse_events.put(msg)
                                    except json.JSONDecodeError:
                                        pass
                                    event_type = ""
                    except Exception as exc:
                        print(f"[XMCPProvider] SSE reader error: {exc}")
                    finally:
                        sse_connected.set()  # Ensure we don't hang
                        sse_done.set()

                # Start SSE reader in background
                sse_thread = threading.Thread(target=_read_sse, daemon=True)
                sse_thread.start()

                # Wait for SSE connection and endpoint discovery
                if not sse_connected.wait(timeout=30):
                    print("[XMCPProvider] Timed out waiting for SSE connection")
                    sse_done.set()
                    return []

                # Wait a bit for the endpoint event
                import time
                for _ in range(50):
                    if post_url_holder[0]:
                        break
                    time.sleep(0.1)

                post_url = post_url_holder[0]
                if not post_url:
                    print("[XMCPProvider] No endpoint event received from SSE stream")
                    sse_done.set()
                    return []

                # Build the full POST URL
                if post_url.startswith("/"):
                    from urllib.parse import urljoin
                    post_url = urljoin(sse_url, post_url)

                # Step 2: Send initialize request
                http.post(
                    post_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "airs", "version": "0.1.0"},
                        },
                    },
                    headers=headers,
                )

                # Wait for initialize response on SSE stream
                init_result = self._wait_for_response(sse_events, request_id=1, timeout=30)
                if init_result is None:
                    print("[XMCPProvider] No initialize response received")
                    sse_done.set()
                    return []

                server_info = init_result.get("serverInfo", {})
                print(f"[XMCPProvider] Connected to {server_info.get('name', '?')} v{server_info.get('version', '?')}")

                # Step 3: Send initialized notification
                http.post(
                    post_url,
                    json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                    headers=headers,
                )

                # Step 4: Call search tool
                http.post(
                    post_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": self.search_tool,
                            "arguments": self._tool_arguments(query, time_window),
                        },
                    },
                    headers=headers,
                )

                # Step 5: Wait for search response on SSE stream
                result = self._wait_for_response(sse_events, request_id=2, timeout=60)
                sse_done.set()

                if result is None:
                    print("[XMCPProvider] No search response received from SSE stream")
                    return []

                return self._result_to_candidates(result)[: self.max_results]

        except Exception as exc:
            print(f"[XMCPProvider] HTTP search failed: {exc}")
            return []

    @staticmethod
    def _wait_for_response(
        sse_events: "queue.Queue[dict[str, Any]]",
        request_id: int,
        timeout: float = 30.0,
    ) -> dict[str, Any] | None:
        """Wait for a JSON-RPC response with the given request ID from the SSE event queue."""
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = sse_events.get(timeout=0.5)
            except Exception:
                continue

            if not isinstance(msg, dict):
                continue

            # Check if this is a response to our request
            msg_id = msg.get("id")
            if msg_id == request_id:
                if "error" in msg:
                    print(f"[XMCPProvider] MCP error response: {msg['error']}")
                    return None
                return msg.get("result", msg)

            # Check for nested result
            if "result" in msg and isinstance(msg["result"], dict):
                # Could be a response without explicit id match
                result = msg["result"]
                if msg_id is None or msg_id == request_id:
                    return result

        return None

    def _build_url(self) -> str:
        url = self.mcp_url
        # For SSE endpoints, don't append apiKey as query param —
        # it goes in the Authorization header instead
        return url

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    @staticmethod
    def _parse_http_response(resp: Any) -> dict[str, Any]:
        """Parse an HTTP response that may be JSON or SSE."""
        content_type = resp.headers.get("content-type", "")

        if "text/event-stream" in content_type:
            # Parse SSE events from the response body
            text = resp.text
            event_type = ""
            for line in text.split("\n"):
                line = line.strip()
                if line.startswith("event:"):
                    event_type = line[len("event:"):].strip()
                    continue
                if line.startswith("data:"):
                    data = line[len("data:"):].strip()
                    try:
                        msg = json.loads(data)
                        if isinstance(msg, dict):
                            if "result" in msg:
                                result = msg["result"]
                                return result if isinstance(result, dict) else {"result": result}
                            if "error" in msg:
                                print(f"[XMCPProvider] MCP error: {msg['error']}")
                                return {}
                    except json.JSONDecodeError:
                        # Multi-line data — accumulate
                        pass
                    continue
            return {}

        # application/json
        try:
            body = resp.json()
        except Exception:
            return {}

        if isinstance(body, dict):
            if "error" in body:
                print(f"[XMCPProvider] MCP error: {body['error']}")
                return {}
            result = body.get("result", body)
            return result if isinstance(result, dict) else {"result": result}

        return {}

    # ------------------------------------------------------------------
    # Tool arguments
    # ------------------------------------------------------------------

    def _tool_arguments(self, query: str, time_window: str) -> dict[str, Any]:
        days = self._parse_days(time_window)
        arguments: dict[str, Any] = {
            "query": query,
            "max_results": self.max_results,
        }
        if days <= 1:
            arguments["time_filter"] = "today"
        elif days <= 7:
            arguments["time_filter"] = "week"
        else:
            arguments["time_filter"] = "month"
        return arguments

    # ------------------------------------------------------------------
    # Result parsing
    # ------------------------------------------------------------------

    def _result_to_candidates(self, result: Any) -> list[SearchCandidate]:
        if isinstance(result, dict) and result.get("isError"):
            message = self._content_text(result) or str(
                result.get("error") or "unknown MCP error"
            )
            print(f"[XMCPProvider] MCP tool returned error: {message[:300]}")
            return []

        tweets = self._extract_tweets(result)
        candidates: list[SearchCandidate] = []
        for tweet in tweets:
            candidate = self._tweet_to_candidate(tweet)
            if candidate is not None:
                candidates.append(candidate)
        return self._deduplicate(candidates)

    def _extract_tweets(self, result: Any) -> list[dict[str, Any]]:
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        if not isinstance(result, dict):
            return []

        # Try common keys for tweet lists
        for key in ("tweets", "results", "items", "data", "posts"):
            value = result.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = self._extract_tweets(value)
                if nested:
                    return nested

        # Try content field (MCP text content)
        content = result.get("content")
        if isinstance(content, list):
            tweets: list[dict[str, Any]] = []
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "text":
                    continue
                text = str(item.get("text") or "")
                tweets.extend(self._text_to_tweets(text))
            return tweets

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

    def _text_to_tweets(self, text: str) -> list[dict[str, Any]]:
        stripped = text.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            return self._extract_tweets(parsed)
        except json.JSONDecodeError:
            pass

        # Try to parse as structured text blocks
        blocks = re.split(r"\n\s*\n", stripped)
        tweets = []
        for block in blocks:
            title = self._extract_text_field(block, "Title")
            url = self._extract_text_field(block, "URL")
            if not title and not url:
                continue
            tweets.append(
                {
                    "title": title,
                    "url": url,
                    "text": (
                        self._extract_text_field(block, "Body")
                        or self._extract_text_field(block, "Text")
                        or block
                    ),
                    "author": (
                        self._extract_text_field(block, "Author")
                        or self._extract_text_field(block, "Username")
                        or "X user"
                    ),
                    "created_at": (
                        self._extract_text_field(block, "Date")
                        or self._extract_text_field(block, "Created")
                    ),
                }
            )
        return tweets

    def _tweet_to_candidate(self, tweet: dict[str, Any]) -> SearchCandidate | None:
        title = str(
            tweet.get("title")
            or tweet.get("text")
            or tweet.get("full_text")
            or tweet.get("content")
            or ""
        ).strip()
        if not title:
            return None

        author = self._extract_author(tweet)
        if not author.startswith("@"):
            author = f"@{author}"

        url = self._extract_url(tweet)
        tweet_id = self._extract_tweet_id(tweet)
        if not url and tweet_id:
            url = f"https://x.com/{author}/status/{tweet_id}"

        body = str(
            tweet.get("text")
            or tweet.get("full_text")
            or tweet.get("content")
            or tweet.get("body")
            or title
        )
        snippet = body[:1000] if body else title

        engagement_parts: list[str] = []
        if tweet.get("likes") is not None:
            engagement_parts.append(f"Likes: {tweet['likes']}")
        if tweet.get("retweets") is not None:
            engagement_parts.append(f"Retweets: {tweet['retweets']}")
        if tweet.get("replies") is not None:
            engagement_parts.append(f"Replies: {tweet['replies']}")
        if tweet.get("views") is not None:
            engagement_parts.append(f"Views: {tweet['views']}")

        if engagement_parts:
            snippet = " | ".join(engagement_parts) + "\n\n" + snippet

        published_at = self._published_at(tweet)

        return SearchCandidate(
            title=title[:200],
            url=url,
            snippet=snippet,
            source_name=f"X/{author}",
            published_at=published_at,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _published_at(self, tweet: dict[str, Any]) -> str | None:
        raw = tweet.get("created_at") or tweet.get("created_utc") or tweet.get("published_at")
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            try:
                return datetime.fromtimestamp(float(raw), tz=timezone.utc).isoformat()
            except (TypeError, ValueError, OSError):
                return str(raw)
        return str(raw)

    @staticmethod
    def _extract_author(tweet: dict[str, Any]) -> str:
        """Extract author/username from a tweet, handling both string and dict values.

        XAgent returns author as a dict like
        ``{'id': '...', 'name': 'Display Name', 'userName': 'handle'}``.
        """
        for key in ("author", "username", "screen_name", "user"):
            value = tweet.get(key)
            if value is None:
                continue
            if isinstance(value, dict):
                # XAgent-style user object
                handle = value.get("userName") or value.get("screen_name") or value.get("name") or ""
                if handle:
                    return str(handle)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "X user"

    @staticmethod
    def _extract_url(tweet: dict[str, Any]) -> str:
        """Extract URL from a tweet, handling both string and dict values."""
        for key in ("url", "permalink"):
            value = tweet.get(key)
            if value is None:
                continue
            if isinstance(value, dict):
                # Some APIs return URL objects
                url = value.get("expanded_url") or value.get("full_url") or value.get("url") or ""
                if url:
                    return str(url)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _extract_tweet_id(tweet: dict[str, Any]) -> str:
        """Extract tweet ID, handling both string and numeric types."""
        for key in ("id", "tweet_id", "id_str"):
            value = tweet.get(key)
            if value is not None:
                return str(value)
        return ""

    @staticmethod
    def _extract_text_field(text: str, label: str) -> str:
        match = re.search(rf"^{re.escape(label)}:\s*(.+)$", text, flags=re.MULTILINE)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _parse_days(time_window: str) -> int:
        match = re.match(r"(\d+)d", time_window)
        if match:
            return int(match.group(1))
        return 7

    @staticmethod
    def _deduplicate(candidates: list[SearchCandidate]) -> list[SearchCandidate]:
        unique: list[SearchCandidate] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = candidate.url or candidate.title
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique