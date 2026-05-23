"""Tests for XMCPProvider (XAgent MCP search provider)."""

import json
from unittest.mock import MagicMock, patch

from airs.mini_agents.base_collector import SearchCandidate
from airs.providers.x_mcp import XMCPProvider, DEFAULT_X_MCP_URL


class StubMCPClient:
    """Stub for stdio-mode BaseMCPClient."""

    def __init__(self, result):
        self.result = result
        self.calls = []
        self._started = False

    def start(self):
        self._started = True

    def close(self):
        self._started = False

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return self.result


def test_x_mcp_provider_converts_structured_tweets_to_search_candidates():
    client = StubMCPClient(
        {
            "tweets": [
                {
                    "title": "Gold jewellery demand surges in Dubai",
                    "text": "Dubai shoppers are buying more 22k gold jewellery ahead of wedding season.",
                    "url": "https://x.com/@jewelryfan/status/123456",
                    "author": "jewelryfan",
                    "likes": 150,
                    "retweets": 30,
                    "replies": 12,
                    "created_at": "2025-01-15T10:30:00Z",
                }
            ]
        }
    )
    provider = XMCPProvider(mcp_client=client, mode="stdio", max_results=5)

    results = provider.search("Dubai gold jewellery", source_type="social", time_window="7d")

    assert len(results) == 1
    assert results[0].title == "Gold jewellery demand surges in Dubai"
    assert results[0].url == "https://x.com/@jewelryfan/status/123456"
    assert results[0].source_name == "X/@jewelryfan"
    assert "Likes: 150" in results[0].snippet
    assert "Retweets: 30" in results[0].snippet
    assert results[0].published_at is not None
    assert client.calls[0] == (
        "search_tweets",
        {
            "query": "Dubai gold jewellery",
            "max_results": 5,
            "time_filter": "week",
        },
    )


def test_x_mcp_provider_handles_text_content():
    client = StubMCPClient(
        {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        [
                            {
                                "title": "Luxury watches trend in Singapore",
                                "text": "Singapore market sees 15% growth in luxury watch sales.",
                                "url": "https://x.com/@watchsg/status/789",
                                "author": "watchsg",
                                "likes": 200,
                                "created_at": "2025-02-01T08:00:00Z",
                            }
                        ]
                    ),
                }
            ]
        }
    )
    provider = XMCPProvider(mcp_client=client, mode="stdio", max_results=5)

    results = provider.search("luxury watches Singapore", source_type="social", time_window="30d")

    assert len(results) == 1
    assert results[0].title == "Luxury watches trend in Singapore"
    assert results[0].source_name == "X/@watchsg"


def test_x_mcp_provider_returns_empty_for_mcp_error():
    client = StubMCPClient(
        {
            "content": [
                {
                    "type": "text",
                    "text": "Error: Rate limit exceeded",
                }
            ],
            "isError": True,
        }
    )
    provider = XMCPProvider(mcp_client=client, mode="stdio", max_results=5)

    assert provider.search("jewellery", source_type="social", time_window="7d") == []


def test_x_mcp_provider_deduplicates_by_url():
    client = StubMCPClient(
        {
            "tweets": [
                {
                    "title": "Gold demand in Dubai",
                    "text": "Dubai gold demand up 20%",
                    "url": "https://x.com/@user1/status/111",
                    "author": "user1",
                },
                {
                    "title": "Gold demand in Dubai (retweet)",
                    "text": "Dubai gold demand up 20%",
                    "url": "https://x.com/@user1/status/111",
                    "author": "user2",
                },
            ]
        }
    )
    provider = XMCPProvider(mcp_client=client, mode="stdio", max_results=10)

    results = provider.search("Dubai gold", source_type="social", time_window="7d")

    assert len(results) == 1


def test_x_mcp_provider_time_filter_today():
    client = StubMCPClient({"tweets": []})
    provider = XMCPProvider(mcp_client=client, mode="stdio", max_results=5)

    provider.search("test", source_type="social", time_window="1d")

    assert client.calls[0][1]["time_filter"] == "today"


def test_x_mcp_provider_time_filter_week():
    client = StubMCPClient({"tweets": []})
    provider = XMCPProvider(mcp_client=client, mode="stdio", max_results=5)

    provider.search("test", source_type="social", time_window="7d")

    assert client.calls[0][1]["time_filter"] == "week"


def test_x_mcp_provider_time_filter_month():
    client = StubMCPClient({"tweets": []})
    provider = XMCPProvider(mcp_client=client, mode="stdio", max_results=5)

    provider.search("test", source_type="social", time_window="30d")

    assert client.calls[0][1]["time_filter"] == "month"


