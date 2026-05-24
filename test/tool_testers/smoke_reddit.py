"""Smoke test: Reddit MCP provider standalone."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from airs.mcp.reddit_mcp import RedditMCPProvider


provider = RedditMCPProvider.from_config()

print("Searching Reddit via MCP for 'luxury jewellery retail'...")
print("MCP command:", provider.server_config.command if provider.server_config else "<missing>")
print("MCP args:", provider.server_config.args if provider.server_config else [])
print("MCP proxy:", provider.proxy_url or "<direct>")
print("MCP timeout:", provider.timeout_seconds)

client = provider._build_client()
try:
    client.start()
    tools = client.list_tools()
    tool_names = [tool.get("name") for tool in tools]
    print("MCP tools:", ", ".join(tool_names))

    if "reddit_explain" in tool_names:
        explain = client.call_tool("reddit_explain", {"term": "karma"})
        print("reddit_explain smoke:", str(explain))

    results = provider._search_with_client(
        client,
        query="luxury jewellery retail",
        time_window="7d",
    )
    results = provider._deduplicate(results)[: provider.max_results]
finally:
    client.close()

print(f"\nFound {len(results)} results:")
for result in results:
    print(f"  [{result.source_name}] {result.title}")
    print(f"    URL: {result.url}")
    print(f"    Published: {result.published_at}")
    print(f"    Snippet: {result.snippet}")
    # Print all fields of the result
    for attr in vars(result):
        if attr not in ("source_name", "title", "url", "published_at", "snippet"):
            print(f"    {attr}: {getattr(result, attr)}")
    print()

if not results:
    print(
        "No results returned. Check that Node.js/npx is installed and that "
        "`npx -y reddit-mcp-buddy` can run in this environment."
    )
