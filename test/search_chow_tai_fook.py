"""Search X for Chow Tai Fook overseas market posts using XAgent MCP."""

import json
import queue
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from airs.providers.x_mcp import XMCPProvider


def search_x(provider: XMCPProvider, query: str, time_window: str = "7d") -> list:
    """Search X using XMCPProvider and return candidates."""
    return provider.search(query, source_type="social", time_window=time_window)


def main():
    config_path = Path(__file__).resolve().parent.parent / ".config.yaml"
    provider = XMCPProvider.from_config(config_path)

    queries = [
        "Chow Tai Fook overseas expansion",
        "CTF jewellery store opening",
        "Chow Tai Fook Singapore",
        "周大福 海外",
        "Hearts On Fire diamond",
    ]

    all_results = []
    seen_urls = set()

    for query in queries:
        print(f"\n{'='*60}")
        print(f"Searching: {query}")
        print(f"{'='*60}")
        results = search_x(provider, query, time_window="30d")
        print(f"  Found {len(results)} results")

        for c in results:
            if c.url in seen_urls:
                continue
            seen_urls.add(c.url)
            all_results.append((query, c))

    # Deduplicated summary
    print(f"\n\n{'='*60}")
    print(f"TOTAL UNIQUE RESULTS: {len(all_results)}")
    print(f"{'='*60}")

    for i, (query, c) in enumerate(all_results, 1):
        print(f"\n[{i}] (from: {query})")
        print(f"    Title: {c.title[:120]}")
        print(f"    URL: {c.url}")
        print(f"    Source: {c.source_name}")
        print(f"    Published: {c.published_at}")
        snippet = c.snippet[:200].replace("\n", " ")
        print(f"    Snippet: {snippet}...")


if __name__ == "__main__":
    main()