def test_x_mcp_provider_from_config_defaults(tmp_path):
    config = tmp_path / ".config.yaml"
    config.write_text(
        "x_agent:\n"
        "  api_key: test-key-123\n",
        encoding="utf-8",
    )

    provider = XMCPProvider.from_config(config)

    assert provider.api_key == "test-key-123"
    assert provider.mode == "http"
    assert provider.mcp_url == DEFAULT_X_MCP_URL
    assert provider.search_tool == "search_tweets"
    assert provider.max_results == 10


def test_x_mcp_provider_from_config_custom_settings(tmp_path):
    config = tmp_path / ".config.yaml"
    config.write_text(
        "x_agent:\n"
        "  api_key: my-key\n"
        "  mode: stdio\n"
        "  search_tool: x_search\n"
        "  max_results: 20\n"
        "  proxy_url: none\n",
        encoding="utf-8",
    )

    provider = XMCPProvider.from_config(config)

    assert provider.api_key == "my-key"
    assert provider.mode == "stdio"
    assert provider.search_tool == "x_search"
    assert provider.max_results == 20
    assert provider.proxy_url is None


def test_x_mcp_provider_builds_url_with_api_key():
    provider = XMCPProvider(
        api_key="test-key",
        mcp_url="https://api.getxagent.com/sse",
        mode="http",
    )

    url = provider._build_url()
    # API key goes in Authorization header, not URL, for SSE transport
    assert url == "https://api.getxagent.com/sse"
    headers = provider._build_headers()
    assert headers["Authorization"] == "Bearer test-key"


def test_x_mcp_provider_builds_url_without_api_key():
    provider = XMCPProvider(
        mcp_url="https://mcp.getxagent.com/mcp",
        mode="http",
    )

    url = provider._build_url()
    assert url == "https://mcp.getxagent.com/mcp"


def test_x_mcp_provider_builds_headers_with_api_key():
    provider = XMCPProvider(api_key="test-key", mode="http")

    headers = provider._build_headers()

    assert headers["Authorization"] == "Bearer test-key"
    assert headers["Content-Type"] == "application/json"


def test_x_mcp_provider_skips_empty_title_tweets():
    client = StubMCPClient(
        {
            "tweets": [
                {
                    "title": "",
                    "text": "",
                    "url": "https://x.com/@user/status/123",
                    "author": "user",
                },
                {
                    "title": "Valid tweet",
                    "text": "Some content",
                    "url": "https://x.com/@user/status/456",
                    "author": "user",
                },
            ]
        }
    )
    provider = XMCPProvider(mcp_client=client, mode="stdio", max_results=5)

    results = provider.search("test", source_type="social", time_window="7d")

    assert len(results) == 1
    assert results[0].title == "Valid tweet"


def test_x_mcp_provider_handles_author_without_at():
    client = StubMCPClient(
        {
            "tweets": [
                {
                    "title": "Test tweet",
                    "text": "Content",
                    "url": "https://x.com/@testuser/status/1",
                    "author": "testuser",
                }
            ]
        }
    )
    provider = XMCPProvider(mcp_client=client, mode="stdio", max_results=5)

    results = provider.search("test", source_type="social", time_window="7d")

    assert results[0].source_name == "X/@testuser"


def test_x_mcp_provider_handles_author_with_at():
    client = StubMCPClient(
        {
            "tweets": [
                {
                    "title": "Test tweet",
                    "text": "Content",
                    "url": "https://x.com/@testuser/status/1",
                    "author": "@testuser",
                }
            ]
        }
    )
    provider = XMCPProvider(mcp_client=client, mode="stdio", max_results=5)

    results = provider.search("test", source_type="social", time_window="7d")

    assert results[0].source_name == "X/@testuser"


def test_x_mcp_provider_constructs_url_from_tweet_id():
    client = StubMCPClient(
        {
            "tweets": [
                {
                    "title": "Test tweet",
                    "text": "Content",
                    "id": "999888777",
                    "author": "testuser",
                }
            ]
        }
    )
    provider = XMCPProvider(mcp_client=client, mode="stdio", max_results=5)

    results = provider.search("test", source_type="social", time_window="7d")

    assert results[0].url == "https://x.com/@testuser/status/999888777"


def test_x_mcp_provider_handles_structured_text_blocks():
    client = StubMCPClient(
        {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Title: Dubai gold retail update\n"
                        "URL: https://x.com/@dubaigold/status/555\n"
                        "Author: dubaigold\n"
                        "Date: 2025-03-10\n"
                        "Body: Gold retail sales up 15% in Q1"
                    ),
                }
            ]
        }
    )
    provider = XMCPProvider(mcp_client=client, mode="stdio", max_results=5)

    results = provider.search("Dubai gold", source_type="social", time_window="7d")

    assert len(results) == 1
    assert results[0].title == "Dubai gold retail update"
    assert results[0].url == "https://x.com/@dubaigold/status/555"
    assert results[0].source_name == "X/@dubaigold"