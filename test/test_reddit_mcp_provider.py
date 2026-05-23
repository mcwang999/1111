import os

from airs.providers.reddit_mcp import DEFAULT_PROXY_URL, RedditMCPProvider


class StubMCPClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return self.result


def test_reddit_mcp_provider_converts_structured_posts_to_search_candidates():
    client = StubMCPClient(
        {
            "posts": [
                {
                    "title": "Dubai shoppers discuss gold jewellery wedding demand",
                    "permalink": "/r/jewelry/comments/abc123/dubai_gold/",
                    "selftext": "Several users discuss 22k gold jewellery buying before weddings.",
                    "subreddit": "jewelry",
                    "created_utc": 1770000000,
                    "score": 128,
                    "num_comments": 42,
                    "upvote_ratio": 0.91,
                }
            ]
        }
    )
    provider = RedditMCPProvider(mcp_client=client, max_results=5)

    results = provider.search("Dubai gold jewellery", source_type="social", time_window="7d")

    assert len(results) == 1
    assert results[0].title == "Dubai shoppers discuss gold jewellery wedding demand"
    assert results[0].url == "https://www.reddit.com/r/jewelry/comments/abc123/dubai_gold/"
    assert results[0].source_name == "reddit/r/jewelry"
    assert "Score: 128" in results[0].snippet
    assert "Comments: 42" in results[0].snippet
    assert "22k gold jewellery" in results[0].snippet
    assert results[0].published_at is not None
    assert client.calls[0] == (
        "search_reddit",
        {
            "query": "Dubai gold jewellery",
            "limit": 5,
            "sort": "relevance",
            "time": "week",
        },
    )


def test_reddit_mcp_provider_supports_subreddit_search_tool():
    client = StubMCPClient({"results": []})
    provider = RedditMCPProvider(
        mcp_client=client,
        subreddits=["jewelry"],
        search_all=False,
    )

    provider.search("luxury retail", source_type="social", time_window="30d")

    assert client.calls == [
        (
            "search_reddit",
            {
                "subreddits": ["jewelry"],
                "query": "luxury retail",
                "limit": 10,
                "sort": "relevance",
                "time": "month",
            },
        )
    ]


def test_reddit_mcp_provider_defaults_to_buddy_npx_server():
    provider = RedditMCPProvider.from_config("missing-config-file.yaml")

    assert provider.server_config.command == ("npx.cmd" if os.name == "nt" else "npx")
    assert provider.server_config.args == ["-y", "reddit-mcp-buddy"]
    assert provider.server_flavor == "buddy"
    assert provider.proxy_url == DEFAULT_PROXY_URL
    assert provider.search_all_tool == "search_reddit"


def test_reddit_mcp_provider_loads_proxy_url_from_config(tmp_path):
    config = tmp_path / ".config.yaml"
    config.write_text(
        "reddit_mcp:\n"
        "  proxy_url: http://127.0.0.1:7890\n",
        encoding="utf-8",
    )

    provider = RedditMCPProvider.from_config(config)

    assert provider.proxy_url == "http://127.0.0.1:7890"


def test_reddit_mcp_provider_loads_timeout_seconds_from_config(tmp_path):
    config = tmp_path / ".config.yaml"
    config.write_text(
        "reddit_mcp:\n"
        "  timeout_seconds: 45\n",
        encoding="utf-8",
    )

    provider = RedditMCPProvider.from_config(config)

    assert provider.timeout_seconds == 45


def test_reddit_mcp_provider_can_disable_default_proxy(tmp_path):
    config = tmp_path / ".config.yaml"
    config.write_text(
        "reddit_mcp:\n"
        "  proxy_url: none\n",
        encoding="utf-8",
    )

    provider = RedditMCPProvider.from_config(config)

    assert provider.proxy_url is None


def test_reddit_mcp_provider_ignores_stale_reddit_mcp_server_command_for_buddy(tmp_path):
    config = tmp_path / ".config.yaml"
    config.write_text(
        "reddit_mcp:\n"
        "  command: reddit-mcp-server\n",
        encoding="utf-8",
    )

    provider = RedditMCPProvider.from_config(config)

    assert provider.server_config.command == ("npx.cmd" if os.name == "nt" else "npx")
    assert provider.server_config.args == ["-y", "reddit-mcp-buddy"]


def test_reddit_mcp_provider_ignores_placeholder_reddit_credentials(tmp_path):
    config = tmp_path / ".config.yaml"
    config.write_text(
        "reddit_mcp:\n"
        "  client_id: 你的 Reddit client id\n"
        "  client_secret: your reddit client secret\n",
        encoding="utf-8",
    )

    provider = RedditMCPProvider.from_config(config)

    assert "REDDIT_CLIENT_ID" not in provider.server_config.env
    assert "REDDIT_CLIENT_SECRET" not in provider.server_config.env


def test_reddit_mcp_provider_converts_text_tool_output_to_candidates():
    client = StubMCPClient(
        {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Title: Jewellery buying advice in Dubai\n"
                        "Subreddit: jewelry\n"
                        "URL: https://www.reddit.com/r/jewelry/comments/xyz\n"
                        "Score: 18\n"
                        "Comments: 7\n"
                        "Body: Is Dubai gold retail cheaper during shopping festival?"
                    ),
                }
            ]
        }
    )
    provider = RedditMCPProvider(mcp_client=client, max_results=5)

    results = provider.search("Dubai gold retail", source_type="social", time_window="7d")

    assert len(results) == 1
    assert results[0].title == "Jewellery buying advice in Dubai"
    assert results[0].url == "https://www.reddit.com/r/jewelry/comments/xyz"
    assert results[0].source_name == "reddit/r/jewelry"


def test_reddit_mcp_provider_returns_empty_list_for_mcp_error():
    client = StubMCPClient(
        {
            "content": [
                {
                    "type": "text",
                    "text": "Error: Request timeout (10s exceeded)",
                }
            ],
            "isError": True,
        }
    )
    provider = RedditMCPProvider(mcp_client=client, max_results=5)

    assert provider.search("jewellery", source_type="social", time_window="7d") == []
