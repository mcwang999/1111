"""Backward-compatible import path for the Reddit MCP provider."""

from airs.mcp.reddit_mcp import DEFAULT_SUBREDDITS, RedditMCPProvider

RedditSearchProvider = RedditMCPProvider

__all__ = ["DEFAULT_SUBREDDITS", "RedditMCPProvider", "RedditSearchProvider"]
